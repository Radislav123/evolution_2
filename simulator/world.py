import ctypes
import datetime
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import arcade
import numpy as np
import numpy.typing as npt
from arcade.gl import BufferDescription
from pyglet import gl

from core.service.colors import ProjectColors
from core.service.functions import load_shader, write_uniforms
from core.service.object import PhysicalObject, ProjectionObject
from simulator.substance import Substance


if TYPE_CHECKING:
    from simulator.window import ProjectWindow

CellIterator = npt.NDArray[np.int32]
VoxelIterator = CellIterator

OpenGLIds = tuple[ctypes.c_uint, ...]
OpenGLHandles = npt.NDArray[np.uint64]


class WorldProjection(ProjectionObject):
    def __init__(self, world: World) -> None:
        super().__init__()

        self.world = world
        self.window = self.world.window
        self.ctx = self.window.ctx

        self.voxel_count = self.world.cell_count
        self.iterator: VoxelIterator = self.world.iterator

        self.program = self.ctx.program(
            vertex_shader = load_shader(f"{self.settings.SHADERS}/projectional/vertex.glsl"),
            fragment_shader = load_shader(
                f"{self.settings.SHADERS}/projectional/fragment.glsl",
                {
                    "color_function_path": (
                        f"{self.settings.SHADERS}/projectional/functions/get_voxel_color/{"default" if not self.settings.TEST_COLOR_CUBE else "test_color_cube"}.glsl",
                        {}
                    )
                }
            )
        )

        self.init_color_texture()
        self.init_absorption_texture()

        uniforms = {
            "u_window_size": (self.window.size, True, True),
            "u_fov_scale": (self.window.projector.projection.fov_scale, True, True),
            "u_near": (self.window.projector.projection.near, True, True),
            "u_far": (self.window.projector.projection.far, True, True),
            "u_world_shape": (self.world.shape, True, True),
            "u_cell_substance_count": (self.settings.CELL_SUBSTANCE_COUNT, False, False),

            "u_background": (ProjectColors.to_opengl(self.settings.WINDOW_BACKGROUND_COLOR), True, True),
            "u_optical_density_scale": (self.settings.OPTICAL_DENSITY_SCALE, False, False),

            "u_test_color_cube_start": (self.settings.TEST_COLOR_CUBE_START, False, False),
            "u_test_color_cube_end": (self.settings.TEST_COLOR_CUBE_END, False, False)
        }
        write_uniforms(self.program, uniforms)

        self.scene = arcade.gl.geometry.quad_2d_fs()
        self.need_update = True

    def init_color_texture(self) -> None:
        texture_id = gl.GLuint()
        gl.glGenTextures(1, texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_1D, texture_id)

        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)

        gl.glTexStorage1D(
            gl.GL_TEXTURE_1D,
            1,
            gl.GL_RGBA8,
            Substance.colors.size
        )
        gl.glTextureSubImage1D(
            texture_id,
            0,
            0,
            Substance.colors.size,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            Substance.colors.ctypes.data
        )

        self.program.set_uniform_safe("u_colors", 0)

    def init_absorption_texture(self) -> None:
        texture_id = gl.GLuint()
        gl.glGenTextures(1, texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_1D, texture_id)

        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)

        gl.glTexStorage1D(
            gl.GL_TEXTURE_1D,
            1,
            gl.GL_R32F,
            Substance.absorptions.size
        )
        gl.glTextureSubImage1D(
            texture_id,
            0,
            0,
            Substance.absorptions.size,
            gl.GL_RED,
            gl.GL_FLOAT,
            Substance.absorptions.ctypes.data
        )

        self.program.set_uniform_safe("u_absorption", 1)

    def start(self) -> None:
        pass

    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            # performance: обновлять переменные через буфер (записывать их в буфер)
            self.program["u_view_position"] = self.window.projector.view.position
            self.program["u_view_forward"] = self.window.projector.view.forward
            self.program["u_view_right"] = self.window.projector.view.right
            self.program["u_view_up"] = self.window.projector.view.up
            self.program["u_zoom"] = self.window.projector.view.zoom

            # Поставить, если будет неправильное отображение
            # gl.glMemoryBarrier(gl.GL_TEXTURE_FETCH_BARRIER_BIT)
            self.scene.render(self.program)


class World(PhysicalObject):
    def __init__(self, window: "ProjectWindow") -> None:
        super().__init__()
        self.seed = self.settings.WORLD_SEED
        if self.seed is None:
            self.seed = datetime.datetime.now().timestamp()
        random.seed(self.seed)
        self.age = 0

        self.window = window
        self.ctx = self.window.ctx

        self.shape = self.settings.WORLD_SHAPE
        self.width, self.length, self.height = self.shape
        self.center = self.shape // 2

        self.iterator: CellIterator = np.stack(
            np.indices(self.shape[::-1])[::-1],
            axis = -1,
            dtype = np.int32
        ).reshape(-1, 3)

        self.cell_count = self.width * self.length * self.height
        # todo: Генерировать мир тоже на gpu
        self.substances = np.zeros((*self.shape, self.settings.CELL_SUBSTANCE_COUNT), dtype = np.uint16)
        self.quantities = np.zeros((*self.shape, self.settings.CELL_SUBSTANCE_COUNT), dtype = np.uint16)

        self.compute_shader = self.ctx.compute_shader(
            source = load_shader(
                f"{self.settings.SHADERS}/physical/compute.glsl",
                None,
                {
                    "block_size_x": self.settings.COMPUTE_SHADER_BLOCK_SHAPE.x,
                    "block_size_y": self.settings.COMPUTE_SHADER_BLOCK_SHAPE.y,
                    "block_size_z": self.settings.COMPUTE_SHADER_BLOCK_SHAPE.z
                }
            )
        )

        self.set_texture_settings()
        # ((texture_ids, handles_read_buffer_id, handles_write_buffer_id), (texture_ids, handles_read_buffer_id, handles_write_buffer_id))
        self.texture_infos = (self.init_textures(), self.init_textures())
        # True - нулевая для чтения, первая для записи
        # False - первая для чтения, нулевая для записи
        self.texture_state = True
        self.bind_textures()

        uniforms = {
            "u_cell_substance_count": (self.settings.CELL_SUBSTANCE_COUNT, True, True),
            "u_world_update_period": (self.settings.WORLD_UPDATE_PERIOD, True, True),

            "u_world_shape": (self.shape, True, True),
            "u_gravity_vector": (self.settings.GRAVITY_VECTOR, True, True)
        }
        write_uniforms(self.compute_shader, uniforms)

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
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)

    # performance: Писать  данные через прокладку в виде Pixel Buffer Object (PBO)?
    def init_textures(self) -> tuple[OpenGLIds, ctypes.c_uint, ctypes.c_uint]:
        read_handles = np.zeros(self.settings.CELL_SUBSTANCE_COUNT, dtype = np.uint64)
        write_handles = np.zeros(self.settings.CELL_SUBSTANCE_COUNT, dtype = np.uint64)

        sampler_id = gl.GLuint()
        gl.glGenSamplers(1, sampler_id)

        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)

        texture_ids = (gl.GLuint * self.settings.CELL_SUBSTANCE_COUNT)()
        gl.glGenTextures(self.settings.CELL_SUBSTANCE_COUNT, texture_ids)

        for index in range(self.settings.CELL_SUBSTANCE_COUNT):
            texture_id = texture_ids[index]
            gl.glBindTexture(gl.GL_TEXTURE_3D, texture_id)

            gl.glTexStorage3D(
                gl.GL_TEXTURE_3D,
                1,
                gl.GL_RGBA32UI,
                self.width,
                self.length,
                self.height
            )
            read_handle = gl.glGetTextureSamplerHandleARB(texture_id, sampler_id)
            gl.glMakeTextureHandleResidentARB(read_handle)
            read_handles[index] = read_handle

            write_handle = gl.glGetImageHandleARB(texture_id, 0, gl.GL_TRUE, 0, gl.GL_RGBA32UI)
            # Возможно, потребуется заменить GL_WRITE_ONLY на GL_READ_WRITE
            gl.glMakeImageHandleResidentARB(write_handle, gl.GL_WRITE_ONLY)
            write_handles[index] = write_handle

        read_buffer_id = gl.GLuint()
        gl.glGenBuffers(1, read_buffer_id)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, read_buffer_id)
        gl.glBufferData(
            gl.GL_SHADER_STORAGE_BUFFER,
            read_handles.nbytes,
            read_handles.ctypes.data,
            gl.GL_STREAM_DRAW
        )

        write_buffer_id = gl.GLuint()
        gl.glGenBuffers(1, write_buffer_id)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, write_buffer_id)
        gl.glBufferData(
            gl.GL_SHADER_STORAGE_BUFFER,
            write_handles.nbytes,
            write_handles.ctypes.data,
            gl.GL_STREAM_DRAW
        )

        return tuple(texture_ids), read_buffer_id, write_buffer_id

    def prepare(self) -> None:
        self.generate_materials()

    def start(self) -> None:
        self.projection = WorldProjection(self)

    def stop(self) -> None:
        self.thread_executor.shutdown()

    # performance: Писать данные через прокладку в виде Pixel Buffer Object (PBO)?
    def write_textures(self) -> None:
        if self.texture_state:
            write_ids = self.texture_infos[1][0]
        else:
            write_ids = self.texture_infos[0][0]

        for index in range(self.settings.CELL_SUBSTANCE_COUNT):
            packed_world = np.empty((self.height, self.length, self.width, 4), dtype = np.uint32)
            # todo: Добавить проверку (assert), что веществ меньше чем 2**15
            # todo: Добавить проверку в шейдере, что количество никогда не превосходит 2**15
            packed_world[..., 0] = (self.substances[..., index].astype(np.uint32)
                                    | (self.quantities[..., index].astype(np.uint32) << 15))
            zero_offset = 2 ** (10 - 1)
            packed_world[..., 1] = (np.uint32(zero_offset)
                                    | (np.uint32(zero_offset) << 10)
                                    | (np.uint32(zero_offset) << 20))

            gl.glTextureSubImage3D(
                write_ids[index],
                0,
                0,
                0,
                0,
                self.width,
                self.length,
                self.height,
                gl.GL_RGBA_INTEGER,
                gl.GL_UNSIGNED_INT,
                packed_world.ctypes.data
            )

        self.textures_writen = True

    def bind_textures(self) -> None:
        if self.texture_state:
            read_buffer_id = self.texture_infos[0][1]
            write_buffer_id = self.texture_infos[1][2]
        else:
            read_buffer_id = self.texture_infos[1][1]
            write_buffer_id = self.texture_infos[0][2]

        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 0, read_buffer_id)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 1, write_buffer_id)

        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, 0)
        self.texture_state = not self.texture_state

    def compute_creatures(self) -> None:
        pass

    # todo: Добавить зацикливание мира по xy
    # performance: Numba @njit(parallel=True)
    # performance: У numpy есть where, возможно он поможет не обновлять весь мир разом, а только активные ячейки
    def on_update(self) -> None:
        futures = []
        for _ in []:
            futures.extend()
        for future in as_completed(futures):
            # это нужно для проброса исключения из потока
            future.result()

        if not self.textures_writen:
            self.write_textures()
        # self.compute_shader["u_world_age"] = self.age

        gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        self.compute_creatures()

        gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        # todo: заменить run (и render в projection) на самостоятельный вызов opengl,
        #  чтобы самостоятельно управлять барьерами
        self.compute_shader.run(*self.settings.COMPUTE_SHADER_WORK_GROUPS)

        self.age += self.settings.WORLD_UPDATE_PERIOD
        self.bind_textures()

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
            Substance.indexes[1:6]
        )
        self.substances[mask, 0] = substance_ids[mask]
