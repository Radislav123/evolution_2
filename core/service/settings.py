import logging

from core.service.singleton import Singleton


class Settings(Singleton):
    def __init__(self):
        # Настройки логгера
        self.LOG_FORMAT = ("[%(asctime)s] - [%(levelname)s] - %(name)s"
                           " - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s")
        self.LOG_FOLDER = "logs"
        self.CONSOLE_LOG_LEVEL = logging.DEBUG
        self.FILE_LOG_LEVEL = logging.DEBUG

        self.RESOURCES_FOLDER = "resources"
        self.IMAGES_FOLDER = f"{self.RESOURCES_FOLDER}/images"

        self.WORLD_SHAPE = (15, 15, 15)

        self.CAMERA_ZOOM_SENSITIVITY = 0.1
        # При значениях меньше 0.4 изображение начинает скакать и переворачиваться
        self.CAMERA_MIN_ZOOM = 0.4
        self.CAMERA_MAX_ZOOM = 100
        self.CAMERA_ZOOM = 1
        # В радианах
        self.CAMERA_YAW = 0
        # В радианах
        self.CAMERA_PITCH = 0
        self.CAMERA_ROTATION_RADIUS = self.WORLD_SHAPE[2] * 2
        self.CAMERA_ROTATION_SENSITIVITY = 0.005

        self.BUTTON_WIDTH = 230
        self.BUTTON_HEIGHT = 30
        # В секундах
        self.BUTTON_UPDATE_PERIOD = 0.5

        self.MAX_TPS = 1000
        self.TIMINGS_LENGTH = 100
        self.SPRITE_SIZE = 100
