from typing import Any, TypeVar

from core.service.logger import Logger
from core.service.settings import Settings


PointType = TypeVar("PointType")


class ProjectMixin:
    settings = Settings()

    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.logger = Logger(cls.__name__)


class Object(ProjectMixin):
    pass


class ProjectionObject(Object):
    pass


class PhysicalObject(Object):
    def on_update(self, *args, **kwargs) -> Any:
        raise NotImplementedError()
