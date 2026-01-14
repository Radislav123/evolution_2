import datetime
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import arcade
import numpy as np
import numpy.typing as npt
import pyglet
from arcade.gl import BufferDescription

from core.service.object import PhysicalObject, ProjectionObject
from simulator.substance import Substance


if TYPE_CHECKING:
    from simulator.window import ProjectWindow

CellIterator = npt.NDArray[np.int32]
VoxelIterator = CellIterator
ColorIterator = npt.NDArray[np.uint8]


class WorldProjection(ProjectionObject):
    def __init__(self, world: World, window: "ProjectWindow") -> None:
        super().__init__()
        self.window = window
        self.ctx = self.window.ctx

        self.world = world
        self.voxel_count = self.world.cell_count
        self.iterator: VoxelIterator = self.world.iterator

        self.colors: ColorIterator = np.zeros((*self.world.shape, 4), dtype = np.uint8)

        self.color_texture_id = pyglet.gl.GLuint()
        pyglet.gl.glGenTextures(1, self.color_texture_id)
        pyglet.gl.glBindTexture(pyglet.gl.GL_TEXTURE_3D, self.color_texture_id)

        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_WRAP_S, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_WRAP_T, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_WRAP_R, pyglet.gl.GL_CLAMP_TO_EDGE)

        # performance: Пометить текстуру как неизменяемую для GPU, чтобы сократить время чтения из нее
        pyglet.gl.glTexImage3D(
            pyglet.gl.GL_TEXTURE_3D,
            0,
            pyglet.gl.GL_RGBA8,
            self.world.width,
            self.world.length,
            self.world.height,
            0,
            pyglet.gl.GL_RGBA,
            pyglet.gl.GL_UNSIGNED_BYTE,
            None
        )
        pyglet.gl.glActiveTexture(pyglet.gl.GL_TEXTURE0)

        self.program = self.ctx.load_program(
            vertex_shader = f"{self.settings.SHADERS}/vertex.glsl",
            fragment_shader = f"{self.settings.SHADERS}/fragment.glsl"
        )
        self.program["u_colors"] = 0
        self.program["u_window_size"] = self.window.size
        self.program["u_fov_scale"] = self.window.projector.projection.fov_scale
        self.program["u_near"] = self.window.projector.projection.near
        self.program["u_far"] = self.window.projector.projection.far
        self.program["u_world_shape"] = self.world.shape
        # noinspection PyTypeChecker
        self.program["u_background"] = tuple(component / 255 for component in self.window.background_color)
        self.scene = arcade.gl.geometry.quad_2d_fs()

        self.need_update = True

    def start(self) -> None:
        pass

    # todo: Для ускорения можно перейти на indirect render?
    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            if self.need_update:
                self.mix_colors()

                pyglet.gl.glPixelStorei(pyglet.gl.GL_UNPACK_ALIGNMENT, 1)
                pyglet.gl.glTexSubImage3D(
                    pyglet.gl.GL_TEXTURE_3D,
                    0,
                    0,
                    0,
                    0,
                    self.world.width,
                    self.world.length,
                    self.world.height,
                    pyglet.gl.GL_RGBA,
                    pyglet.gl.GL_UNSIGNED_BYTE,
                    self.colors.tobytes()
                )

            self.program["u_view_position"] = self.window.projector.view.position
            self.program["u_view_forward"] = self.window.projector.view.forward
            self.program["u_view_right"] = self.window.projector.view.right
            self.program["u_view_up"] = self.window.projector.view.up
            self.program["u_zoom"] = self.window.projector.view.zoom

            self.scene.render(self.program)

    def mix_colors(self) -> None:
        if self.settings.COLOR_TEST:
            index_z, index_y, index_x = np.indices(self.world.shape)
            self.colors[:, :, :, 0] = (index_x / (self.world.shape[2] - 1) * 255).astype(np.uint8)
            self.colors[:, :, :, 1] = (index_y / (self.world.shape[1] - 1) * 255).astype(np.uint8)
            self.colors[:, :, :, 2] = (index_z / (self.world.shape[0] - 1) * 255).astype(np.uint8)
            self.colors[:, :, :, 3] = max(255 // max(self.world.shape), 5)
        else:
            colors = Substance.colors[self.world.substances]
            absorptions = Substance.absorptions[self.world.substances]

            substances_optical_depth = absorptions * self.world.quantities
            voxels_optical_depth = np.sum(substances_optical_depth, axis = -1, keepdims = True)
            voxels_optical_depth = np.where(voxels_optical_depth == 0, 1e-9, voxels_optical_depth)
            absorption_weights = substances_optical_depth / voxels_optical_depth

            rgb = np.sqrt(np.sum((colors ** 2) * absorption_weights[..., np.newaxis], axis = -2))
            transmittances = np.exp(-voxels_optical_depth.squeeze(-1) * self.settings.OPTICAL_DENSITY_SCALE)
            opacities = (1.0 - transmittances) * 255

            self.colors[..., :3] = rgb.astype(np.uint8)
            self.colors[..., 3] = opacities.astype(np.uint8)

        self.need_update = False


class World(PhysicalObject):
    def __init__(self) -> None:
        super().__init__()
        self.shape = self.settings.WORLD_SHAPE
        self.width, self.length, self.height = self.shape
        assert self.width > 0 and self.length > 0 and self.height > 0, "World width, length and height must be greater then zero"

        self.center_x = -(self.width // 2)
        self.center_y = -(self.length // 2)
        self.center_z = -(self.height // 2)
        self.center = (self.center_x, self.center_y, self.center_z)

        self.iterator: CellIterator = np.stack(
            np.indices(self.shape[::-1])[::-1],
            axis = -1,
            dtype = np.int32
        ).reshape(-1, 3)

        self.cell_count = self.width * self.length * self.height
        # todo: Для уменьшения количества промахов кэша можно использовать кривую Мортона
        #  для хранения всех массивов (материалов, количество и т.д.)
        self.substances = np.zeros((*self.shape, self.settings.CELL_SUBSTANCES_MAX_COUNT), dtype = np.uint16)
        self.quantities = np.zeros((*self.shape, self.settings.CELL_SUBSTANCES_MAX_COUNT), dtype = np.uint16)

        self.seed = self.settings.WORLD_SEED
        if self.seed is None:
            self.seed = datetime.datetime.now().timestamp()
        random.seed(self.seed)
        self.age = 0

        self.thread_executor = ThreadPoolExecutor(self.settings.CPU_COUNT)
        self.prepare()
        self.projection: WorldProjection | None = None

    def prepare(self) -> None:
        self.generate_materials()

    def start(self, window: "ProjectWindow") -> None:
        self.projection = WorldProjection(self, window)

    def stop(self) -> None:
        self.thread_executor.shutdown()

    # performance: У numpy есть where, возможно он поможет не обновлять весь мир разом, а только активные ячейки
    def on_update(self, delta_time: int) -> None:
        futures = []
        for _ in []:
            futures.extend()
        for future in as_completed(futures):
            # это нужно для проброса исключения из потока
            future.result()
        self.age += delta_time

    # todo: Удалить этот метод. Он нужен только для тестов на ранних этапах разработки.
    def generate_materials(self) -> None:
        world_sphere_radius = max((self.width + self.length + self.height) / 2 / 3, 1)
        index_z, index_y, index_x = np.indices(self.shape)
        point_radius = np.maximum(
            np.sqrt(
                (self.width / 2 - index_x) ** 2 + (self.length / 2 - index_y) ** 2 + (self.height / 2 - index_z) ** 2
            ),
            1
        )
        mask = point_radius <= world_sphere_radius

        quantities = (1000 * (world_sphere_radius - point_radius) // world_sphere_radius).astype(np.uint16)
        self.quantities[mask, 0] = quantities[mask]

        relative_radius = point_radius / world_sphere_radius
        conditions = (
            relative_radius < 0.2,
            (relative_radius >= 0.2) & (relative_radius < 0.4),
            (relative_radius >= 0.4) & (relative_radius < 0.6),
            (relative_radius >= 0.6) & (relative_radius < 0.8),
            relative_radius >= 0.8
        )
        substance_ids = np.select(
            conditions,
            Substance.indexes[:5]
        )
        self.substances[mask, 0] = substance_ids[mask]
