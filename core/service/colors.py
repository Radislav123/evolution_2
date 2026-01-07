# Чем меньше альфа-канал, тем прозрачней
# 255 - полностью непрозрачный
# 0 - полностью прозрачный
class ProjectColors:
    ArcadeType = tuple[int, int, int, int]
    OpenGLType = tuple[float, float, float, float]

    PLACEHOLDER = (239, 64, 245, 255)

    VOXEL_EDGE = (0, 0, 0, 1)

    BACKGROUND_DARK = (30, 35, 45, 255)
    BACKGROUND_LIGHT = (230, 235, 245, 255)

    WHITE = (255, 255, 255, 255)
    BLACK = (0, 0, 0, 255)
    TRANSPARENT_WHITE = (255, 255, 255, 0)
    TRANSPARENT_BLACK = (0, 0, 0, 0)

    MATERIAL_VACUUM = (0, 0, 0, 3)
    MATERIAL_WATER = (174, 216, 242, 150)

    @staticmethod
    def to_opengl(r: int, g: int, b: int, a: int) -> OpenGLType:
        return r / 255, g / 255, b / 255, a / 255
