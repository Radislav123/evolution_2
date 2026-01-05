import datetime
import os
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generator

import arcade
import numpy as np
import pyglet.gl as gl
from arcade.types import PointList, RGBA255

from core.service.colors import ProjectColors
from core.service.object import Object, ShapeObject
from simulator.material import Materials, Vacuum, Water


# todo: remove class?
class Coordinates:
    # Отображение точки в трехмерном пространстве на двумерное
    @staticmethod
    def convert_3_to_2(a: float, b: float, c: float) -> tuple[float, float]:
        x = a + b / 4
        y = c + b / 3
        return x, y


class Face(ShapeObject):
    default_mode = gl.GL_TRIANGLE_STRIP

    def __init__(
            self,
            points: PointList,
            offset_x: float = 0,
            offset_y: float = 0,
            color: RGBA255 = None,
            copying: bool = False
    ) -> None:
        if not copying:
            points = self.triangulate(points)
        super().__init__(points, offset_x, offset_y, color, copying)


# Подразумевается не ребро, а ребра грани, то есть четыре ребра.
# Называется не FaceEdges в угоду краткости.
class Edge(ShapeObject):
    default_mode = gl.GL_LINE_STRIP

    def __init__(
            self,
            points: PointList,
            offset_x: float = 0,
            offset_y: float = 0,
            color: RGBA255 = None,
            copying: bool = False
    ) -> None:
        if not copying:
            points = list(points)
            points.append(points[0])
        super().__init__(points, offset_x, offset_y, color, copying)


# служит только как хранилище
class Voxel:
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


class WorldProjection(Object):
    def __init__(self, world: World) -> None:
        super().__init__()
        self.world = world
        self.center_x, self.center_y = Coordinates.convert_3_to_2(*self.world.center)

        # Видимость тайлов
        self.visibles = np.array([True for _ in range(self.world.material.size)]).reshape(self.world.shape)
        # В каждой ячейке лежит цвет соответствующего тайла
        # (r, g, b, a)
        self.colors = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        # Порядок добавления важен, так как от него зависит порядок отрисовки, а значит и то,
        # что будет нарисовано на переднем, а что на фоне
        self.colors_to_update: dict[tuple[int, int, int], None] = {point: None for point in self.world.iterate()}
        self.faces_to_update: dict[tuple[int, int, int], None] = {}

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
            self.faces_to_update[coordinates] = None

        default_faces: list[Face] = []
        default_edges: list[Edge] = []
        for face_index, face_vertices in enumerate(voxels_vertices):
            if self.calculate_faces:
                face = Face(face_vertices)
                default_faces.append(face)
            if self.calculate_edges:
                edge = Edge(face_vertices)
                default_edges.append(edge)

        for a, b, c in self.faces_to_update:
            voxel_offset_x, voxel_offset_y = Coordinates.convert_3_to_2(a, b, c)
            voxel_faces = []
            voxel_edges = []

            for face_index, face_vertices in enumerate(voxels_vertices):
                is_visible = face_index in self.visible_faces()
                if self.calculate_faces and is_visible:
                    face_color = self.colors[a, b, c] if is_visible else ProjectColors.NOT_VISIBLE_FACE_COLOR
                    face = default_faces[face_index].copy(voxel_offset_x, voxel_offset_y, face_color)
                    voxel_faces.append(face)
                if self.calculate_edges:
                    edges_color = ProjectColors.VISIBLE_EDGE_COLOR if is_visible else ProjectColors.NOT_VISIBLE_EDGE_COLOR
                    edge = default_edges[face_index].copy(voxel_offset_x, voxel_offset_y, edges_color)
                    voxel_edges.append(edge)

            for face in voxel_faces:
                faces_set.append(face)
            faces[a, b, c] = voxel_faces
            for edge in voxel_edges:
                edges_set.append(edge)
            edges[a, b, c] = voxel_edges

        self.colors_to_update.clear()
        self.faces_to_update.clear()

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
        alpha = round(sum(material.color[3] * amount for material, amount in materials.items()) / total_amount)
        # noinspection PyTypeChecker
        return *rgb, alpha

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
    def __init__(self, shape: tuple[int, int, int], seed: int = None) -> None:
        super().__init__()
        self.shape = shape
        self.width, self.length, self.height = self.shape
        assert self.width > 0 and self.length > 0 and self.height > 0, "World width, length and height must be greater then zero"

        if self.width == 1:
            self.min_x = 0
        else:
            self.min_x = -self.width // 2
        if self.length == 1:
            self.min_y = 0
        else:
            self.min_y = -self.length // 2
        if self.height == 1:
            self.min_z = 0
        else:
            self.min_z = -self.height // 2

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
            point_radius = (x ** 2 + y ** 2 + z ** 2) ** (1 / 2)
            if point_radius <= world_sphere_radius:
                self.material[x, y, z][Water] = round(
                    self.max_material_amount * point_radius / world_sphere_radius
                )

        for x, y, z in self.iterate():
            materials: Materials = self.material[x, y, z]
            total_amount = sum(amount for amount in materials.values())
            assert total_amount <= self.max_material_amount, f"Total amount of materials in tile ({total_amount}) must be lower or equal to max_material_amount ({self.max_material_amount})"
            if total_amount < self.max_material_amount:
                materials[Vacuum] = self.max_material_amount - total_amount
