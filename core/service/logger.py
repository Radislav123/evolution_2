import logging
from pathlib import Path

from core.service.settings import Settings


class Logger:
    settings = Settings()

    LOG_FORMATTER = logging.Formatter(settings.LOG_FORMAT)
    LOG_LEVEL_NAMES = {
        logging.WARNING: "warning",
        logging.INFO: "info",
        logging.DEBUG: "debug"
    }

    @staticmethod
    def get_function_real_filename(function):
        return function.__globals__["__file__"].split('\\')[-1]

    @classmethod
    def get_log_filepath(cls, filename):
        return f"{cls.settings.LOG_FOLDER}/{filename}.log"

    @classmethod
    def construct_handler(cls, log_level = logging.INFO, to_console = False):
        if to_console:
            handler = logging.StreamHandler()
        else:
            # в файл
            handler = logging.FileHandler(cls.get_log_filepath(cls.LOG_LEVEL_NAMES[log_level]))
        handler.setLevel(log_level)
        handler.setFormatter(cls.LOG_FORMATTER)
        return handler

    # уровни отображения логов описаны в documentation/LOGGING.md в разделе Информация о логировании
    def __new__(cls, logger_name: str) -> logging.LoggerAdapter:
        # создает папку для логов, если ее нет
        Path(cls.settings.LOG_FOLDER).mkdir(parents = True, exist_ok = True)
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers = [
            # в файл
            cls.construct_handler(cls.settings.FILE_LOG_LEVEL),
            # в консоль
            cls.construct_handler(cls.settings.CONSOLE_LOG_LEVEL, True)
        ]
        logger = logging.LoggerAdapter(logger)
        return logger


# для проверки логгера
if __name__ == "__main__":
    test_logger = Logger(__name__)
    print(f"logger name: {test_logger.name}")
    print(f"help: {Logger.__doc__}")

    test_logger.info("info message")
    test_logger.debug("debug message")
    test_logger.warning("warning message")
    test_logger.error("error message")
    test_logger.critical("critical message")
