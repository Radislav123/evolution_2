import ctypes
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from pyglet import gl
from pyglet.graphics.shader import ComputeShaderProgram, Shader, ShaderProgram

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

    def init_substance_buffer(self) -> None:
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

        # (
        #   (unit_buffer_id, cell_buffer_id),
        #   (unit_buffer_id, cell_buffer_id)
        # )
        self.buffer_infos = (self.init_world_buffers(), self.init_world_buffers())
        # False - нулевой буфер для чтения, первый буфер для записи
        # True - первый буфер для чтения, нулевой буфер для записи
        self.buffer_state = False
        self.swap_buffers()
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

    def init_substance_buffer(self) -> None:
        buffer_id = gl.GLuint()
        gl.glCreateBuffers(1, buffer_id)
        gl.glNamedBufferStorage(
            buffer_id,
            Substance.physics_data.nbytes,
            Substance.physics_data.ctypes.data,
            0
        )
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 10, buffer_id)

    def init_world_buffers(self) -> ctypes.Array[ctypes.c_uint]:
        buffer_count = 2

        buffer_ids = (gl.GLuint * buffer_count)()
        gl.glCreateBuffers(buffer_count, buffer_ids)

        # Буфер юнитов
        gl.glNamedBufferStorage(
            buffer_ids[0],
            self.cell_count * self.cell_size * 16,
            None,
            gl.GL_DYNAMIC_STORAGE_BIT
        )
        # Буфер ячеек
        gl.glNamedBufferStorage(
            buffer_ids[1],
            self.cell_count * 16,
            None,
            gl.GL_DYNAMIC_STORAGE_BIT
        )

        return buffer_ids

    def prepare(self) -> None:
        self.creation_shader.use()

        gl.glDispatchCompute(*self.settings.WORLD_GROUP_SHAPE)
        gl.glMemoryBarrier(gl.GL_SHADER_STORAGE_BARRIER_BIT)

        self.swap_buffers()

    def start(self) -> None:
        self.projection = WorldProjection(self)

    def stop(self) -> None:
        self.thread_executor.shutdown()

    def swap_buffers(self) -> None:
        read_ids = self.buffer_infos[self.buffer_state]
        write_ids = self.buffer_infos[not self.buffer_state]

        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 0, read_ids[0])
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 1, read_ids[1])
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 2, write_ids[0])
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 3, write_ids[1])

        self.buffer_state = not self.buffer_state

    def compute_creatures(self) -> None:
        pass

    def compute_physics(self) -> None:
        self.stage_0_shader.use()

        gl.glDispatchCompute(*self.settings.WORLD_GROUP_SHAPE)
        gl.glMemoryBarrier(gl.GL_SHADER_STORAGE_BARRIER_BIT)

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
        self.swap_buffers()
