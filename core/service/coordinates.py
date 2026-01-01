import math


COS_30 = math.cos(1 / 6)
SIN_30 = math.sin(1 / 6)


class Coordinates:
    # Отображение точки в трехмерном пространстве на двумерное
    @staticmethod
    def convert_3_to_2(a: float, b: float, c: float) -> tuple[float, float]:
        x = a + b / 2
        y = c + b / 2
        return x, y
