#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Any
import numpy.typing as npt
import logging

from .ssv_logging import log

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
        self._draw_call_uid: int = id(self) if draw_call_uid is None else draw_call_uid
        self._render_buffer = render_buffer
        self._render_process_client = render_process_client
        self._preprocessor = preprocessor
        self._is_valid = True

        # Create a default vertex buffer when initialised
        self._render_process_client.update_vertex_buffer(self._render_buffer.render_buffer_uid, self._draw_call_uid,
                                                         None, None, None)

    @property
    def draw_call_uid(self) -> int:
        """
        Gets the internal uid of this draw call.
        """
        return self._draw_call_uid

    @property
    def is_valid(self) -> bool:
        return self._is_valid

    def __del__(self):
        self.release()

    def release(self):
        """
        Destroys this vertex buffer.
        """
        if not self._is_valid:
            return
            # raise Exception(f"Attempted to delete a vertex buffer which has already been destroyed!")
        self._is_valid = False
        self._render_buffer.delete_vertex_buffer(self)
        self._render_process_client.delete_vertex_buffer(self._render_buffer.render_buffer_uid, self._draw_call_uid)

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
        if not self._is_valid:
            raise Exception(f"Attempted to update a vertex buffer which has already been destroyed!")
        if vertex_array.shape[0] == 0:
            log(f"Vertex array can't be empty!", severity=logging.ERROR)
            return
        if index_array is not None and index_array.shape[0] == 0:
            log(f"Index array can't be empty! Pass None if you don't want to use an index array.",
                severity=logging.ERROR)
            return
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
        if not self._is_valid:
            raise Exception(f"Attempted to register a shader to a vertex buffer which has already been destroyed!")
        shaders = self._preprocessor.preprocess(shader_source, None, additional_template_directory,
                                                additional_templates, shader_defines, compiler_extensions)
        self._render_process_client.register_shader(self._render_buffer.render_buffer_uid, self._draw_call_uid,
                                                    **shaders)

    def update_uniform(self, uniform_name: str, value: Any, share_with_render_buffer: bool = False,
                       share_with_canvas: bool = False) -> None:
        """
        Sets the value of a uniform associated with this draw call.

        :param uniform_name: the name of the uniform to set.
        :param value: the value to set. Must be compatible with the destination uniform.
        :param share_with_render_buffer: update this uniform across all shaders in this render buffer.
        :param share_with_canvas: update this uniform across all shaders in this canvas.
        """
        if not self._is_valid:
            raise Exception(f"Attempted to update a uniform on a vertex buffer which has already been destroyed!")
        self._render_process_client.update_uniform(None if share_with_canvas else self._render_buffer.render_buffer_uid,
                                                   None if share_with_render_buffer else self._draw_call_uid,
                                                   uniform_name, value)
