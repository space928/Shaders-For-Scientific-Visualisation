#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any, Dict, Tuple

from .ssv_vertex_buffer import SSVVertexBuffer

if TYPE_CHECKING:
    from .ssv_canvas import SSVCanvas
    from .ssv_render_process_client import SSVRenderProcessClient
    from .ssv_shader_preprocessor import SSVShaderPreprocessor


class SSVRenderBuffer:
    """
    A lightweight class representing a native render buffer.
    """

    def __init__(self, canvas: SSVCanvas, render_process_client: SSVRenderProcessClient,
                 preprocessor: SSVShaderPreprocessor,
                 render_buffer_uid: Optional[int], render_buffer_name: str,
                 order: int, size: tuple[int, int], dtype: str,
                 components: int):
        """
        *Used Internally*

        Note that ``SSVRenderBuffer`` objects should be constructed using the factory method on an ``SSVCanvas``.

        :param canvas: the canvas creating this render buffer.
        :param render_process_client: the render process connection belonging to the canvas.
        :param preprocessor: the preprocessor belonging to the canvas.
        :param render_buffer_uid: the UID to give this render buffer. Set to ``None`` to generate one automatically.
        :param render_buffer_name: the name of this render buffer. This is the name given to the automatically
                                   generated uniform declaration.
        :param order: the render order of the render buffer. Smaller numbers are rendered first.
        :param size: the resolution of the render buffer.
        :param dtype: the moderngl datatype of the render buffer.
        :param components: how many vector components should each pixel have (RGB=3, RGBA=4).
        """
        self._canvas = canvas
        self._render_process_client = render_process_client
        self._preprocessor = preprocessor
        self._render_buffer_uid = id(self) if render_buffer_uid is None else render_buffer_uid
        self._render_buffer_name = render_buffer_name
        self._order = order
        self._size = size
        self._components = components
        self._dtype = dtype
        self._vertex_buffers: Dict[int, SSVVertexBuffer] = {}

        # Register this frame buffer
        render_process_client.update_frame_buffer(self._render_buffer_uid, order, size, render_buffer_name,
                                                  components, dtype)
        # TODO: Support sampler3D
        preprocessor.add_dynamic_uniform(render_buffer_name, "sampler2D")

        # Create a default full screen draw call for this render buffer
        self._full_screen_vertex_buffer = SSVVertexBuffer(0, self, self._render_process_client,
                                                          self._preprocessor)
        self._vertex_buffers[self._full_screen_vertex_buffer.draw_call_uid] = self._full_screen_vertex_buffer

    def _update_frame_buffer(self):
        self._render_process_client.update_frame_buffer(self._render_buffer_uid, self._order, self._size,
                                                        self._render_buffer_name, self._components, self._dtype)

    @property
    def render_buffer_uid(self) -> int:
        """
        Gets the internal UID of this render buffer.
        """
        return self._render_buffer_uid

    @property
    def render_buffer_name(self) -> str:
        """
        Gets the name of this render buffer.
        """
        return self._render_buffer_name

    @property
    def canvas(self) -> SSVCanvas:
        """
        Gets the canvas associated with this render buffer.
        """
        return self._canvas

    @property
    def full_screen_vertex_buffer(self) -> SSVVertexBuffer:
        """
        Gets the default full-screen vertex buffer for this render buffer.
        """
        return self._full_screen_vertex_buffer

    @property
    def order(self) -> int:
        """
        Gets or sets the render order of this render buffer. This number to hint the renderer as to the order to render
        the buffers in. Smaller values are rendered first; the main render buffer has an order of 999999.
        """
        return self._order

    @order.setter
    def order(self, value):
        self._order = value
        self._update_frame_buffer()

    @property
    def size(self) -> tuple[int, int]:
        """
        Gets or sets the resolution of this render buffer.
        """
        return self._size

    @size.setter
    def size(self, value):
        self._size = value
        self._update_frame_buffer()

    @property
    def components(self) -> int:
        """
        Gets or sets how many vector components each pixel should have (RGB=3, RGBA=4).
        """
        return self._components

    @components.setter
    def components(self, value):
        self._components = value
        self._update_frame_buffer()

    @property
    def dtype(self) -> str:
        """
        Gets or sets the data type for each pixel component
        (see: https://moderngl.readthedocs.io/en/5.8.2/topics/texture_formats.html).
        """
        return self._dtype

    @dtype.setter
    def dtype(self, value):
        self._dtype = value
        self._update_frame_buffer()

    @property
    def vertex_buffers(self) -> Tuple[SSVVertexBuffer, ...]:
        """Gets the tuple of vertex buffers registered to this render buffer."""
        return tuple(v for v in self._vertex_buffers.values())

    def shader(self, shader_source: str, additional_template_directory: Optional[str] = None,
               additional_templates: Optional[list[str]] = None,
               shader_defines: Optional[dict[str, str]] = None,
               compiler_extensions: Optional[list[str]] = None):
        """
        Registers, compiles and attaches a full-screen shader to this render buffer.

        :param shader_source: the shader source code to preprocess. It should contain the necessary
                              ``#pragma SSV <template_name>`` directive see :ref:`built-in-shader-templates` for more
                              information.
        :param additional_template_directory: a path to a directory containing custom shader templates. See
                                              :ref:`writing-shader-templates` for information about using custom shader
                                              templates.
        :param additional_templates: a list of custom shader templates (source code, not paths).See
                                     :ref:`writing-shader-templates` for information about using custom shader
                                     templates.
        :param shader_defines: extra preprocessor defines to be enabled globally.
        :param compiler_extensions: a list of GLSL extensions required by this shader
                                    (eg: ``GL_EXT_control_flow_attributes``)
        """
        self._full_screen_vertex_buffer.shader(shader_source, additional_template_directory, additional_templates,
                                               shader_defines, compiler_extensions)

    def update_uniform(self, uniform_name: str, value: Any, share_with_render_buffer: bool = True,
                       share_with_canvas: bool = False) -> None:
        """
        Sets the value of a uniform associated with this buffer's full-screen shader.

        :param uniform_name: the name of the uniform to set.
        :param value: the value to set. Must be compatible with the destination uniform.
        :param share_with_render_buffer: update this uniform across all shaders in this render buffer.
        :param share_with_canvas: update this uniform across all shaders in this canvas.
        """
        self._full_screen_vertex_buffer.update_uniform(uniform_name, value, share_with_render_buffer, share_with_canvas)

    def vertex_buffer(self) -> SSVVertexBuffer:
        """
        Creates a new draw call and associated vertex buffer on this render buffer.

        :return: A new vertex buffer object.
        """
        vb = SSVVertexBuffer(None, self, self._render_process_client, self._preprocessor)
        self._vertex_buffers[vb.draw_call_uid] = vb
        return vb

    def delete_vertex_buffer(self, buffer: SSVVertexBuffer):
        """
        Removes a vertex buffer from this render buffer, releasing its resources.

        :param buffer: the vertex buffer to remove.
        """
        buff = self._vertex_buffers.pop(buffer.draw_call_uid)
        buff.release()
