#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import numpy.typing as npt

if TYPE_CHECKING:
    from .ssv_render_process_client import SSVRenderProcessClient
    from .ssv_shader_preprocessor import SSVShaderPreprocessor
    from .ssv_render_buffer import SSVRenderBuffer


class SSVVertexBuffer:
    """
    A lightweight class representing a vertex buffer associated with a draw call.
    """

    def __init__(self, draw_call_uid: Optional[int], render_buffer: SSVRenderBuffer,
                 render_process_client: SSVRenderProcessClient,
                 preprocessor: SSVShaderPreprocessor):
        """
        *Used internally*

        Note that ``SSVVertexBuffer`` objects should be constructed using the factory method on either an ``SSVCanvas``
        or an ``SSVRenderBuffer``.
        """
        self._draw_call_uid = id(self) if draw_call_uid is None else draw_call_uid
        self._render_buffer = render_buffer
        self._render_process_client = render_process_client
        self._preprocessor = preprocessor

        # Create a default vertex buffer when initialised
        self._render_process_client.update_vertex_buffer(self._render_buffer.render_buffer_uid, self._draw_call_uid,
                                                         None, None, None)

    @property
    def draw_call_uid(self):
        """
        Gets the internal uid of this draw call.
        """
        return self._draw_call_uid

    def update_vertex_buffer(self, vertex_array: npt.NDArray,
                             vertex_attributes: tuple[str, ...] = ("in_vert", "in_color"),
                             index_array: Optional[npt.NDArray] = None):
        """
        Updates the data inside a vertex buffer.

        :param vertex_array: a numpy array containing the new vertex data.
        :param index_array: optionally, a numpy array containing the indices of vertices ordered to make triangles.
        :param vertex_attributes: a tuple of the names of the vertex attributes to map to in the shader, in the order
                                  that they appear in the vertex array.
        """
        self._render_process_client.update_vertex_buffer(self._render_buffer.render_buffer_uid, self._draw_call_uid,
                                                         vertex_array, index_array, vertex_attributes)

    def shader(self, shader_source: str, additional_template_directory: Optional[str] = None,
               additional_templates: Optional[list[str]] = None,
               shader_defines: Optional[dict[str, str]] = None,
               compiler_extensions: Optional[list[str]] = None):
        """
        Registers, compiles and attaches a shader to the draw call associated with this vertex buffer.

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
        shaders = self._preprocessor.preprocess(shader_source, None, additional_template_directory,
                                                additional_templates, shader_defines, compiler_extensions)
        self._render_process_client.register_shader(self._render_buffer.render_buffer_uid, self._draw_call_uid,
                                                    **shaders)
