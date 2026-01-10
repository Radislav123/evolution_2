import logging

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
        self.SHADERS = f"{self.RESOURCES}/shaders"

        self.WORLD_SHAPE = (25, 25, 25)
        self.SEED = None

        self.CAMERA_ZOOM_SENSITIVITY = 0.1
        # При значениях меньше 0.4 изображение начинает скакать и переворачиваться
        self.CAMERA_MIN_ZOOM = 0.4
        self.CAMERA_MAX_ZOOM = 100
        self.CAMERA_ZOOM = 1
        # Также является расстоянием до центра мира по умолчанию
        self.CAMERA_ROTATION_RADIUS = sum(self.WORLD_SHAPE) // 3 * 5
        self.CAMERA_ROTATION_SENSITIVITY = 0.005
        self.CAMERA_FAR = 1000
        # Не ставить 0, так как возникает ZeroDivisionError
        self.CAMERA_NEAR = 0.00001
        self.CAMERA_FOV = 20

        self.BUTTON_WIDTH = 230
        self.BUTTON_HEIGHT = 30
        # В секундах
        self.BUTTON_UPDATE_PERIOD = 0.5

        self.MAX_TPS = 1000
        self.TIMINGS_LENGTH = 100

        self.COLOR_TEST = False

        self.check()

    # Тут именно исключения, а не ассерты, так как настройки могут меняться пользователем
    def check(self) -> None:
        if min(self.WORLD_SHAPE) <= 0:
            raise SettingError(f"All world dimensions, WORLD_SHAPE {self.WORLD_SHAPE}, must be greater then 0")
