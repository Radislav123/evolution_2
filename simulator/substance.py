from typing import Self

import numpy as np
import numpy.typing as npt

from core.service.functions import get_subclasses


class SubstanceInitError(Exception):
    pass


# https://ru.wikipedia.org/wiki/%D0%9F%D0%B5%D1%80%D0%B8%D0%BE%D0%B4%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F_%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0_%D1%85%D0%B8%D0%BC%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D1%85_%D1%8D%D0%BB%D0%B5%D0%BC%D0%B5%D0%BD%D1%82%D0%BE%D0%B2
# todo: Температуру реализовать как количество запасенного тепла?
# todo: Добавить базовые элементы (Element), из которых будут создаваться вещества.
class Substance:
    count: int
    real = False
    # Характеристики одной единицы вещества - одной молекулы
    # Физические характеристики
    mass: float
    mass_bits = 10

    # Характеристики для отображения
    # Цвет без альфа-канала, так как он заменен на absorption
    # Альфа канал заполнен 0 только для дополнения до 4 байтов
    # todo: Генерировать цвет на основе физических законов
    color: tuple[int, int, int, int]
    # Коэффициент поглощения света
    # todo: Реализовать спектральное поглощение, где для каждой компоненты будет свой коэффициент.
    #  Позволит "переключать зрение с человеческого" на то, что имеет определенное существо
    # https://ru.wikipedia.org/wiki/%D0%A1%D0%BF%D0%B5%D0%BA%D1%82%D1%80_%D0%BF%D0%BE%D0%B3%D0%BB%D0%BE%D1%89%D0%B5%D0%BD%D0%B8%D1%8F
    absorption: float

    def __init__(self) -> None:
        raise SubstanceInitError(f"{self.__class__} instancies are not allowed")

    @classmethod
    def check(cls) -> None:
        if cls is not Vacuum:
            assert 0 < cls.mass < 1 << cls.mass_bits, f"Mass ({cls.mass}) must be in (0; {1 << cls.mass_bits})"
            assert 0 < cls.absorption, f"Absorption ({cls.absorption}) must be greater then 0"
            assert all(0 <= component <= 255 for component in cls.color[:3]), \
                f"Color components {cls.color[:3]} must be in [0; 255]"

    @classmethod
    def calculate_arrays(cls) -> None:
        cls.real_substances: tuple[Self, ...] = tuple(substance for substance in get_subclasses(cls) if substance.real)
        for substance in cls.real_substances:
            substance.check()

        cls.real_count = len(cls.real_substances)
        cls.indexes = np.arange(cls.real_count, dtype = np.uint8)

        cls.physics_data: npt.NDArray[np.uint32] = np.zeros((cls.real_count, 1), dtype = np.uint32)
        cls.physics_data[:, 0] = [substance.mass for substance in cls.real_substances]

        cls.optics_data = np.zeros(
            cls.real_count,
            dtype = np.dtype([("color", np.uint32), ("absorption", np.float32)])
        )
        cls.optics_data["color"] = [np.uint32(substance.color[0])
                                    | (np.uint32(substance.color[1]) << 8)
                                    | (np.uint32(substance.color[2]) << 16)
                                    for substance in cls.real_substances]
        cls.optics_data["absorption"] = [np.float32(substance.absorption) for substance in cls.real_substances]


# Не должен использоваться в расчетах, должен лишь служить как маркер отсутствия вещества, коим и является
# Должен быть единственным не генерируемым, а заданным веществом
class Vacuum(Substance):
    real = True
    mass = 0
    absorption = 0
    color = (0, 0, 0, 0)


# todo: Remove TestSubstance and all subclasses
class TestSubstance(Substance):
    test = True

    def __init_subclass__(cls, **kwargs) -> None:
        cls.real = True


class Primum(TestSubstance):
    mass = 1
    absorption = 0.5
    color = (220, 100, 80, 0)


class Secundum(TestSubstance):
    mass = 2
    absorption = 0.6
    color = (255, 220, 50, 0)


class Tertium(TestSubstance):
    mass = 3
    absorption = 0.7
    color = (100, 200, 100, 0)


class Quartum(TestSubstance):
    mass = 4
    absorption = 0.8
    color = (200, 230, 255, 0)


class Quintum(TestSubstance):
    mass = 5
    absorption = 0.9
    color = (160, 80, 220, 0)


Substance.calculate_arrays()
