#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from typing import Callable, Generic, TypeVar, Set


T = TypeVar("T", bound=Callable[..., None])


class SSVCallbackDispatcher(Generic[T]):
    """
    A simple event callback dispatcher class similar to the ``ipywidgets.widgets.widget.CallbackDispatcher``.
    """
    _callbacks: Set[T]

    def __init__(self):
        self._callbacks = set()

    # TODO: It would be good if we could find a way to impose the generic type constraint on the parameters this method
    #  takes.
    def __call__(self, *args, **kwargs):
        for callback in self._callbacks:
            callback(*args, **kwargs)

    def register_callback(self, callback: T, remove: bool = False):
        """
        Registers/unregisters a callback to this dispatcher.

        :param callback: the callback to add/remove.
        :param remove: whether the callback should be removed.
        """
        if remove:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
        else:
            self._callbacks.add(callback)
