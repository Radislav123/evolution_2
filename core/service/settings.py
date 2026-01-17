import logging
import os

from pyglet.math import Vec3

from core.service.singleton import Singleton


class SettingError(ValueError):
    pass


class Settings(Singleton):
    def __init__(self) -> None:
        # Настройки логгера
        self.LOG_FORMAT = ("[%(asctime)s] - [%(levelname)s] - %(name)s"
                           " - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s")
        self.LOG_FOLDER = "logs"
        self.CONSOLE_LOG_LEVEL = logging.DEBUG
        self.FILE_LOG_LEVEL = logging.DEBUG

        self.RESOURCES = "resources"
        self.IMAGES = f"{self.RESOURCES}/images"
        self.SHADERS = f"shaders"
        self.CPU_COUNT = os.cpu_count()

        self.WORLD_UPDATE_PERIOD = 1
        self.WORLD_SEED = None
        self.WORLD_SHAPE = Vec3(64, 64, 64)
        self.CHUNK_SHAPE = Vec3(32, 32, 32)

        self.OPTICAL_DENSITY_SCALE = 0.001

        self.CELL_SUBSTANCE_COUNT = 4

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

        self.WINDOW_WIDTH = 800
        self.WINDOW_HEIGHT = 600

        self.BUTTON_WIDTH = 230
        self.BUTTON_HEIGHT = 30
        # В секундах
        self.BUTTON_UPDATE_PERIOD = 0.5

        self.MAX_TPS = 1000
        self.TIMINGS_LENGTH = 100

        self.TEST_COLOR_CUBE = True
        self.TEST_COLOR_CUBE_START = (1.0, 1.0, 1.0, max(1 / max(self.WORLD_SHAPE), 0.03))
        self.TEST_COLOR_CUBE_END = (0.0, 0.0, 0.0, max(1 / max(self.WORLD_SHAPE), 0.03))

        self.check()

    # todo: Прописать проверки для всех настроек
    # Тут именно исключения, а не ассерты, так как настройки могут меняться пользователем
    def check(self) -> None:
        if min(self.WORLD_SHAPE) <= 1:
            raise SettingError(f"All world dimensions, WORLD_SHAPE {self.WORLD_SHAPE}, must be greater than 1")

        if self.CPU_COUNT <= 0:
            raise SettingError(f"CPU_COUNT ({self.CPU_COUNT}) must be greater than 0")

        # Именно 32, потому что массивы именно такого размера создаются в шейдере
        if not (0 < self.CELL_SUBSTANCE_COUNT <= 32) or self.CELL_SUBSTANCE_COUNT % 4 != 0:
            raise SettingError(
                f"CELL_SUBSTANCE_COUNT ({self.CELL_SUBSTANCE_COUNT}) must be grater than zero,"
                f" lower or equal to 32 and a multiple of four"
            )
