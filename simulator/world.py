import ctypes
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

OpenGLIds = tuple[ctypes.c_uint, ...]


class WorldProjection(ProjectionObject):
    def __init__(self, world: World) -> None:
        super().__init__()

        self.world = world
        self.window = self.world.window
        self.ctx = self.window.ctx

        self.voxel_count = self.world.cell_count
        self.iterator: VoxelIterator = self.world.iterator

        self.program = self.ctx.load_program(
            vertex_shader = f"{self.settings.SHADERS}/vertex.glsl",
            fragment_shader = f"{self.settings.SHADERS}/fragment.glsl"
        )

        self.init_color_texture()
        self.init_absorption_texture()

        self.program["u_window_size"] = self.window.size
        self.program["u_fov_scale"] = self.window.projector.projection.fov_scale
        self.program["u_near"] = self.window.projector.projection.near
        self.program["u_far"] = self.window.projector.projection.far
        self.program["u_world_shape"] = self.world.shape
        self.program["u_connected_texture_count"] = self.settings.CONNECTED_TEXTURE_COUNT

        # noinspection PyTypeChecker
        self.program["u_background"] = tuple(component / 255 for component in self.window.background_color)
        self.program["u_optical_density_scale"] = self.settings.OPTICAL_DENSITY_SCALE

        self.program["u_test_color_cube"] = self.settings.TEST_COLOR_CUBE
        self.program["u_test_color_cube_start"] = self.settings.TEST_COLOR_CUBE_START
        self.program["u_test_color_cube_end"] = self.settings.TEST_COLOR_CUBE_END

        self.scene = arcade.gl.geometry.quad_2d_fs()

        self.need_update = True

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

    def start(self) -> None:
        pass

    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            self.program["u_view_position"] = self.window.projector.view.position
            self.program["u_view_forward"] = self.window.projector.view.forward
            self.program["u_view_right"] = self.window.projector.view.right
            self.program["u_view_up"] = self.window.projector.view.up
            self.program["u_zoom"] = self.window.projector.view.zoom

            # todo: Перед отрисовкой ставить барьер pyglet.gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)?
            self.scene.render(self.program)


class World(PhysicalObject):
    def __init__(self, window: "ProjectWindow") -> None:
        super().__init__()
        self.window = window
        self.ctx = self.window.ctx

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
        self.substances = np.zeros((*self.shape, self.settings.CELL_SUBSTANCE_COUNT), dtype = np.uint16)
        self.quantities = np.zeros((*self.shape, self.settings.CELL_SUBSTANCE_COUNT), dtype = np.uint16)

        self.set_texture_settings()
        self.substance_texture_ids = self.init_textures(0)
        self.quantity_texture_ids = self.init_textures(1)
        self.data = (
            (self.substance_texture_ids, self.substances),
            (self.quantity_texture_ids, self.quantities)
        )

        self.seed = self.settings.WORLD_SEED
        if self.seed is None:
            self.seed = datetime.datetime.now().timestamp()
        random.seed(self.seed)
        self.age = 0

        self.thread_executor = ThreadPoolExecutor(self.settings.CPU_COUNT)
        self.prepare()
        self.projection: WorldProjection | None = None

        self.textures_writen = False

    @staticmethod
    def set_texture_settings() -> None:
        # performance: Этот параметр замедляет запись и чтение, но убирает необходимость в выравнивании.
        #  Убрать его, но выровнять все передаваемые текстуры по 4 байта?
        #  Перед тем как удалить его из кода, убедиться в том,
        #  что это действительно положительно влияет на производительность.
        pyglet.gl.glPixelStorei(pyglet.gl.GL_UNPACK_ALIGNMENT, 1)

    # todo: объединить с WorldProjection.init_world_textures
    #  (возможно, создав отдельный класс, для работы с opengl, и включив туда и другие связанные функции)
    # performance: Писать  данные через прокладку в виде Pixel Buffer Object (PBO)?
    def init_textures(self, buffer_index: int) -> OpenGLIds:
        assert buffer_index not in self.settings.BUFFER_INDEXES, f"This index ({buffer_index}) already is in usage"
        self.settings.BUFFER_INDEXES.add(buffer_index)
        texture_count = self.settings.CONNECTED_TEXTURE_COUNT * 2
        handles = np.zeros(texture_count, dtype = np.uint64)

        sampler_id = pyglet.gl.GLuint()
        pyglet.gl.glGenSamplers(1, sampler_id)

        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_MIN_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_MAG_FILTER, pyglet.gl.GL_NEAREST)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_WRAP_S, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_WRAP_T, pyglet.gl.GL_CLAMP_TO_EDGE)
        pyglet.gl.glSamplerParameteri(sampler_id, pyglet.gl.GL_TEXTURE_WRAP_R, pyglet.gl.GL_CLAMP_TO_EDGE)

        texture_ids = (pyglet.gl.GLuint * texture_count)()
        pyglet.gl.glGenTextures(texture_count, texture_ids)

        for index in range(texture_count):
            texture_id = texture_ids[index]
            pyglet.gl.glBindTexture(pyglet.gl.GL_TEXTURE_3D, texture_id)

            pyglet.gl.glTexStorage3D(
                pyglet.gl.GL_TEXTURE_3D,
                1,
                pyglet.gl.GL_RGBA16UI,
                self.width,
                self.length,
                self.height
            )
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
        pyglet.gl.glBindBufferBase(pyglet.gl.GL_SHADER_STORAGE_BUFFER, buffer_index, buffer_id)

        return tuple(texture_ids)

    def prepare(self) -> None:
        self.generate_materials()

    def start(self) -> None:
        self.projection = WorldProjection(self)

    def stop(self) -> None:
        self.thread_executor.shutdown()

    # performance: Писать данные через прокладку в виде Pixel Buffer Object (PBO)?
    def write_textures(self) -> None:
        for texture_ids, data in self.data:
            for index in range(self.settings.CONNECTED_TEXTURE_COUNT):
                start = index * 4
                end = (index + 1) * 4

                pyglet.gl.glTextureSubImage3D(
                    texture_ids[index * 2 + self.age % 2],
                    0,
                    0,
                    0,
                    0,
                    self.width,
                    self.length,
                    self.height,
                    pyglet.gl.GL_RGBA_INTEGER,
                    pyglet.gl.GL_UNSIGNED_SHORT,
                    np.ascontiguousarray(data[..., start:end]).ctypes.data
                )

        self.textures_writen = True

    # todo: Добавить зацикливание мира по xy
    # performance: Numba @njit(parallel=True)
    # performance: У numpy есть where, возможно он поможет не обновлять весь мир разом, а только активные ячейки
    def on_update(self, delta_time: int) -> None:
        if not self.textures_writen:
            self.write_textures()

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
