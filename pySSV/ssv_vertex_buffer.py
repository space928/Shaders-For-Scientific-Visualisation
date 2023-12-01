#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

from .ssv_render_process_client import SSVRenderProcessClient


class SSVVertexBuffer:
    """

    """

    def __init__(self, vertex_buffer_id: int, render_process_client: SSVRenderProcessClient, render_buffer_id: int):
        """
        *Used internally*

        Note that ``SSVVertexBuffer`` objects should be constructed using the factory method on either an ``SSVCanvas``
        or an ``SSVRenderBuffer``.

        :param render_process_client:
        """
        self._vertex_buffer_id = vertex_buffer_id
        self._render_process_client = render_process_client
        self._render_buffer_id = render_buffer_id

    @property
    def vertex_buffer_id(self):
        return self._vertex_buffer_id

    def update_vertex_buffer(self, vertex_array):
        self._render_process_client.update_vertex_buffer(self._render_buffer_id, vertex_array)

    def shader(self):
        ...
