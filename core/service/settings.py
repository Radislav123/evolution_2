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

        self.MAX_TPS = 1000
        self.TIMINGS_LENGTH = 100
        self.SPRITE_SIZE = 100

        # При значениях меньше 0.4 изображение начинает скакать и переворачиваться
        self.CAMERA_MIN_ZOOM = 0.4
        self.CAMERA_MAX_ZOOM = 500
        self.CAMERA_INITIAL_ZOOM = 25

        self.BUTTON_WIDTH = 230
        self.BUTTON_HEIGHT = 30
        # В секундах
        self.BUTTON_UPDATE_PERIOD = 0.5
