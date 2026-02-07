import datetime
import logging
import os

from pyglet.math import Vec3

from core.service.colors import ProjectColors
from core.service.singleton import Singleton


class SettingError(ValueError):
    pass


# todo: Добавить загрузку настроек из файла (вычисляемые настройки в файл не добавлять)
class Settings(Singleton):
    def __init__(self) -> None:
        self.WINDOWS_TITLE = "evolution_2"

        # Настройки логгера
        self.LOG_FORMAT = ("[%(asctime)s] - [%(levelname)s] - %(name)s"
                           " - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s")
        self.LOG_FOLDER = "logs"
        self.CONSOLE_LOG_LEVEL = logging.DEBUG
        self.FILE_LOG_LEVEL = logging.DEBUG

        self.RESOURCES = "resources"
        self.IMAGES = f"{self.RESOURCES}/images"
        self.SHADERS = f"shaders"
        self.PHYSICAL_SHADERS = f"{self.SHADERS}/physical"
        self.PROJECTIONAL_SHADERS = f"{self.SHADERS}/projectional"
        self.CPU_COUNT = os.cpu_count()
        self.SHADER_ENCODING = "utf-8"

        self.WORLD_UPDATE_PERIOD = 1
        self.WORLD_SEED = int(datetime.datetime.now().timestamp())
        self.WORLD_SHAPE = Vec3(128, 128, 64)
        self.CELL_COUNT = self.WORLD_SHAPE.x * self.WORLD_SHAPE.y * self.WORLD_SHAPE.z
        self.CELL_SHAPE = Vec3(4, 4, 4)
        self.CELL_SIZE = self.CELL_SHAPE.x * self.CELL_SHAPE.y * self.CELL_SHAPE.z
        self.CHUNK_COUNT = 1

        # Размер рабочей группы вычислительного шейдера
        self.CELL_GROUP_SHAPE = Vec3(8, 8, 8)
        self.WORLD_GROUP_SHAPE = self.WORLD_SHAPE // self.CELL_GROUP_SHAPE

        self.GRAVITY_VECTOR = Vec3(1, 0, 0)

        self.OPTICAL_DENSITY_SCALE = 0.0003

        self.CAMERA_ZOOM_SENSITIVITY = 0.1
        # При значениях меньше 0.4 изображение начинает скакать и переворачиваться
        self.CAMERA_MIN_ZOOM = 0.4
        self.CAMERA_MAX_ZOOM = 100
        self.CAMERA_ZOOM = 1
        # Также является расстоянием до центра мира по умолчанию
        self.CAMERA_ROTATION_RADIUS = sum(self.WORLD_SHAPE) // 3 * 5
        self.CAMERA_ROTATION_SENSITIVITY = 0.005
        self.CAMERA_FAR = 10000
        # Не ставить 0, так как возникает ZeroDivisionError
        self.CAMERA_NEAR = 0.00001
        self.CAMERA_FOV = 20
        self.CAMERA_DOLLY_SENSITIVITY = 5

        self.WINDOW_WIDTH = 800
        self.WINDOW_HEIGHT = 600
        self.WINDOW_BACKGROUND_COLOR = ProjectColors.BACKGROUND_LIGHT

        self.BUTTON_WIDTH = 230
        self.BUTTON_HEIGHT = 30
        # В секундах
        self.BUTTON_UPDATE_PERIOD = 0.5

        self.MAX_FPS = 60
        self.MAX_TPS = 1000

        self.TEST_COLOR_CUBE = False
        self.TEST_COLOR_CUBE_START = (1.0, 1.0, 1.0, max(1 / max(self.WORLD_SHAPE), 0.03))
        self.TEST_COLOR_CUBE_END = (0.0, 0.0, 0.0, max(1 / max(self.WORLD_SHAPE), 0.03))

        self.check()

    # todo: Прописать проверки для всех настроек
    # todo: Добавить проверки на параметры, передаваемые в шейдеры, что они помещаются в соответствующие типы
    # Тут именно исключения, а не ассерты, так как настройки могут меняться пользователем
    def check(self) -> None:
        if min(self.WORLD_SHAPE) <= 1:
            raise SettingError(f"All world dimensions, WORLD_SHAPE {self.WORLD_SHAPE}, must be greater than 1")

        if self.CPU_COUNT <= 0:
            raise SettingError(f"CPU_COUNT ({self.CPU_COUNT}) must be greater than 0")

        if self.WORLD_SHAPE % self.CELL_GROUP_SHAPE != Vec3(0, 0, 0):
            raise SettingError(
                f"self.WORLD_SHAPE % self.CELL_GROUP_SHAPE ({self.WORLD_SHAPE} % {self.CELL_GROUP_SHAPE} == {Vec3(0, 0, 0)}) division remainder must be zero vector"
            )
