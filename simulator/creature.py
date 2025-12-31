import random
from typing import Any, Optional, Sequence, TYPE_CHECKING, Union

from arcade import color

from core.service.coordinates import Coordinates
from core.service.threads.lock import Lock
from simulator.tile import Tile
from simulator.world_object import WorldObject, WorldObjectProjection


if TYPE_CHECKING:
    from simulator.base import Base
    from simulator.world import BaseSet, Regions2


class CreatureProjection(WorldObjectProjection):
    main_color = color.APRICOT


THREAD_SAFE_ATTRIBUTES = {
    "id",
    "age",
    "inited",
    "scream_radius",
    "hear_radius",
    "act_period",
    "act_remainder",
    # атрибуты ниже не должны быть здесь, но я не хочу продумывать их изменения
    "heard_distance",
    "heard_tile",
    "start_base",
    "finish_base",
    "center_tile"
}


class Creature(WorldObject):
    projection_class = CreatureProjection
    projections: dict["Tile", projection_class]
    is_creature = True

    def __init__(self, center_tile: "Tile", time: int, bases: Sequence["Base"]) -> None:
        self.inited = False
        super().__init__(center_tile, time)
        if len(bases) > 1:
            self.start_base, self.finish_base = random.sample(bases, 2)
        else:
            self.start_base = bases[0]
            self.finish_base = bases[0]
        self.scream_radius = 10
        self.hear_radius = 100

        # эталон направления движения
        self.reference_direction_vector = Coordinates(random.randint(-10, 10), random.randint(-10, 10))
        # направление движения
        self.direction_vector = Coordinates(0, 0)
        # пройденный путь
        self.path_vector: Coordinates = Coordinates(0, 0)
        self.bases_reach_counter = {base: 0 for base in bases}
        self.heard_distance: int | None = None
        self.heard_tile: Union["Tile", None] = None

        # некоторая доля существ является скаутами, чтобы находить базы, так как иначе базы теряются при движении
        if self.id % 100 > 90:
            self.is_scout = True
        else:
            self.is_scout = False

        self.change_direction_period = 1

        self.thread_lock = Lock()
        self.inited = True

    def __setattr__(self, key: str, value: Any) -> Any:
        if (key not in THREAD_SAFE_ATTRIBUTES
                and not key.startswith(super().__getattribute__("settings").PRESENT_PREFIX)
                and super().__getattribute__("inited")):
            super().__getattribute__("thread_lock").check_thread(f"{key}")
        return super().__setattr__(key, value)

    def __getattribute__(self, key: str) -> Any:
        if (key not in THREAD_SAFE_ATTRIBUTES
                and not key.startswith(super().__getattribute__("settings").PRESENT_PREFIX)
                and super().__getattribute__("inited")):
            super().__getattribute__("thread_lock").check_thread(f"{key}")
        return super().__getattribute__(key)

    # todo: write it?
    # def __delattr__(self, item):

    def calculate_direction(self) -> None:
        a = self.direction_vector.a - self.path_vector.a
        b = self.direction_vector.b - self.path_vector.b
        c = self.direction_vector.c - self.path_vector.c
        # offset - нужен, чтобы вес был > 0
        offset = 0.000001
        abs_a = abs(a) + offset
        abs_b = abs(b) + offset
        abs_c = abs(c) + offset
        farthest = random.choices((a, b, c), (abs_a, abs_b, abs_c))[0]
        if farthest == a:
            if a >= 0:
                self.direction = 0
            else:
                self.direction = 3
        elif farthest == b:
            if b >= 0:
                self.direction = 4
            else:
                self.direction = 1
        else:
            if c >= 0:
                self.direction = 2
            else:
                self.direction = 5

        if random.randint(0, 99) > 95:
            self.direction = (self.direction + random.choice((-1, 1))) % 6

    def reflect_direction(self) -> None:
        if self.center_tile.neighbours[(self.direction + 1) % 6].object is None:
            self.turn_right()
        elif self.center_tile.neighbours[(self.direction + 5) % 6].object is None:
            self.turn_left()
        elif self.center_tile.neighbours[(self.direction + 3) % 6].object is None:
            self.turn_around()

    def calculate_vector(self) -> None:
        if self.heard_distance is not None:
            self.reference_direction_vector = self.heard_tile.coordinates - self.center_tile.coordinates
            self.direction_vector = self.reference_direction_vector.copy()
            self.path_vector.reset()
            self.heard_distance = None
            self.heard_tile = None
        if (abs(self.path_vector.a) >= abs(self.direction_vector.a)
                or abs(self.path_vector.b) >= abs(self.direction_vector.b)
                or abs(self.path_vector.c) >= abs(self.direction_vector.c)):
            self.direction_vector += self.reference_direction_vector

    def calculate_vector_scout(self) -> None:
        if (abs(self.path_vector.a) >= abs(self.direction_vector.a)
                or abs(self.path_vector.b) >= abs(self.direction_vector.b)
                or abs(self.path_vector.c) >= abs(self.direction_vector.c)):
            self.direction_vector += self.reference_direction_vector

    def act(self, time: int, delta_time: int, bases: "BaseSet") -> None:
        if time % self.change_direction_period == 0:
            self.calculate_vector()
            self.calculate_direction()
        blocker = self.move.execute(self)
        # Достиг финальной базы
        if blocker == self.finish_base:
            self.bases_reach_counter[self.finish_base] = -delta_time
            self.start_base = self.finish_base
            while len(bases) > 1 and (self.finish_base == self.start_base or self.finish_base is None):
                self.finish_base = random.choice(bases)
            self.turn_around()
        # Попытка обойти
        elif blocker is not None:
            real_direction = self.direction
            if self.center_tile.neighbours[temp_direction := (self.direction + 1) % 6].object is None:
                pass
            elif self.center_tile.neighbours[temp_direction := (self.direction + 5) % 6].object is None:
                pass
            elif self.center_tile.neighbours[temp_direction := (self.direction + 3) % 6].object is None:
                pass
            else:
                temp_direction = None
            if temp_direction is not None:
                self.direction = temp_direction
                self.move.execute(self)
                self.direction = real_direction

    def act_scout(self, time: int, delta_time: int) -> None:
        if time % self.change_direction_period == 0:
            self.calculate_vector_scout()
            self.calculate_direction()
        blocker = self.move.execute(self)
        # Достиг любой базы
        if blocker is not None and blocker.is_base:
            self.bases_reach_counter[blocker] = -delta_time
            self.reflect_direction()

    def on_update(self, time: int, regions_2: "Regions2", bases: "BaseSet") -> Any:
        with self.thread_lock:
            delta_time = time - self.last_acting_time
            self.last_acting_time = time

            old_coordinates = self.center_tile.coordinates
            if self.is_scout:
                self.act_scout(time, delta_time)
            else:
                self.act(time, delta_time, bases)
            self.path_vector += self.center_tile.coordinates - old_coordinates

            self.cry(regions_2)
            self.age += delta_time
            self.bases_reach_counter = {base: counter + delta_time
                                        for base, counter in self.bases_reach_counter.items()}

    def cry(self, regions_2: "Regions2") -> None:
        for other in self.center_tile.region.get_creatures(self.scream_radius, regions_2):
            if self.id != other.id:
                crier_distance = self.center_tile.coordinates.distance_3(
                    other.center_tile.coordinates,
                    True
                )
                base_distance = crier_distance + self.bases_reach_counter[other.finish_base]
                if (crier_distance <= other.hear_radius and
                        (other.heard_distance is None or base_distance < other.heard_distance)):
                    other.heard_distance = base_distance
                    other.heard_tile = self.center_tile

    def turn_right(self) -> None:
        self.direction = (self.direction + 1) % 6
        if self.reference_direction_vector:
            self.reference_direction_vector = self.reference_direction_vector.rotate_60()
            self.direction_vector = self.reference_direction_vector.copy()
            self.path_vector.reset()

    def turn_left(self) -> None:
        self.direction = (self.direction + 5) % 6
        if self.reference_direction_vector:
            self.reference_direction_vector = self.reference_direction_vector.rotate_60(clockwise = False)
            self.direction_vector = self.reference_direction_vector.copy()
            self.path_vector.reset()

    def turn_around(self) -> None:
        self.direction = (self.direction + 3) % 6
        if self.reference_direction_vector:
            self.reference_direction_vector *= -1
            self.direction_vector = self.reference_direction_vector.copy()
            self.path_vector.reset()
