import copy
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Self, TYPE_CHECKING

from core.service.coordinates import Coordinates
from core.service.object import PhysicalObject, ProjectionObject
from simulator.creature import Creature
from simulator.tile import Tile, TileProjection


if TYPE_CHECKING:
    from simulator.world import BaseSet, CreatureSet, Regions2, Tiles2


class RegionProjection(ProjectionObject):
    tile_projection: TileProjection


class Region(PhysicalObject):
    projection_class = RegionProjection
    projections: dict[Tile, projection_class]
    neighbours: list[Self]
    radius: int = None

    def __init__(self, coordinates: Coordinates) -> None:
        super().__init__()
        self.coordinates = coordinates
        self.x = self.coordinates.x
        self.y = self.coordinates.y

        self.a = self.coordinates.a
        self.b = self.coordinates.b
        self.c = self.coordinates.c

        self.tiles: set[Tile] | None = None
        self.neighbour_layers: dict[int, set[Self]] = {}
        self.bases: BaseSet = []
        self.creatures: CreatureSet = []

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.coordinates})"

    def on_update(
            self,
            time: int,
            regions_2: "Regions2",
            bases: "BaseSet",
            thread_executor: ThreadPoolExecutor
    ) -> list[Future]:
        futures = []
        for base in self.bases:
            if time % base.act_period == base.act_remainder:
                futures.append(thread_executor.submit(base.on_update, time, regions_2))
        for creature in self.creatures:
            if time % creature.act_period == creature.act_remainder:
                futures.append(thread_executor.submit(creature.on_update, time, regions_2, bases))

        return futures

    def after_update(self, time: int) -> Any:
        # todo: make it with threads
        for base in self.bases:
            if time % base.act_period == base.act_remainder:
                base.after_update()
        for creature in self.creatures:
            if time % creature.act_period == creature.act_remainder:
                creature.after_update()

    def init(self, tiles_2: "Tiles2", regions_2: "Regions2") -> Any:
        self.projections = {}
        for tile in self.tiles:
            projection = self.projection_class()
            self.projections[tile] = projection
            projection.tile_projection = tile.projection

        neighbour_indexes = [index.fix_to_cycle(tiles_2) for index in self.coordinates.get_region_neighbour_centers()]
        self.neighbours = [regions_2[index.x][index.y] for index in neighbour_indexes]

    def get_creatures(self, radius: int, regions_2: "Regions2") -> list[Creature]:
        # noinspection PyTypeChecker
        creatures: list[Creature] = copy.copy(self.creatures)
        layers = radius // self.radius + 1

        if layers not in self.neighbour_layers:
            region_indexes = set()
            region_indexes.add(self.coordinates)
            region_indexes = Coordinates.append_layers(regions_2, region_indexes, layers)
            regions = set(regions_2[index.x][index.y] for index in region_indexes)
            self.neighbour_layers[layers] = regions
        regions = self.neighbour_layers[layers]

        for region in regions:
            creatures.extend(region.creatures)

        return creatures
