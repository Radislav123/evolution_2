class Coordinates:
    # Отображение точки в трехмерном пространстве на двумерное
    @staticmethod
    def convert_3_to_2(a: float, b: float, c: float) -> tuple[float, float]:
        x = a + b / 4
        y = c + b / 3
        return x, y
