from threading import Lock as StandardLock, Thread, ThreadError, current_thread
from types import TracebackType


class MultipleAcquireAttemptException(ThreadError):
    pass


class CallFromAnotherThreadException(ThreadError):
    pass


class Lock:
    def __init__(self) -> None:
        self.lock = StandardLock()
        self.locked = False
        self.thread: Thread | None = None

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(
            self,
            exc_type: type[Exception] | None,
            exc_value: Exception | None,
            exc_traceback: TracebackType | None
    ) -> bool | None:
        return self.release()

    def acquire(self) -> bool:
        if self.locked:
            raise MultipleAcquireAttemptException()
        else:
            self.locked = True
            self.thread = current_thread()
            return self.lock.acquire()

    def release(self) -> bool | None:
        self.locked = False
        self.thread = None
        # Проверка на освобождения без получения (acquire) уже реализована в самом self.lock.release()
        return self.lock.release()

    def check_thread(self, message: str = "") -> None:
        if self.locked and self.thread != current_thread():
            raise CallFromAnotherThreadException(message)
