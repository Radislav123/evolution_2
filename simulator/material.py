Materials = dict[type["Material"], int]


# https://ru.wikipedia.org/wiki/%D0%9F%D0%B5%D1%80%D0%B8%D0%BE%D0%B4%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F_%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0_%D1%85%D0%B8%D0%BC%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B8%D1%85_%D1%8D%D0%BB%D0%B5%D0%BC%D0%B5%D0%BD%D1%82%D0%BE%D0%B2
class Material:
    # Характеристики одной единицы вещества
    mass: float
    color: tuple[int, int, int, int]


class Vacuum(Material):
    mass = 0
    color = (0, 0, 0, 3)


# todo: replace it with generic
class Water(Material):
    mass = 1
    color = (174, 216, 242, 50)
