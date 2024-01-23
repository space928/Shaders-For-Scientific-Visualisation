#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

from threading import Event
from typing import Generic, TypeVar, Optional


T = TypeVar("T")


class Future(Generic[T]):
    """
    Represents a lightweight, low-level Event-backed future.

    For more complex async requirements, the asyncio library is probably a better idea.
    """
    _is_available: Event
    _result: T

    def __init__(self):
        self._is_available = Event()

    @property
    def result(self) -> T:
        return self.result

    @property
    def is_available(self) -> bool:
        return self._is_available.is_set()

    def set_result(self, val: T):
        """
        Sets the result of the Future object and notifies objects waiting for the result.

        :param val: the result to set.
        """
        self._result = val
        self._is_available.set()

    def wait_result(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Waits synchronously until the result is available and then returns it.

        :param timeout: the maximum amount of time in seconds to wait for the result. Set to ``None`` to wait
                        indefinitely.
        :return: the awaited result or ``None`` if the operation timed out.
        """
        if self._is_available.wait(timeout):
            del self._is_available
            return self._result
        else:
            return None


class Reference(Generic[T]):
    """
    Represents an object/value which can be passed by reference.
    """
    _result: T

    def __init__(self, value: T):
        self._result = value

    @property
    def result(self) -> T:
        return self._result

    @result.setter
    def result(self, value: T):
        self._result = value

    def __str__(self):
        return str(self._result)

    def __float__(self):
        return float(self._result)

    def __int__(self):
        return int(self._result)

    def __bool__(self):
        return bool(self._result)

