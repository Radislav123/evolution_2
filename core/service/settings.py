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

        self.MAX_TPS = 1000
        self.TIMINGS_LENGTH = 100
        self.TAB_UPDATE_PERIOD = 10
        self.WORLD_AGE_TAB_UPDATE_PERIOD = 1
        self.TPS_TAB_UPDATE_PERIOD = 5
        self.RESOURCES_TAB_UPDATE_PERIOD = 100
        self.OVERLAY_UPDATE_PERIOD = 50

        self.RESOURCES_FOLDER = "resources"
        self.IMAGES_FOLDER = f"{self.RESOURCES_FOLDER}/images"

        self.SPRITE_SIZE = 100

        self.CAMERA_MIN_ZOOM = 0.01
        self.CAMERA_MAX_ZOOM = 500
        self.CAMERA_INITIAL_ZOOM = 25

        self.BUTTON_WIDTH = 250
        self.BUTTON_HEIGHT = 50
