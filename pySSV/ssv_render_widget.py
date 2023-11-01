#!/usr/bin/env python
# coding: utf-8

#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

from ipywidgets import DOMWidget, CallbackDispatcher
from traitlets import Unicode, Enum, Int
from ._frontend import module_name, module_version


class SSVRenderWidget(DOMWidget):
    """
    An SSV Render Widget manages the state and communication of the Jupyter Widget responsible for displaying rendered
    results embedded in a Jupyter notebook.
    """
    _model_name = Unicode('SSVRenderModel').tag(sync=True)
    _model_module = Unicode(module_name).tag(sync=True)
    _model_module_version = Unicode(module_version).tag(sync=True)
    _view_name = Unicode('SSVRenderView').tag(sync=True)
    _view_module = Unicode(module_name).tag(sync=True)
    _view_module_version = Unicode(module_version).tag(sync=True)

    streaming_mode = Enum(("png", "jpg", "h264"), "png").tag(sync=True)
    stream_data = Unicode("test").tag(sync=True)
    mouse_pos_x = Int(0).tag(sync=True)
    mouse_pos_y = Int(0).tag(sync=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._heartbeat_handlers = CallbackDispatcher()
        self.on_msg(self._handle_widget_msg)

    def _handle_widget_msg(self, _, content, buffers):
        if content.get('event', '') == 'heartbeat':
            self._heartbeat_handlers()

    def on_heartbeat(self, callback, remove=False):
        """
        Register a callback to execute when the widget receives a heartbeat from th client.

        :param callback: the function to be called when a heartbeat is received.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._heartbeat_handlers.register_callback(callback, remove=remove)
