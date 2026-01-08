import datetime
import os
import random
from array import array
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, TYPE_CHECKING

import numpy as np
from arcade import ArcadeContext
from arcade.gl import BufferDescription, Geometry
from arcade.types import Point3

from core.service.colors import ProjectColors
from core.service.object import Object, ProjectionObject
from core.service.singleton import Singleton
from simulator.material import Materials, Vacuum, Water


if TYPE_CHECKING:
    from simulator.window import ProjectWindow

VoxelIterator = np.ndarray[np.ndarray[np.int32], ...]
ColorIterator = np.ndarray[ProjectColors.ArcadeType, ...]


class Voxel(ProjectionObject, Singleton):
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


# todo: Сделать двойную буферизацию
class WorldProjection(Object):
    def __init__(self, world: World, window: "ProjectWindow") -> None:
        super().__init__()
        self.window = window
        self.ctx = self.window.ctx
        self.program = self.ctx.load_program(
            vertex_shader = f"{self.settings.SHADERS}/vertex.glsl",
            fragment_shader = f"{self.settings.SHADERS}/fragment.glsl"
        )

        self.world = world
        self.voxel_count = self.world.cell_count
        self.axis_sort_order: tuple[int, int, int] | None = None
        self.sort_direction: tuple[int, int, int] | None = None
        self.iterator: VoxelIterator | None = None
        self.update_iterator()
        self.reference_voxel = Voxel.generate_geometry(self.ctx, center = self.world.center)

        self.program["u_world_min"] = self.world.min
        self.program["u_world_max"] = self.world.max

        self.positions_vbo = self.ctx.buffer(reserve = self.voxel_count * 4 * 4, usage = "stream")
        self.colors_vbo = self.ctx.buffer(reserve = self.voxel_count * 4 * 1, usage = "stream")

        self.reference_voxel.append_buffer_description(
            BufferDescription(
                self.positions_vbo,
                "4i",
                ["in_instance_position"],
                instanced = True
            )
        )
        self.reference_voxel.append_buffer_description(
            BufferDescription(
                self.colors_vbo,
                "4f1",
                ["in_instance_color"],
                normalized = ["in_instance_color"],
                instanced = True
            )
        )

        # (r, g, b, a)
        # noinspection PyTypeChecker
        self.colors: ColorIterator = np.zeros((*self.world.shape, 4), dtype = np.uint8)
        self.colors_to_update: set[tuple[int, int, int]] = {(x, y, z) for x, y, z, _ in self.iterator}

        self.inited = False

    def update_buffers(self) -> Any:
        for x, y, z in self.colors_to_update:
            self.mix_color(x, y, z)
        self.colors_to_update.clear()

        positions = np.ascontiguousarray(self.iterator)
        self.positions_vbo.write(positions)

        ordered_colors = self.colors[self.iterator[:, 0], self.iterator[:, 1], self.iterator[:, 2]]
        colors = np.ascontiguousarray(ordered_colors)
        self.colors_vbo.write(colors)

        self.inited = True

    # todo: Возможно, для ускорения расчетов, обновлять цвет только при его ЗНАЧИТЕЛЬНОМ изменении?
    def mix_color(self, x: int, y: int, z: int) -> None:
        color_test = self.settings.COLOR_TEST
        if color_test:
            rgb = (
                int((x + self.world.width / 2) / self.world.width * 255),
                int((y + self.world.length / 2) / self.world.length * 255),
                int((z + self.world.height / 2) / self.world.height * 255)
            )
            alpha = int(255 / max(self.world.shape) ** (1 / 2))
        else:
            materials = self.world.material[x, y, z]
            total_amount = sum(materials.values())
            rgb = (
                round(sum(material.color[index] * amount for material, amount in materials.items()) // total_amount) for
                index in range(3)
            )
            alpha = round(sum(material.color[3] * amount for material, amount in materials.items()) / total_amount)
        self.colors[x, y, z] = (*rgb, alpha)

    def reset(self) -> None:
        self.inited = False

    def start(self) -> None:
        pass

    # todo: Для ускорения можно перейти на indirect render?
    def draw(self, draw_faces: bool, draw_edges: bool) -> None:
        self.update_iterator()
        if not self.inited:
            self.update_buffers()

        projection_matrix = self.window.projector.generate_projection_matrix()
        view_matrix = self.window.projector.generate_view_matrix()
        self.program["u_vp"] = projection_matrix @ view_matrix

        self.reference_voxel.render(self.program, instances = self.voxel_count)

    # todo: добавить кэш или предрасчет
    def update_iterator(self) -> None:
        forward = self.window.projector.view.forward
        axis_sort_order = self.window.projector.view.axis_sort_order
        sort_direction = self.window.projector.view.sort_direction

        # todo: Тормозит на моменте обновления буфера, а не на обновлении итератора
        if self.axis_sort_order != axis_sort_order or self.sort_direction != sort_direction:
            self.axis_sort_order = axis_sort_order
            self.sort_direction = sort_direction

            ranges = {}
            major, middle, minor = axis_sort_order[2], axis_sort_order[1], axis_sort_order[0]
            for i in range(3):
                if forward[i] < 0:
                    # Идем от начала к концу
                    ranges[i] = range(self.world.min[i], self.world.max[i] + 1, 1)
                else:
                    # Идем от конца к началу
                    ranges[i] = range(self.world.max[i], self.world.min[i] - 1, -1)

            grid = np.mgrid[ranges[0], ranges[1], ranges[2]]
            iterator = grid.transpose(major + 1, middle + 1, minor + 1, 0).reshape(-1, 3)
            self.iterator = np.zeros((iterator.shape[0], 4), dtype = np.int32)
            self.iterator[:, :3] = iterator

            self.inited = False


class World(Object):
    def __init__(self, shape: tuple[int, int, int], window: "ProjectWindow", seed: int = None) -> None:
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
        self.min = (self.min_x, self.min_y, self.min_z)

        self.max_x = self.min_x + self.width - 1
        self.max_y = self.min_y + self.length - 1
        self.max_z = self.min_z + self.height - 1
        self.max = (self.max_x, self.max_y, self.max_z)

        self.center_x = 0
        self.center_y = 0
        self.center_z = 0
        self.center = (self.center_x, self.center_y, self.center_z)
        self.iterator: VoxelIterator = tuple(
            (x, y, z)
            for z in range(self.min_z, self.max_z + 1)
            for y in range(self.min_y, self.max_y + 1)
            for x in range(self.min_x, self.max_x + 1)
        )

        if seed is None:
            seed = datetime.datetime.now().timestamp()
        self.seed = seed
        random.seed(self.seed)

        self.age = 0
        self.max_material_amount = 1000

        self.cell_count = self.width * self.length * self.height
        # В каждой ячейке лежит словарь с веществом и его количеством
        # {material: amount}
        self.material = np.array([defaultdict(int) for _ in range(self.cell_count)]).reshape(self.shape)

        self.thread_executor = ThreadPoolExecutor(os.cpu_count())
        self.prepare()

        self.projection = WorldProjection(self, window)

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

    def generate_materials(self) -> None:
        world_sphere_radius = max((self.width + self.length + self.height) / 2 / 3, 1)
        for x, y, z in self.iterator:
            point_radius = max((x ** 2 + y ** 2 + z ** 2) ** (1 / 2), 1)
            if point_radius <= world_sphere_radius:
                self.material[x, y, z][Water] = round(
                    self.max_material_amount * (world_sphere_radius - point_radius) / world_sphere_radius
                )

        for x, y, z in self.iterator:
            materials: Materials = self.material[x, y, z]
            total_amount = sum(amount for amount in materials.values())
            assert total_amount <= self.max_material_amount, f"Total amount of materials in tile ({total_amount}) must be lower or equal to max_material_amount ({self.max_material_amount})"
            if total_amount < self.max_material_amount:
                materials[Vacuum] = self.max_material_amount - total_amount
