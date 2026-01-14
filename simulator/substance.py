import numpy as np

from core.service.functions import get_subclasses


# https://ru.wikipedia.org/wiki/%D0%9F%D0%B5%D1%80%D0%B8%D0%BE%D0%B4%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F_%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0_%D1%85%D0%B8%D0%BC%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D1%85_%D1%8D%D0%BB%D0%B5%D0%BC%D0%B5%D0%BD%D1%82%D0%BE%D0%B2
# todo: Температуру реализовать как количество запасенного тепла?
# todo: Добавить базовые элементы (Element), из которых будут создаваться вещества.
class Substance:
    # Характеристики одной единицы вещества - одной молекулы
    # Физические характеристики
    mass: float

    # Характеристики для отображения
    # Цвет без альфа-канала, так как он заменен на absorption
    # todo: Генерировать цвет на основе физических законов
    color: tuple[int, int, int]
    # Коэффициент поглощения света
    # todo: Реализовать спектральное поглощение, где для каждой компоненты будет свой коэффициент.
    #  Позволит "переключать зрение с человеческого" на то, что имеет определенное существо
    # https://ru.wikipedia.org/wiki/%D0%A1%D0%BF%D0%B5%D0%BA%D1%82%D1%80_%D0%BF%D0%BE%D0%B3%D0%BB%D0%BE%D1%89%D0%B5%D0%BD%D0%B8%D1%8F
    absorption: float

    @classmethod
    def calculate_arrays(cls) -> None:
        cls.real_substances = tuple(
            substance for substance in get_subclasses(cls) if hasattr(substance, "mass")
        )
        cls.indexes = np.arange(len(cls.real_substances), dtype = np.uint8)

        cls.colors = np.array(
            [substance.color for substance in cls.real_substances],
            dtype = np.float32
        )
        cls.absorptions = np.array(
            [substance.absorption for substance in cls.real_substances],
            dtype = np.float32
        )


# todo: Remove it and all subclasses
class TestSubstance(Substance):
    test = True


class Primum(TestSubstance):
    mass = 1
    absorption = 0.5
    color = (220, 100, 80)


class Secundum(TestSubstance):
    mass = 2
    absorption = 0.6
    color = (255, 220, 50)


class Tertium(TestSubstance):
    mass = 3
    absorption = 0.7
    color = (100, 200, 100)


class Quartum(TestSubstance):
    mass = 4
    absorption = 0.8
    color = (200, 230, 255)


class Quintum(TestSubstance):
    mass = 5
    absorption = 0.9
    color = (160, 80, 220)


Substance.calculate_arrays()
