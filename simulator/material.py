# https://ru.wikipedia.org/wiki/%D0%9F%D0%B5%D1%80%D0%B8%D0%BE%D0%B4%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F_%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0_%D1%85%D0%B8%D0%BC%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D1%85_%D1%8D%D0%BB%D0%B5%D0%BC%D0%B5%D0%BD%D1%82%D0%BE%D0%B2
class Material:
    index = 0
    counter = 0
    # Характеристики одной единицы вещества
    mass: float
    color: tuple[int, int, int, int]

    def __init_subclass__(cls):
        super().__init_subclass__()
        Material.counter += 1
        cls.index = Material.counter


# todo: Добавить базовые элементы, из которых будут создаваться материалы.
class Unit(Material):
    mass = 1
    # todo: Генерировать цвет на основе физических законов
    color = (200, 230, 255, 100)
