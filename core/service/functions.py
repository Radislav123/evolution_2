from itertools import count, takewhile
from typing import Iterator, Type, TypeVar

from core.service.logger import Logger
from core.service.settings import Settings


settings = Settings()
logger = Logger(__name__)

T = TypeVar("T")


def float_range(start: float, stop: float, step: float) -> Iterator[float]:
    return takewhile(lambda x: x < stop, count(start, step))


def get_subclasses(cls) -> list[Type[T]]:
    """Возвращает все дочерние классы рекурсивно."""

    subclasses = cls.__subclasses__()
    child_subclasses = []
    for child in subclasses:
        child_subclasses.extend(get_subclasses(child))
    subclasses.extend(child_subclasses)
    return subclasses
