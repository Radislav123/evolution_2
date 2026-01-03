import datetime
import functools
import itertools
import os
import random
from array import array
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Self

import arcade
import numpy as np
import pyglet.gl as gl
from arcade import ArcadeContext, get_window
from arcade.gl import Buffer, Geometry, Program
from arcade.shape_list import ShapeElementList
from arcade.types import PointList, RGBA255

from core.service.object import Object, ProjectionObject
from simulator.material import Materials, Vacuum, Water


class Coordinates:
    # Отображение точки в трехмерном пространстве на двумерное
    @staticmethod
    @functools.cache
    def convert_3_to_2(a: float, b: float, c: float) -> tuple[float, float]:
        x = a + b / 4
        y = c + b / 3
        return x, y


# См. arcade.shape_list.Shape
class CopyableShape:
    # полностью непрозрачный розовый - для заметности
    default_color: RGBA255 = (239, 64, 245, 255)
    mode: int
    ctx: ArcadeContext
    program: Program

    # Сначала применяется смещение (offset_[x|y]), потом масштаб (scale)
    def __init__(
            self,
            points: PointList,
            offset_x: float = 0,
            offset_y: float = 0,
            color: RGBA255 = default_color,
            copying: bool = False
    ) -> None:
        self.is_copy = False
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.default_points = points
        self.points = [(x + self.offset_x, y + self.offset_y) for x, y in self.default_points]
        self.color = color

        # Pack the data into a single array
        self.data = array("f", (number for point in self.points for obj in (point, self.color) for number in obj))
        self.vertices = len(points)

        self.geometry: Geometry | None = None
        self.buffer: Buffer | None = None

    def __copy__(self) -> Self:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement __copy__. Use copy instead.")

    def __deepcopy__(self, memo) -> Self:
        raise NotImplementedError(f"{self.__class__.__name__} does not implement __deepcopy__. Use copy instead.")

    def draw(self) -> None:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement draw. Not draw in alone. Use ShapeElementList.draw instead."
        )

    @staticmethod
    def triangulate(point_list: PointList) -> PointList:
        half = len(point_list) // 2
        interleaved = itertools.chain.from_iterable(
            itertools.zip_longest(point_list[:half], reversed(point_list[half:]))
        )
        triangulated_point_list = [p for p in interleaved if p is not None]
        return triangulated_point_list

    def copy(self, offset_x: float = None, offset_y: float = None, color: RGBA255 = None) -> Self:
        if offset_x is None:
            offset_x = self.offset_x
        if offset_y is None:
            offset_y = self.offset_y
        if color is None:
            color = self.color

        instance = self.__class__(self.default_points, offset_x, offset_y, color, True)
        return instance


class Face(CopyableShape):
    mode = gl.GL_TRIANGLE_STRIP

    def __init__(
            self,
            points: PointList,
            offset_x: float = 0,
            offset_y: float = 0,
            color: RGBA255 = CopyableShape.default_color,
            copying: bool = False
    ) -> None:
        if not copying:
            points = self.triangulate(points)
        super().__init__(points, offset_x, offset_y, color, copying)


# Подразумевается не ребро, а ребра грани, то есть четыре ребра.
# Называется не FaceEdges в угоду краткости.
class Edge(CopyableShape):
    mode = gl.GL_LINE_STRIP

    def __init__(
            self,
            points: PointList,
            offset_x: float = 0,
            offset_y: float = 0,
            color: RGBA255 = CopyableShape.default_color,
            copying: bool = False
    ) -> None:
        if not copying:
            points = list(points)
            points.append(points[0])
        super().__init__(points, offset_x, offset_y, color, copying)


# служит только как хранилище
class Voxel:
    visible_edge_color = (0, 0, 0, 3)
    not_visible_edge_color = (0, 0, 0, 10)
    not_visible_face_color = (255, 255, 255, 0)
    image_size = 100

    vertices_3 = (
        # (a, b, c)
        (0, 0, 0),
        (0, 1, 0),
        (1, 1, 0),
        (1, 0, 0),
        (0, 0, 1),
        (0, 1, 1),
        (1, 1, 1),
        (1, 0, 1)
    )
    vertices_2 = [Coordinates.convert_3_to_2(*point) for point in vertices_3]
    # индексы точек куба (CUBE_POINTS) для граней
    face_indexes = [
        [0, 4, 7, 3],
        [4, 5, 6, 7],
        [3, 7, 6, 2],
        [0, 4, 5, 1],
        [0, 1, 2, 3],
        [1, 5, 6, 2]
    ]


class WorldProjection(ProjectionObject):
    # todo: remove cache?
    voxels_cache: dict[float, tuple[np.ndarray, ShapeElementList, list[float]]] = {}

    def __init__(self, world: World) -> None:
        # Это было в arcade.shape_list.Shape, но вынесено сюда, чтобы исполняться лишь единожды
        CopyableShape.ctx = get_window().ctx
        CopyableShape.program = CopyableShape.ctx.line_generic_with_colors_program

        super().__init__()
        self.world = world

        # Видимость тайлов
        self.visibles = np.array([True for _ in range(self.world.material.size)]).reshape(self.world.shape)
        # В каждой ячейке лежит цвет соответствующего тайла
        # (r, g, b, a)
        self.colors = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        self.colors_to_update: set[tuple[int, int, int]] = {(a, b, c)
                                                            for a in range(self.world.max_a)
                                                            for b in range(self.world.max_b)
                                                            for c in range(self.world.max_c)}
        self.voxels_to_update: set[tuple[int, int, int]] = set()
        # В каждой ячейке лежит список граней тайла
        self.faces = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        self.faces_set = arcade.shape_list.ShapeElementList()
        self.calculate_faces = False
        self.edges = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        self.edges_set = arcade.shape_list.ShapeElementList()
        self.calculate_edges = False

        self.inited = False

    # todo: добавить определение ближайшей грани для определения того, какой слой ближе к камере,
    #  что нужно для того, чтобы выставлять глубину граням (координату z) для того, чтобы более дальние не перекрывали
    #  более ближние при отображении
    def init(self) -> Any:
        # todo: перейти на перезапись вместо создания новых ndarray?
        # https://stackoverflow.com/questions/31598677/why-list-comprehension-is-much-faster-than-numpy-for-multiplying-arrays
        faces = np.array([lambda: [None] * 6 for _ in range(self.world.material.size)]).reshape(self.world.shape)
        faces_set = arcade.shape_list.ShapeElementList()
        edges = np.array([lambda: [None] * 6 for _ in range(self.world.material.size)]).reshape(self.world.shape)
        edges_set = arcade.shape_list.ShapeElementList()

        # только для видимых граней
        voxels_vertices: list[list[tuple[float, float]]] = []
        for point_indexes in Voxel.face_indexes:
            face_vertices = [Voxel.vertices_2[point_index] for point_index in point_indexes]
            voxels_vertices.append(face_vertices)

        for coordinates in self.colors_to_update:
            a, b, c = coordinates
            self.colors[a, b, c] = self.mix_color(a, b, c)
            self.voxels_to_update.add(coordinates)

        default_faces: list[Face] = []
        default_edges: list[Edge] = []
        for face_index, face_vertices in enumerate(voxels_vertices):
            if self.calculate_faces:
                face = Face(face_vertices)
                default_faces.append(face)
            if self.calculate_edges:
                edge = Edge(face_vertices)
                default_edges.append(edge)

        for a, b, c in self.voxels_to_update:
            voxel_offset_x, voxel_offset_y = Coordinates.convert_3_to_2(a, b, c)
            voxel_faces = []
            voxel_edges = []

            for face_index, face_vertices in enumerate(voxels_vertices):
                is_visible = face_index in self.visible_faces()
                if self.calculate_faces and is_visible:
                    voxel_color = self.colors[a, b, c] if is_visible else Voxel.not_visible_face_color
                    face = default_faces[face_index].copy(voxel_offset_x, voxel_offset_y, voxel_color)
                    voxel_faces.append(face)
                if self.calculate_edges:
                    edges_color = Voxel.visible_edge_color if is_visible else Voxel.not_visible_edge_color
                    edge = default_edges[face_index].copy(voxel_offset_x, voxel_offset_y, edges_color)
                    voxel_edges.append(edge)

            for face in voxel_faces:
                faces_set.append(face)
            faces[a, b, c] = voxel_faces
            for edge in voxel_edges:
                edges_set.append(edge)
            edges[a, b, c] = voxel_edges

        self.faces = faces
        self.faces_set = faces_set
        self.edges = edges
        self.edges_set = edges_set

        self.inited = True

    def mix_color(self, a: int, b: int, c: int) -> tuple[int, int, int, int]:
        materials = self.world.material[a, b, c]
        total_amount = sum(materials.values())
        rgb = (
            round(sum(material.color[index] * amount for material, amount in materials.items()) // total_amount) for
            index in range(3)
        )
        a = round(sum(material.color[3] * amount for material, amount in materials.items()) / total_amount)
        # noinspection PyTypeChecker
        return *rgb, a

    # Возвращает список видимых граней
    def visible_faces(self) -> list[int]:
        return [0, 1, 2]

    # Возвращает список видимых граней
    def not_visible_faces(self) -> list[int]:
        return [3, 4, 5]

    def reset(self) -> None:
        self.inited = False

    def start(self) -> None:
        pass

    def on_draw(self, draw_faces: bool, draw_edges: bool) -> None:
        if self.calculate_faces != draw_faces:
            self.calculate_faces = draw_faces
            self.reset()
        if self.calculate_edges != draw_edges:
            self.calculate_edges = draw_edges
            self.reset()

        if not self.inited:
            self.init()
        if draw_faces:
            self.faces_set.draw()
        if draw_edges:
            self.edges_set.draw()


class World(Object):
    def __init__(
            self,
            width: int,
            height: int,
            depth: int,
            seed: int = None
    ) -> None:
        super().__init__()
        self.max_a = width
        self.max_b = height
        self.max_c = depth

        if seed is None:
            seed = datetime.datetime.now().timestamp()
        self.seed = seed
        random.seed(self.seed)

        self.age = 0
        self.max_material_amount = 1000

        self.center_a = self.max_a // 2
        self.center_b = self.max_b // 2
        self.center_c = self.max_c // 2

        cells_number = self.max_a * self.max_b * self.max_c
        self.shape = (self.max_a, self.max_b, self.max_c)
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

    def generate_materials(self) -> None:
        for a in range(self.max_a):
            for b in range(self.max_b):
                for c in range(self.max_c):
                    a_centered = a - self.center_a
                    b_centered = b - self.center_b
                    c_centered = c - self.center_c
                    world_sphere_radius = (self.center_a + self.center_b + self.center_c) / 3
                    point_radius = (a_centered ** 2 + b_centered ** 2 + c_centered ** 2) ** (1 / 2)
                    if point_radius <= world_sphere_radius:
                        self.material[a, b, c][Water] = round(
                            self.max_material_amount * point_radius / world_sphere_radius
                        )

        for a in range(self.max_a):
            for b in range(self.max_b):
                for c in range(self.max_c):
                    materials: Materials = self.material[a, b, c]
                    total_amount = sum(amount for amount in materials.values())
                    assert total_amount <= self.max_material_amount, f"Total amount of materials in tile ({total_amount}) must be lower or equal to max_material_amount ({self.max_material_amount})"
                    if total_amount < self.max_material_amount:
                        materials[Vacuum] = self.max_material_amount - total_amount
