#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Any

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

    @abstractmethod
    def read_frame(self, components: int = 4, frame_buffer_uid: int = 0) -> bytes:
        """
        Gets the current contents of the frame buffer as a byte array.

        :param components: how many components to read from the frame (out of ``RGBA``).
        :param frame_buffer_uid: the frame buffer to read from.
        :return: the contents of the frame buffer as a bytearray in the ``RGBA`` format.
        """
        ...

    @abstractmethod
    def read_frame_into(self, buffer: bytearray, components: int = 4, frame_buffer_uid: int = 0):
        """
        Gets the current contents of the frame buffer as a byte array.

        :param buffer: the buffer to copy the frame into.
        :param components: how many components to read from the frame (out of ``RGBA``).
        :param frame_buffer_uid: the frame buffer to read from.
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
    def update_frame_buffer(self, frame_buffer_uid: int, order: int, size: (int, int), components: int = 4,
                            dtype: str = "f1"):
        """
        Updates the resolution/format of the given frame buffer. Note that framebuffer 0 is always used for output.
        If the given framebuffer id does not exist, it is created.

        :param frame_buffer_uid: the uid of the framebuffer to update/create. Buffer 0 is the output framebuffer.
        :param order: the sorting order to render the frame buffers in, smaller values are rendered first.
        :param size: the new resolution of the framebuffer.
        :param components: how many vector components should each pixel have (RGB=3, RGBA=4).
        :param dtype: the data type for each pixel component (see: https://moderngl.readthedocs.io/en/5.8.2/topics/texture_formats.html).
        """
        ...

    @abstractmethod
    def delete_frame_buffer(self, frame_buffer_uid: int):
        """
        Destroys the given framebuffer. *Note* that framebuffer 0 can't be destroyed as it is the output framebuffer.

        :param frame_buffer_uid: the uid of the framebuffer to destroy.
        """
        ...

    @abstractmethod
    def update_uniform(self, frame_buffer_uid: Optional[int], draw_call_uid: Optional[int],
                       uniform_name: str, value: Any):
        """
        Updates the value of a named shader uniform.

        :param frame_buffer_uid: the uid of the framebuffer of the uniform to update. Set to ``None`` to update across
                                 all buffers.
        :param draw_call_uid: the uid of the draw call of the uniform to update. Set to ``None`` to update across all
                              buffers.
        :param uniform_name: the name of the shader uniform to update.
        :param value: the new value of the shader uniform. (Must be convertible to a GLSL type)
        """
        ...

    @abstractmethod
    def update_vertex_buffer(self, frame_buffer_uid: int, draw_call_uid: int,
                             vertex_array: npt.NDArray, index_array: Optional[npt.NDArray],
                             vertex_attributes: tuple[str]):
        """
        Updates the data inside a vertex buffer.

        :param frame_buffer_uid: the uid of the framebuffer of the vertex buffer to update.
        :param draw_call_uid: the uid of the draw call of the vertex buffer to update.
        :param vertex_array: a numpy array containing the new vertex data.
        :param index_array: optionally, a numpy array containing the indices of vertices ordered to make triangles.
        :param vertex_attributes: a tuple of the names of the vertex attributes to map to in the shader, in the order
                                  that they appear in the vertex array.
        """
        ...

    @abstractmethod
    def register_shader(self, frame_buffer_uid: int, draw_call_uid: int,
                        vertex_shader: str, fragment_shader: Optional[str],
                        tess_control_shader: Optional[str], tess_evaluation_shader: Optional[str],
                        geometry_shader: Optional[str], compute_shader: Optional[str]):
        """
        Compiles and registers a shader to a given framebuffer.

        :param frame_buffer_uid: the uid of the framebuffer to register the shader to.
        :param draw_call_uid: the uid of the draw call to register the shader to.
        :param vertex_shader: the preprocessed vertex shader GLSL source.
        :param fragment_shader: the preprocessed fragment shader GLSL source.
        :param tess_control_shader: the preprocessed tessellation control shader GLSL source.
        :param tess_evaluation_shader: the preprocessed tessellation evaluation shader GLSL source.
        :param geometry_shader: the preprocessed geometry shader GLSL source.
        :param compute_shader: *[Not implemented]* the preprocessed compute shader GLSL source.
        """
        ...

    @abstractmethod
    def update_texture(self, texture_uid: int, data: npt.NDArray, rect: Optional[tuple[int, int, int, int]]):
        """
        Creates or updates a texture from the NumPy array provided.

        :param texture_uid: the uid of the texture to create or update.
        :param data: a NumPy array containing the image data to copy to the texture.
        :param rect: optionally, a rectangle (left, top, right, bottom) specifying the area of the target texture to
                     update.
        """
        ...

    @abstractmethod
    def delete_texture(self, texture_uid: int):
        """
        Destroys the given texture object.

        :param texture_uid: the uid of the texture to destroy.
        """
        ...
