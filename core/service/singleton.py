from typing import Self


class Singleton:
    instances: dict[str, Self] = {}

    def __new__(cls, *args, class_id = None, **kwargs) -> "Self":
        if class_id is None:
            class_id = cls.__name__
        if class_id not in cls.instances:
            cls.instances[class_id] = super().__new__(cls, *args, **kwargs)
        return cls.instances[class_id]
