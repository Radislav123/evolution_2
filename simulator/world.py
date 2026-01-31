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
from core.service.glsl import load_shader, write_uniforms
from core.service.object import PhysicalObject, ProjectionObject
from simulator.substance import Substance


if TYPE_CHECKING:
    from simulator.window import ProjectWindow

CellIterator = npt.NDArray[np.int32]

OpenGLIds = tuple[ctypes.c_uint, ...]
OpenGLHandles = npt.NDArray[np.uint64]


class UniformSetError(Exception):
    pass


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
            Shader(load_shader(f"{self.settings.PROJECTIONAL_SHADERS}/vertex.glsl"), "vertex"),
            Shader(load_shader(f"{self.settings.PROJECTIONAL_SHADERS}/fragment.glsl", ), "fragment")
        )

        self.init_color_texture()
        self.init_absorption_texture()

        uniforms = {
            "u_window_size": (self.window.size, True, True),
            "u_fov_scale": (self.window.projector.projection.fov_scale, True, True),
            "u_near": (self.window.projector.projection.near, True, True),
            "u_far": (self.window.projector.projection.far, True, True),

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

        # todo: remove iterator?
        self.iterator: CellIterator = np.stack(
            np.indices(self.shape[::-1])[::-1],
            axis = -1,
            dtype = np.int32
        ).reshape(-1, 3)

        self.cell_count = self.width * self.length * self.height
        self.subcell_in_cell_count = self.cell_shape.x * self.cell_shape.y * self.cell_shape.z
        self.subcell_count = self.cell_count * self.subcell_in_cell_count

        self.creation_shader = ComputeShaderProgram(load_shader(f"{self.settings.PHYSICAL_SHADERS}/creation.glsl"))
        self.stage_0_shader = ComputeShaderProgram(load_shader(f"{self.settings.PHYSICAL_SHADERS}/stage_0.glsl", ))
        self.physics_buffer = PhysicsBuffer()
        self.init_physics_buffer()

        # (
        #   (texture_ids, handles_read_buffer_id, handles_write_cell_buffer_id, handles_write_block_buffer_id, handles_write_unit_buffer_id),
        #   (texture_ids, handles_read_buffer_id, handles_write_cell_buffer_id, handles_write_block_buffer_id, handles_write_unit_buffer_id),
        # )
        self.texture_infos = (self.init_textures(), self.init_textures())
        # True - нулевая для чтения, первая для записи
        # False - первая для чтения, нулевая для записи
        self.texture_state = True
        self.swap_textures()

        uniforms = {
            # todo: вернуть True, True?
            "u_world_update_period": (self.settings.WORLD_UPDATE_PERIOD, False, False),

            # todo: вернуть True, True?
            "u_gravity_vector": (self.settings.GRAVITY_VECTOR, False, False)
        }
        write_uniforms(self.stage_0_shader, uniforms)

        self.thread_executor = ThreadPoolExecutor(self.settings.CPU_COUNT)
        self.prepare()
        self.projection: WorldProjection | None = None

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
    def init_textures(self) -> tuple[OpenGLIds, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]:
        read_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)
        write_cell_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)
        write_block_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)
        write_unit_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)

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

            write_cell_handle = gl.glGetImageHandleARB(texture_id, 2, gl.GL_TRUE, 0, gl.GL_RGBA32UI)
            gl.glMakeImageHandleResidentARB(write_cell_handle, gl.GL_WRITE_ONLY)
            write_cell_handles[index] = write_cell_handle

            write_block_handle = gl.glGetImageHandleARB(texture_id, 1, gl.GL_TRUE, 0, gl.GL_RGBA32UI)
            gl.glMakeImageHandleResidentARB(write_block_handle, gl.GL_WRITE_ONLY)
            write_block_handles[index] = write_block_handle

            write_unit_handle = gl.glGetImageHandleARB(texture_id, 0, gl.GL_TRUE, 0, gl.GL_RGBA32UI)
            gl.glMakeImageHandleResidentARB(write_unit_handle, gl.GL_WRITE_ONLY)
            write_unit_handles[index] = write_unit_handle

        buffer_ids = (gl.GLuint * 4)()
        gl.glCreateBuffers(4, buffer_ids)

        read_buffer_id = buffer_ids[0]
        gl.glNamedBufferStorage(
            read_buffer_id,
            read_handles.nbytes,
            read_handles.ctypes.data,
            0
        )

        write_cell_buffer_id = buffer_ids[1]
        gl.glNamedBufferStorage(
            write_cell_buffer_id,
            write_cell_handles.nbytes,
            write_cell_handles.ctypes.data,
            0
        )

        write_block_buffer_id = buffer_ids[2]
        gl.glNamedBufferStorage(
            write_block_buffer_id,
            write_block_handles.nbytes,
            write_block_handles.ctypes.data,
            0
        )

        write_unit_buffer_id = buffer_ids[3]
        gl.glNamedBufferStorage(
            write_unit_buffer_id,
            write_unit_handles.nbytes,
            write_unit_handles.ctypes.data,
            0
        )

        return tuple(texture_ids), read_buffer_id, write_cell_buffer_id, write_block_buffer_id, write_unit_buffer_id

    def prepare(self) -> None:
        self.creation_shader.use()

        gl.glDispatchCompute(*self.settings.WORLD_GROUP_SHAPE)
        gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)

        self.swap_textures()

    def start(self) -> None:
        self.projection = WorldProjection(self)

    def stop(self) -> None:
        self.thread_executor.shutdown()

    # Оставлен для будущей реализации сохранения и загрузки мира
    # performance: Писать данные через прокладку в виде Pixel Buffer Object (PBO)?
    def write_textures(self) -> None:
        self.substances = np.zeros(self.unit_shape, dtype = np.uint16)
        self.quantities = np.zeros(self.unit_shape, dtype = np.uint16)
        self.sphere_mask = np.zeros(self.unit_shape, dtype = np.uint16)

        if self.texture_state:
            write_ids = self.texture_infos[1][0]
        else:
            write_ids = self.texture_infos[0][0]
        chunk_index = 0

        packed_units = np.empty((*self.unit_shape, 4), dtype = np.uint32)
        # todo: Добавить проверку (assert), что веществ меньше чем 2**16
        # todo: Добавить проверку в шейдере, что количество никогда не превосходит 2**16
        packed_units[..., 0] = (self.substances.astype(np.uint32)
                                | (self.quantities.astype(np.uint32) << 16))
        zero_offset = 2 ** (10 - 1)
        packed_units[..., 1] = (np.uint32(zero_offset)
                                | (np.uint32(zero_offset) << 10)
                                | (np.uint32(zero_offset) << 20))
        packed_units = np.ascontiguousarray(packed_units.swapaxes(0, 2))

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
            packed_units.ctypes.data
        )

        packed_world_info = np.empty((*self.shape, 4), dtype = np.uint32)
        cells = self.sphere_mask.reshape(self.shape.x, 4, self.shape.y, 4, self.shape.z, 4).transpose(0, 2, 4, 1, 3, 5)
        flat_bits = cells.reshape(-1, 64)
        packed_info = np.packbits(flat_bits, axis = -1, bitorder = "little").view(np.uint32)
        packed_world_info[..., 0] = packed_info[:, 0].reshape(self.shape)
        packed_world_info = np.ascontiguousarray(packed_world_info)

        gl.glTextureSubImage3D(
            write_ids[chunk_index],
            2,
            0,
            0,
            0,
            self.shape.x,
            self.shape.y,
            self.shape.z,
            gl.GL_RGBA_INTEGER,
            gl.GL_UNSIGNED_INT,
            packed_world_info.ctypes.data
        )

    def swap_textures(self) -> None:
        if self.texture_state:
            read_buffer_id = self.texture_infos[0][1]
            write_cell_buffer_id = self.texture_infos[1][2]
            write_block_buffer_id = self.texture_infos[1][3]
            write_unit_buffer_id = self.texture_infos[1][4]
        else:
            read_buffer_id = self.texture_infos[1][1]
            write_cell_buffer_id = self.texture_infos[0][2]
            write_block_buffer_id = self.texture_infos[0][3]
            write_unit_buffer_id = self.texture_infos[0][4]

        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 0, read_buffer_id)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 1, write_cell_buffer_id)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 2, write_block_buffer_id)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 3, write_unit_buffer_id)

        self.texture_state = not self.texture_state

    def compute_creatures(self) -> None:
        # gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        pass

    def compute_physics(self) -> None:
        self.stage_0_shader.use()

        gl.glDispatchCompute(*self.settings.WORLD_GROUP_SHAPE)
        gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)

    def on_update(self) -> None:
        futures = []
        for _ in []:
            futures.extend()
        for future in as_completed(futures):
            # это нужно для проброса исключения из потока
            future.result()

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
        self.swap_textures()
