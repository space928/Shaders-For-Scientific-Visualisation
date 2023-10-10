#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from abc import ABC, abstractmethod


class SSVRender(ABC):
    """
    Am abstract rendering backend for SSV
    """

    @abstractmethod
    def __init__(self, resolution):
        ...

    @abstractmethod
    def log_context_info(self, full=False):
        """
        Logs the OpenGL information to the console for debugging.
        :param full: whether to log *all* of the OpenGL context information (including extensions)
        """
        ...
