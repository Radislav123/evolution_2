import ctypes
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import numpy as np
from pyglet import gl
from pyglet.graphics.shader import ComputeShaderProgram, Shader, ShaderProgram
from pyglet.math import Vec3

from core.service.colors import ProjectColors
from core.service.glsl import load_shader, write_uniforms
from core.service.object import GLBuffer, PhysicalObject, ProjectionObject
from simulator.substance import Substance


if TYPE_CHECKING:
    from simulator.window import ProjectWindow


class UniformSetError(Exception):
    pass


class CameraBuffer(GLBuffer):
    gl_id = gl.GLuint()
    _fields_ = [
        ("u_view_position", gl.GLfloat * 3),
        ("u_padding_0", gl.GLint),
        ("u_view_forward", gl.GLfloat * 3),
        ("u_padding_1", gl.GLint),
        ("u_view_right", gl.GLfloat * 3),
        ("u_padding_2", gl.GLint),
        ("u_view_up", gl.GLfloat * 3),
        ("u_zoom", gl.GLfloat),
    ]


class PhysicsBuffer(GLBuffer):
    gl_id = gl.GLuint()
    _fields_ = [
        ("u_world_age", gl.GLuint),
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
        self.init_substance_buffer()

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

        self.uniform_buffer = CameraBuffer()
        self.init_uniform_buffer()

        self.scene_vertices = self.program.vertex_list(
            4,
            gl.GL_TRIANGLE_STRIP,
            in_vertex_position = ('f', (-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0))
        )
        self.need_update = True

    @staticmethod
    def init_substance_buffer() -> None:
        buffer_id = gl.GLuint()
        gl.glCreateBuffers(1, buffer_id)
        gl.glNamedBufferStorage(
            buffer_id,
            Substance.optics_data.nbytes,
            Substance.optics_data.ctypes.data,
            0
        )
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 20, buffer_id)

    def init_uniform_buffer(self) -> None:
        gl.glCreateBuffers(1, self.uniform_buffer.gl_id)
        gl.glNamedBufferStorage(
            self.uniform_buffer.gl_id,
            ctypes.sizeof(self.uniform_buffer),
            ctypes.byref(self.uniform_buffer),
            gl.GL_DYNAMIC_STORAGE_BIT
        )

        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 3, self.uniform_buffer.gl_id)

    def start(self) -> None:
        pass

    def on_draw(self, draw_voxels: bool) -> None:
        if draw_voxels:
            self.program.use()

            if self.window.projector.changed:
                self.uniform_buffer.u_view_position = self.window.projector.view.position
                self.uniform_buffer.u_view_forward = self.window.projector.view.forward
                self.uniform_buffer.u_view_right = self.window.projector.view.right
                self.uniform_buffer.u_view_up = self.window.projector.view.up
                self.uniform_buffer.u_zoom = self.window.projector.view.zoom
                gl.glNamedBufferSubData(
                    self.uniform_buffer.gl_id,
                    0,
                    ctypes.sizeof(self.uniform_buffer),
                    ctypes.byref(self.uniform_buffer)
                )
                self.window.projector.changed = False

            self.scene_vertices.draw(gl.GL_TRIANGLE_STRIP)


class World(PhysicalObject):
    def __init__(self, window: "ProjectWindow") -> None:
        super().__init__()
        self.seed = self.settings.WORLD_SEED
        random.seed(self.seed)
        self.age = 0

        self.window = window
        self.ctx = self.window.ctx

        self.shape = self.settings.WORLD_SHAPE
        self.width, self.length, self.height = self.shape
        self.center = self.shape // 2
        self.cell_count = self.settings.CELL_COUNT
        self.cell_size = self.settings.CELL_SIZE

        self.creation_shader = ComputeShaderProgram(load_shader(f"{self.settings.PHYSICAL_SHADERS}/creation.glsl"))
        self.stage_0_shader = ComputeShaderProgram(load_shader(f"{self.settings.PHYSICAL_SHADERS}/stage_0.glsl"))
        self.uniform_buffer = PhysicsBuffer()
        self.init_uniform_buffer()

        self.texture_infos = (self.init_textures(), self.init_textures())
        self.texture_state = False
        self.swap_textures()
        self.init_substance_buffer()

        uniforms = {
            "u_world_update_period": (self.settings.WORLD_UPDATE_PERIOD, True, True),

            "u_gravity_vector": (self.settings.GRAVITY_VECTOR, True, True)
        }
        write_uniforms(self.stage_0_shader, uniforms)

        self.thread_executor = ThreadPoolExecutor(self.settings.CPU_COUNT)
        self.prepare()
        self.projection: WorldProjection | None = None

    def init_uniform_buffer(self) -> None:
        gl.glCreateBuffers(1, self.uniform_buffer.gl_id)
        gl.glNamedBufferStorage(
            self.uniform_buffer.gl_id,
            ctypes.sizeof(self.uniform_buffer),
            ctypes.byref(self.uniform_buffer),
            gl.GL_DYNAMIC_STORAGE_BIT
        )

        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, 2, self.uniform_buffer.gl_id)

    @staticmethod
    def init_substance_buffer() -> None:
        buffer_id = gl.GLuint()
        gl.glCreateBuffers(1, buffer_id)
        gl.glNamedBufferStorage(
            buffer_id,
            Substance.physics_data.nbytes,
            Substance.physics_data.ctypes.data,
            0
        )
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 10, buffer_id)

    @staticmethod
    def init_texture(sampler_id: int, texture_id: int, shape: Vec3) -> tuple[int, int]:
        gl.glTextureStorage3D(texture_id, 1, gl.GL_RGBA32UI, *shape)

        read_handle = gl.glGetTextureSamplerHandleARB(texture_id, sampler_id)
        gl.glMakeTextureHandleResidentARB(read_handle)

        write_handle = gl.glGetImageHandleARB(texture_id, 0, gl.GL_TRUE, 0, gl.GL_RGBA32UI)
        gl.glMakeImageHandleResidentARB(write_handle, gl.GL_WRITE_ONLY)

        return read_handle, write_handle

    def init_textures(self) -> ctypes.Array[ctypes.c_uint]:
        texture_type_count = 2
        texture_count = self.settings.CHUNK_COUNT * texture_type_count

        read_unit_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)
        read_cell_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)
        write_unit_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)
        write_cell_handles = np.zeros(self.settings.CHUNK_COUNT, dtype = np.uint64)

        sampler_ids = (gl.GLuint * texture_type_count)()
        gl.glCreateSamplers(texture_type_count, sampler_ids)

        for sampler_id in sampler_ids:
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)

        texture_ids = (gl.GLuint * texture_count)()
        gl.glCreateTextures(gl.GL_TEXTURE_3D, texture_count, texture_ids)

        # Юниты
        for index in range(self.settings.CHUNK_COUNT):
            id_offset = self.settings.CHUNK_COUNT * 0
            texture_id = texture_ids[id_offset + index]
            read_handle, write_handle = self.init_texture(
                sampler_ids[0],
                texture_id,
                self.shape * self.settings.CELL_SHAPE
            )
            read_unit_handles[index] = read_handle
            write_unit_handles[index] = write_handle

        # Ячейки
        for index in range(self.settings.CHUNK_COUNT):
            id_offset = self.settings.CHUNK_COUNT * 1
            texture_id = texture_ids[id_offset + index]
            read_handle, write_handle = self.init_texture(
                sampler_ids[1],
                texture_id,
                self.shape
            )
            read_cell_handles[index] = read_handle
            write_cell_handles[index] = write_handle

        all_handles = (
            read_unit_handles,
            write_unit_handles,
            read_cell_handles,
            write_cell_handles
        )
        buffers_count = len(all_handles)
        buffer_ids = (gl.GLuint * buffers_count)()
        gl.glCreateBuffers(buffers_count, buffer_ids)
        for buffer_id, handles in zip(buffer_ids, all_handles):
            gl.glNamedBufferStorage(buffer_id, handles.nbytes, handles.ctypes.data, 0)

        return buffer_ids

    def prepare(self) -> None:
        self.creation_shader.use()

        gl.glDispatchCompute(*self.settings.WORLD_GROUP_SHAPE)
        gl.glMemoryBarrier(gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)

        self.swap_textures()

    def start(self) -> None:
        self.projection = WorldProjection(self)

    def stop(self) -> None:
        self.thread_executor.shutdown()

    def swap_textures(self) -> None:
        read_unit_buffer_id = self.texture_infos[self.texture_state][0]
        write_unit_buffer_id = self.texture_infos[not self.texture_state][1]
        read_cell_buffer_id = self.texture_infos[self.texture_state][2]
        write_cell_buffer_id = self.texture_infos[not self.texture_state][3]

        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 0, read_unit_buffer_id)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 5, write_unit_buffer_id)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 1, read_cell_buffer_id)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 6, write_cell_buffer_id)

        self.texture_state = not self.texture_state

    def compute_creatures(self) -> None:
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

        self.uniform_buffer.u_world_age = self.age
        gl.glNamedBufferSubData(
            self.uniform_buffer.gl_id,
            0,
            ctypes.sizeof(self.uniform_buffer),
            ctypes.byref(self.uniform_buffer)
        )

        self.compute_creatures()
        self.compute_physics()

        self.age += self.settings.WORLD_UPDATE_PERIOD
        self.swap_textures()
