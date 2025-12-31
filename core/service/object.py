from typing import Any, Self

from arcade import Sprite, color
from arcade.types import Color

from core.service import settings
from core.service.logger import Logger
from core.service.settings import Settings
from core.service.texture import Texture


class Mixin:
    settings = Settings()
    logger = Logger(__qualname__)


class Object:
    settings = settings.Settings()
    counter = 0
    logger = Logger(__qualname__)

    def __init__(self) -> None:
        super().__init__()
        self.id = self.counter
        self.__class__.counter += 1

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.id})"

    def __repr__(self) -> str:
        return str(self)

    def __lt__(self, other: "Self") -> bool:
        return self.id < other.id


class ProjectionObject(Sprite, Object):
    main_color: Color = color.WHITE
    border_color: Color = color.BLACK
    background_color: Color = color.TRANSPARENT_BLACK

    def __init__(self) -> None:
        texture = Texture.create_hexagon(
            25,
            1,
            self.main_color,
            self.border_color,
            self.background_color
        )
        super().__init__(texture, 1, 0, 0, 0)
        self.selected = False


class PhysicalObject(Object):
    def on_update(self, *args, **kwargs) -> Any:
        raise NotImplementedError()
