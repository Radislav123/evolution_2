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
    substance_texture_ids: OpenGLIds
    quantity_texture_ids: OpenGLIds

    substance_pbo_ids: OpenGLIds
    quantity_pbo_ids: OpenGLIds

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

        self.substance_texture_ids, self.substance_pbo_ids = self.init_world_textures(0)
        self.quantity_texture_ids, self.quantity_pbo_ids = self.init_world_textures(1)

        self.program["u_window_size"] = self.window.size
        self.program["u_fov_scale"] = self.window.projector.projection.fov_scale
        self.program["u_near"] = self.window.projector.projection.near
        self.program["u_far"] = self.window.projector.projection.far
        self.program["u_world_shape"] = self.world.shape
        self.program["u_connected_texture_count"] = self.connected_texture_count

        # noinspection PyTypeChecker
        self.program["u_background"] = tuple(component / 255 for component in self.window.background_color)
        self.program["u_optical_density_scale"] = self.settings.OPTICAL_DENSITY_SCALE

        self.program["u_test_color_cube"] = self.settings.TEST_COLOR_CUBE
        self.program["u_test_color_cube_start"] = self.settings.TEST_COLOR_CUBE_START
        self.program["u_test_color_cube_end"] = self.settings.TEST_COLOR_CUBE_END

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
    def init_world_textures(self, binding_index: int) -> tuple[OpenGLIds, OpenGLIds]:
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

        pbo_ids = (pyglet.gl.GLuint * self.connected_texture_count)()
        pyglet.gl.glGenBuffers(self.connected_texture_count, pbo_ids)

        for index in range(self.connected_texture_count):
            texture_id = texture_ids[index]
            pbo_id = pbo_ids[index]

            pyglet.gl.glBindTexture(pyglet.gl.GL_TEXTURE_3D, texture_id)

            pyglet.gl.glTexStorage3D(
                pyglet.gl.GL_TEXTURE_3D,
                1,
                pyglet.gl.GL_RGBA16UI,
                self.world.width,
                self.world.length,
                self.world.height
            )
            handle = pyglet.gl.glGetTextureSamplerHandleARB(texture_id, sampler_id)
            pyglet.gl.glMakeTextureHandleResidentARB(ctypes.c_uint64(handle))
            handles[index] = handle

            # В байтах
            pbo_size = self.voxel_count * 8
            pyglet.gl.glBindBuffer(pyglet.gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
            pyglet.gl.glBufferData(pyglet.gl.GL_PIXEL_UNPACK_BUFFER, pbo_size, None, pyglet.gl.GL_STREAM_DRAW)
            pyglet.gl.glBindBuffer(pyglet.gl.GL_PIXEL_UNPACK_BUFFER, 0)

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

        return tuple(texture_ids), tuple(pbo_ids)

    def update_world_textures(self) -> None:
        for index in range(self.connected_texture_count):
            texture_id = self.substance_texture_ids[index]
            start = index * 4
            end = (index + 1) * 4

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
                np.ascontiguousarray(self.world.substances[..., start:end]).ctypes.data
            )

        for index in range(self.connected_texture_count):
            texture_id = self.quantity_texture_ids[index]
            start = index * 4
            end = (index + 1) * 4

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
                np.ascontiguousarray(self.world.quantities[..., start:end]).ctypes.data
            )

        self.need_update = False

    # todo: remove method?
    def update_world_textures_1(self) -> None:
        for index in range(self.connected_texture_count):
            texture_id = self.substance_texture_ids[index]
            pbo_id = self.substance_pbo_ids[index]

            pyglet.gl.glBindBuffer(pyglet.gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
            ptr = pyglet.gl.glMapBufferRange(
                pyglet.gl.GL_PIXEL_UNPACK_BUFFER, 0, self.world.substances.nbytes,
                pyglet.gl.GL_MAP_WRITE_BIT | pyglet.gl.GL_MAP_INVALIDATE_BUFFER_BIT
            )

            ctypes.memmove(ptr, self.world.substances.ctypes.data, self.world.substances.nbytes)
            pyglet.gl.glUnmapBuffer(pyglet.gl.GL_PIXEL_UNPACK_BUFFER)
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
                0
            )

        for index in range(self.connected_texture_count):
            texture_id = self.quantity_texture_ids[index]
            pbo_id = self.quantity_pbo_ids[index]

            pyglet.gl.glBindBuffer(pyglet.gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
            ptr = pyglet.gl.glMapBufferRange(
                pyglet.gl.GL_PIXEL_UNPACK_BUFFER, 0, self.world.quantities.nbytes,
                pyglet.gl.GL_MAP_WRITE_BIT | pyglet.gl.GL_MAP_INVALIDATE_BUFFER_BIT
            )

            ctypes.memmove(ptr, self.world.quantities.ctypes.data, self.world.quantities.nbytes)
            pyglet.gl.glUnmapBuffer(pyglet.gl.GL_PIXEL_UNPACK_BUFFER)
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
                0
            )

        pyglet.gl.glBindBuffer(pyglet.gl.GL_PIXEL_UNPACK_BUFFER, 0)
        self.need_update = False

    def start(self) -> None:
        pass

    # todo: Для ускорения можно перейти на indirect render?
    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            if self.need_update and self.window.frame % self.settings.UPDATE_WORLD_TEXTURE_PERIOD == 0:
                self.update_world_textures()

            self.program["u_view_position"] = self.window.projector.view.position
            self.program["u_view_forward"] = self.window.projector.view.forward
            self.program["u_view_right"] = self.window.projector.view.right
            self.program["u_view_up"] = self.window.projector.view.up
            self.program["u_zoom"] = self.window.projector.view.zoom

            self.scene.render(self.program)


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

    # performance: Numba @njit(parallel=True)
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
