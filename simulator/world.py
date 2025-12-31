import datetime
import math
import os
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable

from arcade import SpriteList

from core.service.coordinates import Coordinates
from core.service.object import Object, ProjectionObject
from simulator.base import Base, BaseProjection
from simulator.creature import Creature, CreatureProjection
from simulator.region import Region
from simulator.tile import Tile, TileProjection


type Tiles2 = dict[int, dict[int, Tile]]
type Regions2 = dict[int, dict[int, Region]]
type CreatureSet = list[Creature]
type BaseSet = list[Base]


class Map(ProjectionObject):
    def __init__(self, width: int, height: int) -> None:
        super().__init__()

        # соотносится с центром окна
        self.center_x = width // 2
        self.center_y = height // 2
        self.offset_x = self.center_x
        self.offset_y = self.center_y

        # множитель размера отображения мира
        self.coeff: float | None = None
        self.min_coeff = 1
        self.max_coeff = 100
        # возвышение, в градусах
        self.elevation: float | None = None
        self.tilt_coeff: float | None = None
        self.min_elevation = 30
        self.max_elevation = 90
        # поворот, в градусах
        self.rotation: float | None = None
        self.centralize()

        self.bases = SpriteList[BaseProjection]()
        self.creatures = SpriteList[CreatureProjection]()
        self.tiles = SpriteList[TileProjection]()

        self.selected_tiles = set[TileProjection]()
        self.inited = False

    def init(self) -> Any:
        self.init_tiles()
        self.init_bases()
        self.init_creatures()
        self.inited = True

    def init_tiles(self) -> None:
        for tile in self.tiles:
            tile.init(self.offset_x, self.offset_y, self.coeff, self.tilt_coeff)

    def init_bases(self) -> None:
        for base in self.bases:
            base.position = base.tile_projection.position
            base.size = base.tile_projection.size

    def init_creatures(self) -> None:
        for creature in self.creatures:
            creature.position = creature.tile_projection.position
            creature.size = creature.tile_projection.size

    def reset(self) -> None:
        self.inited = False

    def start(
            self,
            creatures: Iterable[CreatureProjection],
            bases: Iterable[BaseProjection],
            tiles: Iterable[TileProjection]
    ) -> None:
        for projection in bases:
            self.bases.append(projection)
        for projection in creatures:
            self.creatures.append(projection)
        for projection in tiles:
            self.tiles.append(projection)

    def on_draw(self, draw_creatures: bool, draw_bases: bool, draw_tiles: bool) -> None:
        if not self.inited:
            self.init()

        if draw_tiles:
            self.tiles.draw()
        if draw_bases:
            self.bases.draw()
        if draw_creatures:
            self.creatures.draw()

    def change_coeff(self, position_x: int, position_y: int, offset: int) -> None:
        scroll_coeff = 10
        coeff_offset = offset * self.coeff / self.max_coeff * scroll_coeff
        old_coeff = self.coeff
        self.coeff = max(min(self.coeff + coeff_offset, self.max_coeff), self.min_coeff)

        if (coeff_diff := self.coeff - old_coeff) != 0:
            move_coeff = -(1 - self.coeff / old_coeff)
            if abs(coeff_diff - coeff_offset) < 0.01:
                move_coeff = round(move_coeff, 1)
            offset_x = (self.offset_x - position_x) * move_coeff
            offset_y = (self.offset_y - position_y) * move_coeff
            self.offset_x += offset_x
            self.offset_y += offset_y

        self.reset()

    def centralize(self) -> None:
        # todo: вызов данного метода должен перерисовывать карту так, чтобы она целиком помещалась на экране
        self.coeff = 4
        self.elevation = 90
        self.tilt_coeff = 1
        self.rotation = 0

    def change_offset(self, offset_x: int, offset_y: int) -> None:
        self.offset_x += offset_x
        self.offset_y += offset_y
        self.reset()

    def change_tilt(self, offset: int) -> None:
        coeff = 1 / 2
        self.elevation = max(min(self.elevation + offset * coeff, self.max_elevation), self.min_elevation)
        self.tilt_coeff = math.sin(math.radians(self.elevation))
        self.reset()

    def change_rotation(self, offset: int) -> None:
        max_rotation = 360
        self.rotation = (max_rotation + self.rotation + offset) % max_rotation
        self.reset()

    def point_to_coordinates(self, point_x: float, point_y: float) -> Coordinates:
        sqrt = math.sqrt(3)

        radius = self.coeff / 2
        relative_x = point_x - self.offset_x
        relative_y = point_y - self.offset_y
        position_x = round((relative_x * sqrt / 3 - relative_y / 3) / radius)
        position_y = round((relative_y * 2 / 3) / radius / self.tilt_coeff)

        return Coordinates(position_x, position_y)


class World(Object):
    def __init__(
            self,
            world_radius: int,
            region_radius: int,
            population: int,
            bases_number: int,
            map_width: int,
            map_height: int,
            seed: int = None
    ) -> None:
        super().__init__()
        Coordinates.world_radius = world_radius
        Coordinates.region_radius = region_radius

        if seed is None:
            seed = datetime.datetime.now().timestamp()
        self.seed = seed
        self.population = population
        self.bases_number = bases_number
        random.seed(self.seed)

        self.age = 0
        self.center_x = 0
        self.center_y = 0
        # в тайлах
        Region.radius = region_radius
        self.region_radius = Region.radius
        # количество радиусов региона в радиусе мира
        self.world_radius = world_radius
        self.radius = self.world_radius * (self.region_radius * 2 + 1) + self.region_radius

        self.creatures: CreatureSet = []
        self.bases: BaseSet = []
        self.tiles_2: Tiles2 = defaultdict(dict)
        Coordinates.tiles_2 = self.tiles_2
        self.tile_set = set[Tile]()
        self.regions_2: Regions2 = defaultdict(dict)
        self.region_set = set[Region]()
        self.map = Map(map_width, map_height)

        self.thread_executor = ThreadPoolExecutor(os.cpu_count())
        self.prepare()

    def start(self) -> None:
        indexes = set(x.coordinates for x in self.tile_set)
        for _ in range(self.bases_number):
            center_index = random.choice(list(indexes))
            center_tile = self.tiles_2[center_index.x][center_index.y]
            base = Base(center_tile, self.age)

            base_indexes = set()
            base_indexes.add(base.center_tile.coordinates)
            base_indexes = Coordinates.append_layers(self.tiles_2, base_indexes, base.radius)
            base.init(self.tiles_2[index.x][index.y] for index in base_indexes)
            occupied_indexes = Coordinates.append_layers(self.tiles_2, base_indexes, base.radius)

            indexes.difference_update(occupied_indexes)
            self.bases.append(base)
            center_tile.region.bases.append(base)

        indexes = list(indexes)
        for _ in range(self.population):
            list_index = random.randint(0, len(indexes) - 1)
            center_index = indexes.pop(list_index)
            center_tile = self.tiles_2[center_index.x][center_index.y]
            creature = Creature(center_tile, self.age, self.bases)

            creature.init(self.tiles_2[index.x][index.y] for index in {center_index})
            self.creatures.append(creature)
            center_tile.region.creatures.append(creature)

    def stop(self) -> None:
        self.thread_executor.shutdown()

    def on_update(self, deta_time: int) -> None:
        self.age += deta_time
        futures = []
        # todo: сделать обход, минимизирующий обработку соседних регионов одновременно при параллельной обработке
        for region in self.region_set:
            futures.extend(region.on_update(self.age, self.regions_2, self.bases, self.thread_executor))
        for future in as_completed(futures):
            # это нужно для проброса исключения из потока
            future.result()

        for region in self.region_set:
            region.after_update(self.age)

    # https://www.redblobgames.com/grids/hexagons/#map-storage
    # todo: добавить сохранение/кэширование карты и соседей для более быстрой загрузки
    def prepare(self) -> None:
        offset = self.region_radius * 2 + 1
        region_centers = [Coordinates(0, 0)]
        for layer in range(1, self.world_radius + 1):
            for number in range(layer):
                x = self.region_radius * layer + number * (self.region_radius + 1)
                y = -(layer * offset - number * self.region_radius)
                coordinates = Coordinates(x, y)
                for _ in range(6):
                    coordinates = coordinates.rotate_60()
                    region_centers.append(coordinates)

        for coordinates in region_centers:
            region = Region(coordinates)
            self.add_region(region)

        for region in self.region_set:
            region_indexes = self.get_region_indexes(region.coordinates)
            region_tiles = set()
            for tile_index in region_indexes:
                tile = Tile(tile_index, region)
                self.add_tile(tile)
                region_tiles.add(tile)
            region.tiles = region_tiles

        for region in self.region_set:
            region.init(self.tiles_2, self.regions_2)

        for tile in self.tile_set:
            tile.init(self.tiles_2)

    def add_tile(self, tile: Tile) -> None:
        self.tiles_2[tile.x][tile.y] = tile
        self.tile_set.add(tile)

    def add_region(self, region: Region) -> None:
        self.regions_2[region.x][region.y] = region
        self.region_set.add(region)

    def get_region_indexes(self, coordinates: Coordinates) -> set[Coordinates]:
        indexes = set()
        indexes.add(coordinates)
        indexes = Coordinates.append_layers(self.tiles_2, indexes, self.region_radius, False)
        return indexes
