import ctypes
import datetime
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from pyglet import gl
from pyglet.graphics.shader import ComputeShaderProgram, Shader, ShaderProgram

from core.service.colors import ProjectColors
from core.service.functions import load_shader, write_uniforms
from core.service.object import PhysicalObject, ProjectionObject
from simulator.substance import Substance


if TYPE_CHECKING:
    from simulator.window import ProjectWindow

CellIterator = npt.NDArray[np.int32]

OpenGLIds = tuple[ctypes.c_uint, ...]
OpenGLHandles = npt.NDArray[np.uint64]


class CameraBuffer(ctypes.Structure):
    gl_id = gl.GLuint()
    _fields_ = [
        ("u_view_position", gl.GLfloat * 3),
        ("u_padding_1", gl.GLint),
        ("u_view_forward", gl.GLfloat * 3),
        ("u_padding_2", gl.GLint),
        ("u_view_right", gl.GLfloat * 3),
        ("u_padding_3", gl.GLint),
        ("u_view_up", gl.GLfloat * 3),
        ("u_zoom", gl.GLfloat),
        # Всегда дополнять до кратности 16 байт
        # ("u_padding_0", gl.GLint * 0)
    ]


class PhysicsBuffer(ctypes.Structure):
    gl_id = gl.GLuint()
    _fields_ = [
        ("u_world_age", gl.GLuint),
        # Всегда дополнять до кратности 16 байт
        ("u_padding_0", gl.GLint * 3)
    ]


class WorldProjection(ProjectionObject):
    def __init__(self, world: World) -> None:
        super().__init__()

        self.world = world
        self.window = self.world.window
        self.ctx = self.window.ctx

        self.program = ShaderProgram(
            Shader(
                load_shader(f"{self.settings.SHADERS}/projectional/vertex.glsl"),
                "vertex"
            ),
            Shader(
                load_shader(
                    f"{self.settings.SHADERS}/projectional/fragment.glsl",
                    {
                        "color_function_path": (
                            f"{self.settings.SHADERS}/projectional/functions/get_cell_color/{"default" if not self.settings.TEST_COLOR_CUBE else "test_color_cube"}.glsl",
                            {}
                        )
                    },
                    {
                        "cell_size_d": self.settings.CELL_SHAPE_D
                    }
                ),
                "fragment"
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

            "u_background": (ProjectColors.to_opengl(self.settings.WINDOW_BACKGROUND_COLOR), True, True),
            "u_optical_density_scale": (self.settings.OPTICAL_DENSITY_SCALE, False, False),

            "u_test_color_cube_start": (self.settings.TEST_COLOR_CUBE_START, False, False),
            "u_test_color_cube_end": (self.settings.TEST_COLOR_CUBE_END, False, False)
        }
        write_uniforms(self.program, uniforms)

        self.camera_buffer = CameraBuffer()
        self.init_camera_buffer()

        self.scene_vertices = self.program.vertex_list(
            4,
            gl.GL_TRIANGLE_STRIP,
            in_vertex_position = ('f', (-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0))
        )
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

        write_uniforms(self.program, {"u_colors": (0, False, False)})

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

        write_uniforms(self.program, {"u_absorption": (1, False, False)})

    def init_camera_buffer(self) -> None:
        gl.glCreateBuffers(1, ctypes.byref(self.camera_buffer.gl_id))
        gl.glNamedBufferStorage(
            self.camera_buffer.gl_id,
            ctypes.sizeof(self.camera_buffer),
            ctypes.byref(self.camera_buffer),
            gl.GL_DYNAMIC_STORAGE_BIT
        )

        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 3, self.camera_buffer.gl_id)

    def start(self) -> None:
        pass

    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            self.program.use()

            if self.window.projector.changed:
                self.camera_buffer.u_view_position = self.window.projector.view.position
                self.camera_buffer.u_view_forward = self.window.projector.view.forward
                self.camera_buffer.u_view_right = self.window.projector.view.right
                self.camera_buffer.u_view_up = self.window.projector.view.up
                self.camera_buffer.u_zoom = self.window.projector.view.zoom
                gl.glNamedBufferSubData(
                    self.camera_buffer.gl_id,
                    0,
                    ctypes.sizeof(self.camera_buffer),
                    ctypes.byref(self.camera_buffer)
                )
                self.window.projector.changed = False

            self.scene_vertices.draw(gl.GL_TRIANGLE_STRIP)


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
        self.cell_shape = self.settings.CELL_SHAPE
        self.unit_shape = self.settings.WORLD_UNIT_SHAPE
        self.width, self.length, self.height = self.shape
        self.center = self.shape // 2

        self.iterator: CellIterator = np.stack(
            np.indices(self.shape[::-1])[::-1],
            axis = -1,
            dtype = np.int32
        ).reshape(-1, 3)

        self.cell_count = self.width * self.length * self.height
        self.subcell_in_cell_count = self.cell_shape.x * self.cell_shape.y * self.cell_shape.z
        self.subcell_count = self.cell_count * self.subcell_in_cell_count
        # todo: Генерировать мир тоже на gpu
        self.substances = np.zeros(self.unit_shape, dtype = np.uint16)
        self.quantities = np.zeros(self.unit_shape, dtype = np.uint16)

        self.physics_shader = ComputeShaderProgram(
            load_shader(
                f"{self.settings.SHADERS}/physical/compute.glsl",
                None,
                {
                    "cell_size_d": self.settings.CELL_SHAPE_D
                }
            )
        )
        self.physics_buffer = PhysicsBuffer()
        self.init_physics_buffer()

        # ((texture_ids, handles_read_buffer_id, handles_write_buffer_id), (texture_ids, handles_read_buffer_id, handles_write_buffer_id))
        self.texture_infos = (self.init_textures(), self.init_textures())
        # True - нулевая для чтения, первая для записи
        # False - первая для чтения, нулевая для записи
        self.texture_state = True
        self.bind_textures()

        uniforms = {
            # todo: вернуть True, True?
            "u_world_update_period": (self.settings.WORLD_UPDATE_PERIOD, False, False),

            "u_world_unit_shape": (self.unit_shape, True, True),
            # todo: вернуть True, True?
            "u_gravity_vector": (self.settings.GRAVITY_VECTOR, False, False)
        }
        write_uniforms(self.physics_shader, uniforms)

        self.thread_executor = ThreadPoolExecutor(self.settings.CPU_COUNT)
        self.prepare()
        self.projection: WorldProjection | None = None

        self.textures_writen = False

    def init_physics_buffer(self) -> None:
        gl.glCreateBuffers(1, ctypes.byref(self.physics_buffer.gl_id))
        gl.glNamedBufferStorage(
            self.physics_buffer.gl_id,
            ctypes.sizeof(self.physics_buffer),
            ctypes.byref(self.physics_buffer),
            gl.GL_DYNAMIC_STORAGE_BIT
        )

        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 2, self.physics_buffer.gl_id)

    # performance: Писать  данные через прокладку в виде Pixel Buffer Object (PBO)?
    def init_textures(self) -> tuple[OpenGLIds, ctypes.c_uint, ctypes.c_uint]:
        read_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)
        write_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)

        sampler_id = gl.GLuint()
        gl.glGenSamplers(1, sampler_id)

        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)

        texture_ids = (gl.GLuint * self.settings.CHUNK_COUNT)()
        gl.glGenTextures(self.settings.CHUNK_COUNT, texture_ids)

        for index in range(self.settings.CHUNK_COUNT):
            texture_id = texture_ids[index]
            gl.glBindTexture(gl.GL_TEXTURE_3D, texture_id)

            gl.glTexStorage3D(
                gl.GL_TEXTURE_3D,
                3,
                gl.GL_RGBA32UI,
                self.unit_shape.x,
                self.unit_shape.y,
                self.unit_shape.z
            )
            read_handle = gl.glGetTextureSamplerHandleARB(texture_id, sampler_id)
            gl.glMakeTextureHandleResidentARB(read_handle)
            read_handles[index] = read_handle

            write_handle = gl.glGetImageHandleARB(texture_id, 0, gl.GL_TRUE, 0, gl.GL_RGBA32UI)
            # Возможно, потребуется заменить GL_WRITE_ONLY на GL_READ_WRITE
            gl.glMakeImageHandleResidentARB(write_handle, gl.GL_WRITE_ONLY)
            write_handles[index] = write_handle

        buffer_ids = (gl.GLuint * 2)()
        gl.glCreateBuffers(2, buffer_ids)

        read_buffer_id = buffer_ids[0]
        gl.glNamedBufferStorage(
            read_buffer_id,
            read_handles.nbytes,
            read_handles.ctypes.data,
            gl.GL_DYNAMIC_STORAGE_BIT
        )

        write_buffer_id = buffer_ids[1]
        gl.glNamedBufferStorage(
            write_buffer_id,
            write_handles.nbytes,
            write_handles.ctypes.data,
            gl.GL_DYNAMIC_STORAGE_BIT
        )

        return tuple(texture_ids), read_buffer_id, write_buffer_id

    def prepare(self) -> None:
        self.generate_sphere()

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

        chunk_index = 0

        packed_world = np.empty((*self.unit_shape, 4), dtype = np.uint32)
        # todo: Добавить проверку (assert), что веществ меньше чем 2**15
        # todo: Добавить проверку в шейдере, что количество никогда не превосходит 2**15
        packed_world[..., 0] = (self.substances[...].astype(np.uint32)
                                | (self.quantities[...].astype(np.uint32) << 15))
        zero_offset = 2 ** (10 - 1)
        packed_world[..., 1] = (np.uint32(zero_offset)
                                | (np.uint32(zero_offset) << 10)
                                | (np.uint32(zero_offset) << 20))

        gl.glTextureSubImage3D(
            write_ids[chunk_index],
            0,
            0,
            0,
            0,
            self.unit_shape.x,
            self.unit_shape.y,
            self.unit_shape.z,
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

        self.texture_state = not self.texture_state

    def compute_creatures(self) -> None:
        # gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        pass

    def compute_physics(self) -> None:
        self.physics_shader.use()

        gl.glDispatchCompute(*self.settings.WORLD_SHAPE)
        gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)

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

        # todo: move to start or init?
        if not self.textures_writen:
            self.write_textures()

        self.physics_buffer.u_world_age = self.age
        gl.glNamedBufferSubData(
            self.physics_buffer.gl_id,
            0,
            ctypes.sizeof(self.physics_buffer),
            ctypes.byref(self.physics_buffer)
        )

        self.compute_creatures()
        self.compute_physics()

        self.age += self.settings.WORLD_UPDATE_PERIOD
        self.bind_textures()

    # todo: Удалить этот метод. Он нужен только для тестов на ранних этапах разработки.
    def generate_sphere(self, radius: float = None) -> None:
        if radius is None:
            radius = max(sum(self.unit_shape) / 2 / 3, 1)
        index_z, index_y, index_x = np.indices(self.unit_shape)
        in_center = True
        if in_center:
            point_radius = np.maximum(
                np.sqrt(
                    (self.unit_shape.x / 2 - index_x) ** 2
                    + (self.unit_shape.y / 2 - index_y) ** 2
                    + (self.unit_shape.z / 2 - index_z) ** 2
                ),
                1
            )
        else:
            point_radius = np.maximum(np.sqrt(index_x ** 2 + index_y ** 2 + index_z ** 2), 1)
        mask = point_radius <= radius

        quantities = (1000 * (radius - point_radius) // radius).astype(np.uint16)
        self.quantities[mask] = quantities[mask]

        relative_radius = point_radius / radius
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
        self.substances[mask] = substance_ids[mask]

        # self.substances[:] = 3
        # self.quantities[:] = 50
        # self.substances[:] = 0
        # self.quantities[:] = 0
        # self.substances[*(self.center * self.cell_shape)] = 1
        # self.quantities[*(self.center * self.cell_shape)] = 1000
