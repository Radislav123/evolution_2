import random
from typing import Any, Iterable, Optional, TYPE_CHECKING

from core.service.object import PhysicalObject, ProjectionObject
from simulator.action import Move


if TYPE_CHECKING:
    from simulator.tile import Tile, TileProjection


class WorldObjectProjection(ProjectionObject):
    tile_projection: "TileProjection"


class WorldObject(PhysicalObject):
    projection_class: type[WorldObjectProjection]
    projections: dict["Tile", WorldObjectProjection]
    is_base = False
    is_creature = False

    def __init__(self, center_tile: "Tile", time: int) -> None:
        super().__init__()
        self.center_tile = center_tile
        self.tiles: set["Tile"] | None = None
        self.age = 0
        self.direction: int = random.randint(0, 5)
        self.resources = 0
        self.last_acting_time = time
        self.act_period = 10
        self.act_remainder = self.id % self.act_period

        self.move = Move()

    def init(self, tiles: Iterable["Tile"]) -> Any:
        self.tiles = set(tiles)
        self.projections = {}
        for tile in self.tiles:
            tile.object = self
            projection = self.projection_class()
            self.projections[tile] = projection
            projection.tile_projection = tile.projection

    def after_update(self) -> Any:
        for key in self.__dict__:
            if key.startswith(self.settings.FUTURE_PREFIX):
                present_key = key.replace(self.settings.FUTURE_PREFIX, self.settings.PRESENT_PREFIX)
                setattr(self, present_key, getattr(self, key))
                setattr(self, key, None)
