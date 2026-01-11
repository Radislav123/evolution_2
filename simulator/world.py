import datetime
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import arcade
import numpy as np
import pyglet
from arcade.gl import BufferDescription

from core.service.colors import ProjectColors
from core.service.object import PhysicalObject, ProjectionObject
from simulator.material import Unit


if TYPE_CHECKING:
    from simulator.window import ProjectWindow

CellIterator = np.ndarray[tuple[int, int, int], ...]
VoxelIterator = CellIterator
ColorIterator = np.ndarray[ProjectColors.ArcadeType, ...]


class WorldProjection(ProjectionObject):
    def __init__(self, world: World, window: "ProjectWindow") -> None:
        super().__init__()
        self.window = window
        self.ctx = self.window.ctx

        self.world = world
        self.voxel_count = self.world.cell_count
        self.axis_sort_order: tuple[int, int, int] | None = None
        self.sort_direction: tuple[int, int, int] | None = None

        # Координаты для проекции начинаются с (0, 0, 0),
        # так как это избавляет от необходимости их смещения при работе с графикой
        self.iterator: VoxelIterator = self.world.iterator - self.world.min

        # (r, g, b, a)
        # noinspection PyTypeChecker
        self.colors: ColorIterator = np.zeros((*self.world.shape, 4), dtype = np.uint8)
        # noinspection PyTypeChecker
        self.colors_to_update: set[tuple[int, int, int]] = {tuple(point) for point in self.iterator}

        self.color_texture_id = pyglet.gl.GLuint()
        pyglet.gl.glGenTextures(1, self.color_texture_id)
        pyglet.gl.glBindTexture(pyglet.gl.GL_TEXTURE_3D, self.color_texture_id)

        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_WRAP_S, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_WRAP_T, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glTexParameteri(pyglet.gl.GL_TEXTURE_3D, pyglet.gl.GL_TEXTURE_WRAP_R, pyglet.gl.GL_CLAMP_TO_EDGE)

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
        self.program["u_world_max"] = self.world.max
        self.program["u_world_min"] = self.world.min
        # noinspection PyTypeChecker
        self.program["u_background"] = tuple(component / 255 for component in self.window.background_color)
        self.scene = arcade.gl.geometry.quad_2d_fs()

        self.inited = False

    def start(self) -> None:
        pass

    # todo: Для ускорения можно перейти на indirect render?
    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            for x, y, z in self.colors_to_update:
                self.mix_color(x, y, z)
            self.colors_to_update.clear()

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

    # todo: Сейчас цвет не зависит от количества вещества в вокселе.
    #  Для того, чтобы убрать max_material_amount, нужно учитывать.
    # todo: Возможно, быстрее будет рассчитывать цвет в шейдере?
    #  Но как тогда быть с тем, что в одном вокселе может быть несколько веществ?
    def mix_color(self, x: int, y: int, z: int) -> None:
        if self.settings.COLOR_TEST:
            # Нормализованная позиция
            position = tuple(component / self.world.shape[index] for index, component in enumerate((x, y, z)))
            start_color = ProjectColors.WHITE
            end_color = ProjectColors.BLACK
            rgb = tuple(
                int(start_color[i] * (1 - position[i]) + end_color[i] * position[i])
                for i in range(3)
            )
            alpha = int(255 / max(self.world.shape))
        else:
            materials = self.world.material[x + self.world.min_x, y + self.world.min_y, z + self.world.min_z]
            total_amount = max(sum(materials.values()), 1)
            coeff = 1000
            rgb = (
                sum(material.color[index] * amount for material, amount in materials.items()) // total_amount
                for index in range(3)
            )
            alpha = min(
                sum(material.color[3] * amount for material, amount in materials.items()) * total_amount / coeff // 255,
                255
                )
        self.colors[x, y, z] = (*rgb, alpha)


class World(PhysicalObject):
    def __init__(self) -> None:
        super().__init__()
        self.shape = self.settings.WORLD_SHAPE
        self.width, self.length, self.height = self.shape
        assert self.width > 0 and self.length > 0 and self.height > 0, "World width, length and height must be greater then zero"

        self.min_x = 0 if self.width == 1 else -(self.width // 2)
        self.min_y = 0 if self.length == 1 else -(self.length // 2)
        self.min_z = 0 if self.height == 1 else -(self.height // 2)
        self.min = (self.min_x, self.min_y, self.min_z)

        self.max_x = self.min_x + self.width - 1
        self.max_y = self.min_y + self.length - 1
        self.max_z = self.min_z + self.height - 1
        self.max = (self.max_x, self.max_y, self.max_z)

        self.center_x = 0
        self.center_y = 0
        self.center_z = 0
        self.center = (self.center_x, self.center_y, self.center_z)
        # Если мир очень большой, то хранение такого списка может быть очень дорогим по памяти удовольствием.
        # Но это дает выигрыш в скорости
        self.iterator: CellIterator = (
                np.stack(np.indices(self.shape)[::-1], axis = -1).reshape(-1, 3) + self.min
        ).astype(np.int32)

        self.seed = self.settings.WORLD_SEED
        if self.seed is None:
            self.seed = datetime.datetime.now().timestamp()
        random.seed(self.seed)

        self.age = 0

        self.cell_count = self.width * self.length * self.height
        # В каждой ячейке лежит словарь с веществом и его количеством
        # {material: amount}
        self.material = np.array([defaultdict(int) for _ in range(self.cell_count)]).reshape(self.shape)

        self.thread_executor = ThreadPoolExecutor(self.settings.CPU_COUNT)
        self.prepare()

        self.projection: WorldProjection | None = None

    def prepare(self) -> None:
        self.generate_materials()

    def start(self, window: "ProjectWindow") -> None:
        self.projection = WorldProjection(self, window)

    def stop(self) -> None:
        self.thread_executor.shutdown()

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
        for x, y, z in self.iterator:
            point_radius = max((x ** 2 + y ** 2 + z ** 2) ** (1 / 2), 1)
            if point_radius <= world_sphere_radius:
                self.material[x, y, z][Unit] = round(
                    1000 * (world_sphere_radius - point_radius) / world_sphere_radius
                )
