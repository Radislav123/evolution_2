import datetime
import os
import random
from array import array
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generator, TYPE_CHECKING

import numpy as np
from arcade import ArcadeContext, get_window
from arcade.gl import BufferDescription, Geometry
from arcade.types import Point3

from core.service.colors import ProjectColors
from core.service.object import Object, ProjectionObject
from simulator.material import Materials, Vacuum, Water


if TYPE_CHECKING:
    from simulator.window import ProjectWindow


class Voxel(ProjectionObject):
    # Координаты вершин
    vertices = (
        # (x, y, z)
        (0, 0, 0),
        (0, 1, 0),
        (1, 1, 0),
        (1, 0, 0),
        (0, 0, 1),
        (0, 1, 1),
        (1, 1, 1),
        (1, 0, 1)
    )
    # Индексы точек граней
    face_vertex_indexes = (
        # Нижняя
        (0, 1, 2, 3),
        # Передняя
        (3, 7, 4, 0),
        # Правая
        (2, 6, 7, 3),
        # Задняя
        (1, 5, 6, 2),
        # Левая
        (0, 4, 5, 1),
        # Верхняя
        (7, 6, 5, 4)
    )
    # Нормали граней
    face_normals = (
        (0, 0, -1),
        (0, -1, 0),
        (1, 0, 0),
        (0, 1, 0),
        (-1, 0, 0),
        (0, 0, 1)
    )
    # Порядок обхода граней
    face_order = (0, 1, 2, 3, 4, 5)
    # Разбиение четырехугольника на треугольники
    triangles = (
        0, 1, 2,
        0, 2, 3
    )

    @classmethod
    def generate_geometry(cls, ctx: ArcadeContext, size: Point3 = (1, 1, 1), center: Point3 = (0, 0, 0)) -> Geometry:
        offset = tuple(component / 2 for component in size)

        positions = array(
            'f',
            (center[component_index] + vertex[component_index] - offset[component_index]
             for vertex in
             (cls.vertices[cls.face_vertex_indexes[face_index][face_vertex_index]]
              for face_index in cls.face_order
              for face_vertex_index in cls.triangles)
             for component_index in range(3)
             )
        )

        normals = array(
            'f',
            (cls.face_normals[face_index][component_index]
             for face_index in cls.face_order
             for _ in cls.triangles
             for component_index in range(3))
        )

        return ctx.geometry(
            [
                BufferDescription(ctx.buffer(data = positions), "3f", ["in_position"]),
                BufferDescription(ctx.buffer(data = normals), "3f", ["in_normal"])
            ]
        )


class WorldProjection(Object):
    def __init__(self, world: World) -> None:
        super().__init__()
        # noinspection PyTypeChecker
        self.window: "ProjectWindow" = get_window()
        self.ctx = self.window.ctx
        self.program = self.ctx.load_program(
            vertex_shader = f"{self.settings.SHADERS}/vertex.glsl",
            fragment_shader = f"{self.settings.SHADERS}/fragment.glsl"
        )

        self.world = world

        self.reference_voxel = Voxel.generate_geometry(self.ctx, center = self.world.center)
        # В каждой ячейке лежит цвет соответствующего тайла
        # (r, g, b, a)
        self.colors = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        self.colors_to_update: set[tuple[int, int, int]] = {point for point in self.world.iterate()}

        self.inited = False

    def init(self) -> Any:
        for coordinates in self.colors_to_update:
            x, y, z = coordinates
            self.colors[x, y, z] = self.mix_color(x, y, z)

        positions = array('f', (coordinate for point in self.world.iterate() for coordinate in point))
        positions_vbo = self.ctx.buffer(data = positions)
        self.reference_voxel.append_buffer_description(
            BufferDescription(
                positions_vbo,
                '3f',
                ['in_instance_position'],
                instanced = True
            )
        )

        colors = array('f', (component for point in self.world.iterate() for component in self.colors[*point]))
        colors_vbo = self.ctx.buffer(data = colors)
        self.reference_voxel.append_buffer_description(
            BufferDescription(
                colors_vbo,
                '4f',
                ['in_instance_color'],
                instanced = True
            )
        )

        self.program["u_world_shape_min"] = (self.world.min_x, self.world.min_y, self.world.min_z)
        self.program["u_world_shape_max"] = (self.world.max_x, self.world.max_y, self.world.max_z)

        self.inited = True

    def mix_color(self, x: int, y: int, z: int) -> ProjectColors.OpenGLType:
        materials = self.world.material[x, y, z]
        total_amount = sum(materials.values())
        rgb = (
            round(sum(material.color[index] * amount for material, amount in materials.items()) // total_amount) for
            index in range(3)
        )
        alpha = round(sum(material.color[3] * amount for material, amount in materials.items()) / total_amount)
        color = ProjectColors.to_opengl(*rgb, alpha)
        # todo: remove this
        # color = (
        #     1 - ((x + self.world.width / 2) / self.world.width),
        #     1 - ((y + self.world.length / 2) / self.world.length),
        #     1 - ((z + self.world.height / 2) / self.world.height),
        #     0.3
        # )
        # color = (
        #     ((x + self.world.width / 2) / self.world.width),
        #     ((y + self.world.length / 2) / self.world.length),
        #     ((z + self.world.height / 2) / self.world.height),
        #     0.3
        # )
        temp_1 = 0.8
        if (x, y, z) == (0, 0, -1):
            color = (0.5, 0, 0, temp_1)
        if (x, y, z) == (0, 0, 0):
            color = (0, 0.5, 0, temp_1)
        if (x, y, z) == (0, 0, 1):
            color = (0, 0, 0.5, temp_1)
        return color

    def reset(self) -> None:
        self.inited = False

    def start(self) -> None:
        pass

    # todo: Для ускорения можно перейти на indirect render?
    def draw(self, draw_faces: bool, draw_edges: bool) -> None:
        if not self.inited:
            self.init()

        # todo: remove depth_mask and cull_face changes?
        cull_face = self.ctx.cull_face
        depth_mask = self.ctx.screen.depth_mask
        # self.ctx.screen.depth_mask = False

        projection_matrix = self.window.projector.generate_projection_matrix()
        view_matrix = self.window.projector.generate_view_matrix()
        self.program["u_vp"] = projection_matrix @ view_matrix
        self.program["u_view_position"] = self.window.projector.view.position

        self.reference_voxel.render(self.program, instances = self.world.material.size)

        self.ctx.cull_face = cull_face
        self.ctx.screen.depth_mask = depth_mask


class World(Object):
    def __init__(self, shape: tuple[int, int, int], seed: int = None) -> None:
        super().__init__()
        self.shape = shape
        self.width, self.length, self.height = self.shape
        assert self.width > 0 and self.length > 0 and self.height > 0, "World width, length and height must be greater then zero"

        if self.width == 1:
            self.min_x = 0
        else:
            self.min_x = -(self.width // 2)
        if self.length == 1:
            self.min_y = 0
        else:
            self.min_y = -(self.length // 2)
        if self.height == 1:
            self.min_z = 0
        else:
            self.min_z = -(self.height // 2)

        self.max_x = self.min_x + self.width - 1
        self.max_y = self.min_y + self.length - 1
        self.max_z = self.min_z + self.height - 1

        self.center_x = 0
        self.center_y = 0
        self.center_z = 0
        self.center = (self.center_x, self.center_y, self.center_z)

        if seed is None:
            seed = datetime.datetime.now().timestamp()
        self.seed = seed
        random.seed(self.seed)

        self.age = 0
        self.max_material_amount = 1000

        cells_number = self.width * self.length * self.height
        # В каждой ячейке лежит словарь с веществом и его количеством
        # {material: amount}
        self.material = np.array([defaultdict(int) for _ in range(cells_number)]).reshape(self.shape)

        self.thread_executor = ThreadPoolExecutor(os.cpu_count())
        self.prepare()

        self.projection = WorldProjection(self)

    def start(self) -> None:
        pass

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

    def prepare(self) -> None:
        self.generate_materials()

    def iterate(self) -> Generator[tuple[int, int, int]]:
        return ((x, y, z)
                for z in range(self.min_z, self.max_z + 1)
                for y in range(self.min_y, self.max_y + 1)
                for x in range(self.min_x, self.max_x + 1))

    def generate_materials(self) -> None:
        world_sphere_radius = max((self.width + self.length + self.height) / 2 / 3, 1)
        for x, y, z in self.iterate():
            point_radius = max((x ** 2 + y ** 2 + z ** 2) ** (1 / 2), 1)
            if point_radius <= world_sphere_radius:
                self.material[x, y, z][Water] = round(
                    self.max_material_amount * (world_sphere_radius - point_radius) / world_sphere_radius
                )

        for x, y, z in self.iterate():
            materials: Materials = self.material[x, y, z]
            total_amount = sum(amount for amount in materials.values())
            assert total_amount <= self.max_material_amount, f"Total amount of materials in tile ({total_amount}) must be lower or equal to max_material_amount ({self.max_material_amount})"
            if total_amount < self.max_material_amount:
                materials[Vacuum] = self.max_material_amount - total_amount
