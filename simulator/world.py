import datetime
import os
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import arcade
import numpy as np

from core.service.coordinates import Coordinates
from core.service.object import Object, ProjectionObject


# служит только как хранилище настроек
class Tile:
    visible_color = (0, 0, 0, 50)
    not_visible_color = (0, 0, 0, 10)
    default_width = 1


class WorldProjection(ProjectionObject):
    def __init__(self, world: World) -> None:
        super().__init__()

        # соотносится с центром окна
        self.offset_x: float | None = None
        self.offset_y: float | None = None
        self.world_width = world.width
        self.world_height = world.height
        self.world_depth = world.depth

        # множитель размера отображения мира
        self.coeff: float | None = None
        self.min_coeff = 0.01
        self.max_coeff = 200

        # В каждой ячейке лежит массив с гранями
        # [face_0, face_1, face_2, face_3, face_4, face_5]
        self.tiles = np.array([lambda: [None] * 6 for _ in range(world.material.size)]).reshape(world.shape)
        self.tiles_set = arcade.shape_list.ShapeElementList()

        self.centralize()
        self.inited = False

    def init(self) -> Any:
        for a in range(self.world_depth):
            for b in range(self.world_height):
                for c in range(self.world_depth):
                    offset_x, offset_y = Coordinates.convert_3_to_2(a, b, c)
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
                    # (x, y)
                    points = [Coordinates.convert_3_to_2(*point) for point in points]
                    # coeff and offset
                    points = [
                        (
                            (point[0] + offset_x) * self.coeff + self.offset_x,
                            (point[1] + offset_y) * self.coeff + self.offset_y
                        ) for point in points
                    ]

                    # обход по граням
                    faces = [
                        [0, 4, 7, 3],
                        [4, 5, 6, 7],
                        [3, 7, 6, 2],
                        [0, 4, 5, 1],
                        [0, 1, 2, 3],
                        [1, 5, 6, 2]
                    ]
                    faces = [
                        arcade.shape_list.create_line_loop(
                            [points[point_index] for point_index in face],
                            Tile.visible_color if index in Coordinates.visible_faces() else Tile.not_visible_color,
                            Tile.default_width
                        ) for index, face in enumerate(faces)
                    ]

                    for face in faces:
                        self.tiles_set.append(face)
                    self.tiles[a, b, c] = faces
        self.inited = True

    def reset(self) -> None:
        self.tiles_set.clear()
        self.inited = False

    def start(self) -> None:
        pass

    def on_draw(self, draw_tiles: bool) -> None:
        if not self.inited:
            self.init()
        if draw_tiles:
            self.tiles_set.draw()

    def change_coeff(self, position_x: int, position_y: int, offset: int) -> None:
        scroll_coeff = 10
        coeff_offset = offset * self.coeff / self.max_coeff * scroll_coeff
        old_coeff = self.coeff
        self.coeff = max(min(self.coeff + coeff_offset, self.max_coeff), self.min_coeff)

        if (coeff_diff := self.coeff - old_coeff) != 0:
            move_coeff = -(1 - self.coeff / old_coeff)
            if abs(coeff_diff - coeff_offset) < 0.01:
                move_coeff = round(move_coeff, 2)
            offset_x = (self.offset_x - position_x) * move_coeff
            offset_y = (self.offset_y - position_y) * move_coeff
            self.offset_x += offset_x
            self.offset_y += offset_y

        self.reset()

    def centralize(self) -> None:
        window = arcade.get_window()

        # todo: вызов данного метода должен перерисовывать карту так, чтобы она целиком помещалась на экране?
        self.coeff = 50

        self.offset_x, self.offset_y = Coordinates.convert_3_to_2(
            self.world_width / 2,
            self.world_height / 2,
            self.world_depth / 2
        )
        self.offset_x *= -self.coeff
        self.offset_y *= -self.coeff
        self.offset_x += window.center_x
        self.offset_y += window.center_y

        self.reset()

    def change_offset(self, offset_x: int, offset_y: int) -> None:
        self.offset_x += offset_x
        self.offset_y += offset_y
        self.reset()


class World(Object):
    def __init__(
            self,
            width: int,
            height: int,
            depth: int,
            seed: int = None
    ) -> None:
        super().__init__()
        self.width = width
        self.height = height
        self.depth = depth

        if seed is None:
            seed = datetime.datetime.now().timestamp()
        self.seed = seed
        random.seed(self.seed)

        self.age = 0
        self.center_a = self.width // 2
        self.center_b = self.height // 2
        self.center_c = self.depth // 2

        cells_number = self.width * self.height * self.depth
        self.shape = (self.width, self.height, self.depth)
        # В каждой ячейке лежит словарь с веществом и его количеством
        # {material: amount}
        self.material = np.array([defaultdict(int) for _ in range(cells_number)]).reshape(self.shape)

        self.projection = WorldProjection(self)

        self.thread_executor = ThreadPoolExecutor(os.cpu_count())
        self.prepare()

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
        pass
