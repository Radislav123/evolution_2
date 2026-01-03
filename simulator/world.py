import datetime
import functools
import os
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import arcade
import numpy as np
from arcade.shape_list import ShapeElementList

from core.service.color import Color
from core.service.object import Object, ProjectionObject
from simulator.material import Materials, Vacuum, Water


class Coordinates:
    # Отображение точки в трехмерном пространстве на двумерное
    @staticmethod
    @functools.cache
    def convert_3_to_2(a: float, b: float, c: float, coeff: float = 1) -> tuple[float, float]:
        x = (a + b / 4) * coeff
        y = (c + b / 3) * coeff
        return x, y


# служит только как хранилище настроек
class Tile:
    visible_edge_color = (0, 0, 0, 3)
    not_visible_edge_color = (0, 0, 0, 10)
    not_visible_face_color = (255, 255, 255, 0)
    default_width = 1
    image_size = 100


class WorldProjection(ProjectionObject):
    # todo: remove cache?
    tiles_cache: dict[float, tuple[np.ndarray, ShapeElementList, list[float]]] = {}
    calculate_edges = True

    def __init__(self, world: World) -> None:
        super().__init__()
        self.world = world

        # соотносится с центром окна
        self.offset_x: int = 0
        self.offset_y: int = 0

        # множитель размера отображения мира
        self.coeff: float = 1
        self.min_coeff = 0.01
        self.max_coeff = 5000
        self.coeff_round_digits = 0

        # Видимость тайлов
        self.visibles = np.array([True for _ in range(self.world.material.size)]).reshape(self.world.shape)
        # В каждой ячейке лежит цвет соответствующего тайла
        # (r, g, b, a)
        self.colors = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        self.colors_to_update: set[tuple[int, int, int]] = {(a, b, c)
                                                            for a in range(self.world.max_a)
                                                            for b in range(self.world.max_b)
                                                            for c in range(self.world.max_c)}
        self.tiles_to_update: set[tuple[int, int, int]] = set()
        # В каждой ячейке лежит список граней тайла
        self.tiles = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        self.tiles_set = arcade.shape_list.ShapeElementList()
        self.edges = np.array([None for _ in range(self.world.material.size)]).reshape(self.world.shape)
        self.edges_set = arcade.shape_list.ShapeElementList()

        self.inited = False
        self.centralize()

    def init(self) -> Any:
        points = (
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
        # обход по граням
        face_indexes = [
            [0, 4, 7, 3],
            [4, 5, 6, 7],
            [3, 7, 6, 2],
            [0, 4, 5, 1],
            [0, 1, 2, 3],
            [1, 5, 6, 2]
        ]
        for coordinates in self.colors_to_update:
            a, b, c = coordinates
            self.colors[a, b, c] = self.mix_color(a, b, c)
            self.tiles_to_update.add(coordinates)

        for a, b, c in self.tiles_to_update:
            pass

        tiles = np.array([lambda: [None] * 6 for _ in range(self.world.material.size)]).reshape(self.world.shape)
        tiles_set = arcade.shape_list.ShapeElementList()
        edges = np.array([lambda: [None] * 6 for _ in range(self.world.material.size)]).reshape(self.world.shape)
        edges_set = arcade.shape_list.ShapeElementList()
        for a in range(self.world.max_a):
            for b in range(self.world.max_b):
                for c in range(self.world.max_c):
                    offset_x, offset_y = Coordinates.convert_3_to_2(a, b, c)
                    # (x, y)
                    tile_points = [Coordinates.convert_3_to_2(*point) for point in points]
                    # coeff and offset
                    tile_points = [
                        (
                            (point[0] + offset_x) * self.coeff,
                            (point[1] + offset_y) * self.coeff
                        ) for point in tile_points
                    ]

                    tile_faces = []
                    tile_edges = []
                    for face_index, point_indexes in enumerate(face_indexes):
                        face_points = [tile_points[point_index] for point_index in point_indexes]

                        is_visible = face_index in self.visible_faces()
                        if self.calculate_edges:
                            edge = arcade.shape_list.create_line_loop(
                                face_points,
                                Tile.visible_edge_color if is_visible else Tile.not_visible_edge_color,
                                Tile.default_width
                            )
                            tile_edges.append(edge)
                            for edge in tile_edges:
                                edges_set.append(edge)
                            edges[a, b, c] = tile_edges

                        if is_visible:
                            face = arcade.shape_list.create_polygon(
                                face_points,
                                self.colors[a, b, c] if is_visible else Tile.not_visible_face_color,
                            )
                            tile_faces.append(face)

                    for face in tile_faces:
                        tiles_set.append(face)
                    tiles[a, b, c] = tile_faces

        self.tiles = tiles
        self.tiles_set = tiles_set
        self.tiles_set.position = (0, 0)
        self.tiles_set.move(self.offset_x, self.offset_y)
        self.edges = edges
        self.edges_set = edges_set
        self.edges_set.position = (0, 0)
        self.edges_set.move(self.offset_x, self.offset_y)

        self.inited = True

    def mix_color(self, a: int, b: int, c: int) -> Color:
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

    def on_draw(self, draw_tiles: bool, draw_edges: bool) -> None:
        if not self.inited:
            self.init()
        if draw_tiles:
            self.tiles_set.draw()
        if draw_edges:
            self.edges_set.draw()

    # todo: вызов данного метода должен перерисовывать карту так, чтобы она целиком помещалась на экране?
    def centralize(self) -> None:
        window = arcade.get_window()
        self.coeff = 25

        offset_x, offset_y = Coordinates.convert_3_to_2(
            self.world.max_a / 2,
            self.world.max_b / 2,
            self.world.max_c / 2
        )
        offset_x = round(window.center_x - offset_x * self.coeff)
        offset_y = round(window.center_y - offset_y * self.coeff)

        self.change_offset(-self.offset_x, -self.offset_y)
        self.change_offset(offset_x, offset_y)

        self.reset()

    def change_coeff(self, position_x: int, position_y: int, offset: int) -> None:
        scroll_coeff = self.max_coeff / 20
        coeff_offset = offset * self.coeff / self.max_coeff * scroll_coeff
        old_coeff = self.coeff
        self.coeff = max(min(self.coeff + coeff_offset, self.max_coeff), self.min_coeff)

        if (coeff_diff := self.coeff - old_coeff) != 0:
            scale_factor = self.coeff / old_coeff
            if offset > 0:
                move_coeff = -(1 - scale_factor)
            else:
                move_coeff = (1 - 1 / scale_factor)
            if abs(coeff_diff - coeff_offset) < 0.01:
                move_coeff = round(move_coeff, 2)
            offset_x = (self.offset_x - position_x) * move_coeff
            offset_y = (self.offset_y - position_y) * move_coeff
            self.change_offset(offset_x, offset_y)

        self.reset()

    def change_offset(self, offset_x: float, offset_y: float) -> None:
        offset_x = round(offset_x)
        offset_y = round(offset_y)
        self.offset_x += offset_x
        self.offset_y += offset_y
        self.tiles_set.move(offset_x, offset_y)
        self.edges_set.move(offset_x, offset_y)


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
                    radius = (self.center_a + self.center_b + self.center_c) / 3
                    a_centered = a - self.center_a
                    b_centered = b - self.center_b
                    c_centered = c - self.center_c
                    if (a_centered ** 2 + b_centered ** 2 + c_centered ** 2) ** (1 / 2) <= radius:
                        self.material[a, b, c][Water] = self.max_material_amount * 2 // 3

        for a in range(self.max_a):
            for b in range(self.max_b):
                for c in range(self.max_c):
                    materials: Materials = self.material[a, b, c]
                    total_amount = sum(amount for amount in materials.values())
                    assert total_amount <= self.max_material_amount, f"Total amount of materials in tile ({total_amount}) must be lower or equal to max_material_amount ({self.max_material_amount})"
                    if total_amount < self.max_material_amount:
                        materials[Vacuum] = self.max_material_amount - total_amount
