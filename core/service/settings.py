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

        self.SPRITE_SIZE = 100

        # todo: remove camera zoom settings?
        self.CAMERA_MIN_ZOOM = 0.01
        self.CAMERA_MAX_ZOOM = 500
        self.CAMERA_INITIAL_ZOOM = 25

        self.BUTTON_WIDTH = 250
        self.BUTTON_HEIGHT = 50
