import logging

from core.service.singleton import Singleton


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
        self.SHADERS = f"{self.RESOURCES}/shaders"
        self.GPU_BUFFER_COUNT = 3
        assert self.GPU_BUFFER_COUNT > 0, f"GPU_BUFFER_COUNT ({self.GPU_BUFFER_COUNT}) must be grater then 0"

        self.WORLD_SHAPE = (70, 70, 70)
        self.SEED = None

        self.CAMERA_ZOOM_SENSITIVITY = 0.1
        # При значениях меньше 0.4 изображение начинает скакать и переворачиваться
        self.CAMERA_MIN_ZOOM = 0.4
        self.CAMERA_MAX_ZOOM = 100
        self.CAMERA_ZOOM = 1
        self.CAMERA_ROTATION_RADIUS = sum(self.WORLD_SHAPE) // 3 * 5
        self.CAMERA_ROTATION_SENSITIVITY = 0.005

        self.BUTTON_WIDTH = 230
        self.BUTTON_HEIGHT = 30
        # В секундах
        self.BUTTON_UPDATE_PERIOD = 0.5

        self.MAX_TPS = 1000
        self.TIMINGS_LENGTH = 100

        self.COLOR_TEST = True
