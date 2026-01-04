import itertools
from typing import Any, Self

from arcade import Sprite
from arcade.shape_list import Shape
from arcade.types import PointList, RGBA255

from core.service.colors import ProjectColors
from core.service.logger import Logger
from core.service.settings import Settings
from core.service.texture import Texture


class ObjectMixin:
    settings = Settings()

    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.logger = Logger(cls.__name__)


class Object(ObjectMixin):
    pass


class ProjectionObject(Object):
    pass


class ShapeObject(Shape, ProjectionObject):
    default_mode: int

    # Сначала применяется смещение (offset_[x|y]), потом масштаб (scale)
    def __init__(
            self,
            points: PointList,
            offset_x: float = 0,
            offset_y: float = 0,
            color: RGBA255 = None,
            copying: bool = False
    ) -> None:
        self.is_copy = copying

        self.offset_x = offset_x
        self.offset_y = offset_y

        self.default_points = points
        points = [(x + self.offset_x, y + self.offset_y) for x, y in self.default_points]

        if color is None:
            color = ProjectColors.PLACEHOLDER
        self.color = color
        colors = [color] * len(points)

        super().__init__(points, colors, self.default_mode)
        super(ProjectionObject, self).__init__()

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


class SpriteObject(Sprite, ProjectionObject):
    def __init__(self) -> None:
        texture = Texture.create_circle(
            self.settings.SPRITE_SIZE / 2,
            1,
            ProjectColors.WHITE,
            ProjectColors.BLACK,
            ProjectColors.TRANSPARENT_BLACK
        )
        super().__init__(texture, 1, 0, 0, 0)
        super(ProjectionObject, self).__init__()


class PhysicalObject(Object):
    def on_update(self, *args, **kwargs) -> Any:
        raise NotImplementedError()
