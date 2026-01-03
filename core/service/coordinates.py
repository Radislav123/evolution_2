import functools


class Coordinates:
    # Отображение точки в трехмерном пространстве на двумерное
    @staticmethod
    @functools.cache
    def convert_3_to_2(a: float, b: float, c: float, coeff: float = 1) -> tuple[float, float]:
        x = (a + b / 4) * coeff
        y = (c + b / 3) * coeff
        return x, y
