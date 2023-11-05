#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

import numpy.typing as npt


class ShaderStage(Enum):
    """
    An enum representing an OpenGL shader stage.
    """
    VERTEX = "vertex"
    TESSELLATION = "tessellation"
    GEOMETRY = "geometry"
    PIXEL = "pixel"
    COMPUTE = "compute"


class SSVRender(ABC):
    """
    An abstract rendering backend for SSV
    """

    @abstractmethod
    def __init__(self):
        ...

    @abstractmethod
    def render(self) -> bool:
        """
        Renders a complete frame.

        :return: whether the frame rendered successfully.
        """
        ...

    def get_frame(self, components=4) -> bytearray:
        """
        Gets the current contents of the frame buffer as a byte array.

        :param components: how many components to read from the frame (out of ``RGBA``).
        :return: the contents of the frame buffer as a bytearray in the ``RGBA`` format.
        """
        ...

    @abstractmethod
    def log_context_info(self, full=False):
        """
        Logs the OpenGL information to the console for debugging.

        :param full: whether to log *all* of the OpenGL context information (including extensions).
        """
        ...

    @abstractmethod
    def update_frame_buffer(self, buffer_id: int, size: (int, int), pixel_format: int):
        """
        Updates the resolution/format of the given frame buffer. Note that framebuffer 0 is always used for output.
        If the given framebuffer id does not exist, it is created.

        :param buffer_id: the id of the framebuffer to update/create. Buffer 0 is the output framebuffer.
        :param size: the new resolution of the framebuffer.
        :param pixel_format: the new pixel format of the framebuffer.
        """
        ...

    @abstractmethod
    def delete_frame_buffer(self, buffer_id: int):
        """
        Destroys the given framebuffer. *Note* that framebuffer 0 can't be destroyed as it is the output framebuffer.

        :param buffer_id: the id of the framebuffer to destroy.
        """
        ...

    @abstractmethod
    def update_uniform(self, buffer_id: int, uniform_name: str, value):
        """
        Updates the value of a named shader uniform.

        :param buffer_id: the id of the program of the uniform to update. Set to -1 to update across all buffers.
        :param uniform_name: the name of the shader uniform to update.
        :param value: the new value of the shader uniform. (Must be convertible to GLSL type)
        """
        ...

    @abstractmethod
    def update_vertex_buffer(self, buffer_id: int, array: Optional[npt.NDArray]):
        """
        Updates the data inside a vertex buffer.

        :param buffer_id: the buffer_id of the vertex array to update.
        :param array: a numpy array containing the new vertex data.
        """
        ...

    @abstractmethod
    def register_shader(self, buffer_id: int, vertex_shader: str, fragment_shader: Optional[str],
                        tess_control_shader: Optional[str], tess_evaluation_shader: Optional[str],
                        geometry_shader: Optional[str], compute_shader: Optional[str]):
        """
        Compiles and registers a shader to a given framebuffer.

        :param buffer_id: the framebuffer id to register the shader to.
        :param vertex_shader: the preprocessed vertex shader GLSL source.
        :param fragment_shader: the preprocessed fragment shader GLSL source.
        :param tess_control_shader: the preprocessed tessellation control shader GLSL source.
        :param tess_evaluation_shader: the preprocessed tessellation evaluation shader GLSL source.
        :param geometry_shader: the preprocessed geometry shader GLSL source.
        :param compute_shader: *[Not implemented]* the preprocessed compute shader GLSL source.
        """
        ...
