import ctypes
import datetime
import random
import time
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

WorldTextureIds = tuple[ctypes.c_uint, ...]


class WorldProjection(ProjectionObject):
    substance_texture_ids: WorldTextureIds
    quantity_texture_ids: WorldTextureIds

    def __init__(self, world: World, window: "ProjectWindow") -> None:
        super().__init__()
        self.window = window
        self.ctx = self.window.ctx
        self.set_texture_settings()

        self.world = world
        self.voxel_count = self.world.cell_count
        self.iterator: VoxelIterator = self.world.iterator

        self.program = self.ctx.load_program(
            vertex_shader = f"{self.settings.SHADERS}/vertex.glsl",
            fragment_shader = f"{self.settings.SHADERS}/fragment.glsl"
        )
        self.connected_texture_count = self.settings.CELL_SUBSTANCE_COUNT // 4

        self.init_color_texture()
        self.init_absorption_texture()

        self.substance_texture_ids = self.init_world_textures(0)
        self.quantity_texture_ids = self.init_world_textures(1)

        self.program["u_window_size"] = self.window.size
        self.program["u_fov_scale"] = self.window.projector.projection.fov_scale
        self.program["u_near"] = self.window.projector.projection.near
        self.program["u_far"] = self.window.projector.projection.far
        self.program["u_world_shape"] = self.world.shape
        self.program["u_connected_texture_count"] = self.connected_texture_count

        # noinspection PyTypeChecker
        self.program["u_background"] = tuple(component / 255 for component in self.window.background_color)
        self.program["u_optical_density_scale"] = self.settings.OPTICAL_DENSITY_SCALE

        self.program["u_test_color"] = self.settings.TEST_COLOR
        self.program["u_test_color_start"] = self.settings.TEST_COLOR_START
        self.program["u_test_color_end"] = self.settings.TEST_COLOR_END

        self.scene = arcade.gl.geometry.quad_2d_fs()

        self.need_update = True

    @staticmethod
    def set_texture_settings() -> None:
        # performance: Этот параметр замедляет запись и чтение, но убирает необходимость в выравнивании.
        #  Убрать его, но выровнять все передаваемые текстуры по 4 байта?
        #  Перед тем как удалить его из кода, убедиться в том,
        #  что это действительно положительно влияет на производительность.
        pyglet.gl.glPixelStorei(pyglet.gl.GL_UNPACK_ALIGNMENT, 1)

    def init_color_texture(self) -> None:
        texture_id = pyglet.gl.GLuint()
        pyglet.gl.glGenTextures(1, texture_id)
        pyglet.gl.glActiveTexture(pyglet.gl.GL_TEXTURE0)
        pyglet.gl.glBindTexture(pyglet.gl.GL_TEXTURE_1D, texture_id)

        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_1D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_1D, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_1D, pyglet.gl.GL_TEXTURE_WRAP_S, pyglet.gl.GL_CLAMP_TO_EDGE)

        pyglet.gl.glTexStorage1D(
            pyglet.gl.GL_TEXTURE_1D,
            1,
            pyglet.gl.GL_RGBA8,
            Substance.colors.size
        )
        pyglet.gl.glTextureSubImage1D(
            texture_id,
            0,
            0,
            Substance.colors.size,
            pyglet.gl.GL_RGBA,
            pyglet.gl.GL_UNSIGNED_BYTE,
            Substance.colors.ctypes.data
        )
        self.program["u_colors"] = 0

    def init_absorption_texture(self) -> None:
        texture_id = pyglet.gl.GLuint()
        pyglet.gl.glGenTextures(1, texture_id)
        pyglet.gl.glActiveTexture(pyglet.gl.GL_TEXTURE1)
        pyglet.gl.glBindTexture(pyglet.gl.GL_TEXTURE_1D, texture_id)

        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_1D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_1D, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_1D, pyglet.gl.GL_TEXTURE_WRAP_S, pyglet.gl.GL_CLAMP_TO_EDGE)

        pyglet.gl.glTexStorage1D(
            pyglet.gl.GL_TEXTURE_1D,
            1,
            pyglet.gl.GL_R32F,
            Substance.absorptions.size
        )
        pyglet.gl.glTextureSubImage1D(
            texture_id,
            0,
            0,
            Substance.absorptions.size,
            pyglet.gl.GL_RED,
            pyglet.gl.GL_FLOAT,
            Substance.absorptions.ctypes.data
        )
        self.program["u_absorption"] = 1

    # todo: Писать сами данные в текстуру через pyglet.gl.glTextureSubImage3D
    # performance: Писать  данные через прокладку в виде Pixel Buffer Object (PBO)?
    def init_world_textures(self, binding_index: int) -> WorldTextureIds:
        handles = np.zeros(self.connected_texture_count, dtype = np.uint64)

        sampler_id = pyglet.gl.GLuint()
        pyglet.gl.glGenSamplers(1, sampler_id)

        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_WRAP_S, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_WRAP_T, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_WRAP_R, pyglet.gl.GL_CLAMP_TO_EDGE)

        texture_ids = (pyglet.gl.GLuint * self.connected_texture_count)()
        pyglet.gl.glGenTextures(self.connected_texture_count, texture_ids)

        for index, texture_id in enumerate(texture_ids):
            pyglet.gl.glBindTexture(pyglet.gl.GL_TEXTURE_3D, texture_id)

            pyglet.gl.glTexStorage3D(
                pyglet.gl.GL_TEXTURE_3D,
                1,
                pyglet.gl.GL_RGBA16UI,
                self.world.width,
                self.world.length,
                self.world.height
            )
            # noinspection PyTypeChecker
            handle = pyglet.gl.glGetTextureSamplerHandleARB(texture_id, sampler_id)
            pyglet.gl.glMakeTextureHandleResidentARB(ctypes.c_uint64(handle))
            handles[index] = handle

        buffer_id = pyglet.gl.GLuint()
        pyglet.gl.glGenBuffers(1, buffer_id)
        pyglet.gl.glBindBuffer(pyglet.gl.GL_SHADER_STORAGE_BUFFER, buffer_id)

        pyglet.gl.glBufferData(
            pyglet.gl.GL_SHADER_STORAGE_BUFFER,
            handles.nbytes,
            handles.ctypes.data,
            pyglet.gl.GL_DYNAMIC_DRAW
        )
        pyglet.gl.glBindBufferBase(pyglet.gl.GL_SHADER_STORAGE_BUFFER, binding_index, buffer_id)

        return tuple(texture_ids)

    # todo: remove method
    def mix_colors(self) -> None:
        if self.settings.TEST_COLOR:
            index_z, index_y, index_x = np.indices(self.world.shape)
            self.colors[:, :, :, 0] = (index_x / (self.world.shape[2] - 1) * 255).astype(np.uint8)
            self.colors[:, :, :, 1] = (index_y / (self.world.shape[1] - 1) * 255).astype(np.uint8)
            self.colors[:, :, :, 2] = (index_z / (self.world.shape[0] - 1) * 255).astype(np.uint8)
            self.colors[:, :, :, 3] = max(255 // max(self.world.shape), 5)
        else:
            colors = Substance.colors[..., :3][self.world.substances].astype(np.float32)
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

    # performance: PBO (Pixel Buffer Object) - позволяет сделать обновление текстур неблокирующей операцией
    def update_world_textures(self) -> None:
        for index, texture_id in enumerate(self.substance_texture_ids):
            pyglet.gl.glTextureSubImage3D(
                texture_id,
                0,
                0,
                0,
                0,
                self.world.width,
                self.world.length,
                self.world.height,
                pyglet.gl.GL_RGBA_INTEGER,
                pyglet.gl.GL_UNSIGNED_SHORT,
                np.ascontiguousarray(self.world.substances[..., (index * 4):((index + 1) * 4)]).ctypes.data
            )

        for index, texture_id in enumerate(self.quantity_texture_ids):
            pyglet.gl.glTextureSubImage3D(
                texture_id,
                0,
                0,
                0,
                0,
                self.world.width,
                self.world.length,
                self.world.height,
                pyglet.gl.GL_RGBA_INTEGER,
                pyglet.gl.GL_UNSIGNED_SHORT,
                np.ascontiguousarray(self.world.quantities[..., (index * 4):((index + 1) * 4)]).ctypes.data
            )

        self.need_update = False

    def start(self) -> None:
        pass

    # todo: Для ускорения можно перейти на indirect render?
    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            # print("----------------------------------------")
            total = time.time()
            if self.need_update:
                self.update_world_textures()
                # print(f"update texture: {time.time() - total}")

            self.program["u_view_position"] = self.window.projector.view.position
            self.program["u_view_forward"] = self.window.projector.view.forward
            self.program["u_view_right"] = self.window.projector.view.right
            self.program["u_view_up"] = self.window.projector.view.up
            self.program["u_zoom"] = self.window.projector.view.zoom

            temp = time.time()
            self.scene.render(self.program)
            # print(f"render: {time.time() - temp}")
            # print(f"total: {time.time() - total}")
            # self.need_update = True


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
        self.substances = np.zeros((*self.shape, self.settings.CELL_SUBSTANCE_COUNT), dtype = np.uint16)
        self.quantities = np.zeros((*self.shape, self.settings.CELL_SUBSTANCE_COUNT), dtype = np.uint16)

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
        in_center = True
        if in_center:
            point_radius = np.maximum(
                np.sqrt(
                    (self.width / 2 - index_x) ** 2
                    + (self.length / 2 - index_y) ** 2
                    + (self.height / 2 - index_z) ** 2
                ),
                1
            )
        else:
            point_radius = np.maximum(np.sqrt(index_x ** 2 + index_y ** 2 + index_z ** 2), 1)
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
