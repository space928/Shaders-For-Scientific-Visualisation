#!/usr/bin/env python
# coding: utf-8

#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

from ipywidgets import DOMWidget, CallbackDispatcher
from io import StringIO
from typing import NewType, Callable
from traitlets import Unicode, Enum, Int, Bool
from ._frontend import module_name, module_version


OnMessageDelegate = NewType("OnMessageDelegate", Callable[[], None])
OnClickDelegate = NewType("OnClickDelegate", Callable[[bool, int], None])
OnKeyDelegate = NewType("OnKeyDelegate", Callable[[str, bool], None])
OnWheelDelegate = NewType("OnWheelDelegate", Callable[[float], None])


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
    status_connection = Bool(False).tag(sync=True)
    status_logs = Unicode("").tag(sync=True)
    mouse_pos_x = Int(0).tag(sync=True)
    mouse_pos_y = Int(0).tag(sync=True)
    enable_renderdoc = Bool(False).tag(sync=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._heartbeat_handlers = CallbackDispatcher()
        self._play_handlers = CallbackDispatcher()
        self._stop_handlers = CallbackDispatcher()
        self._click_handlers = CallbackDispatcher()
        self._key_handlers = CallbackDispatcher()
        self._wheel_handlers = CallbackDispatcher()
        self._renderdoc_capture_handlers = CallbackDispatcher()
        self.on_msg(self._handle_widget_msg)
        self._view_count = 0

    def _handle_widget_msg(self, _, content, buffers):
        if "heartbeat" in content and self._view_count > 0:
            self._heartbeat_handlers()
        elif "play" in content:
            self._play_handlers()
        elif "stop" in content:
            self._stop_handlers()
        elif "mousedown" in content:
            self._click_handlers(True, content["mousedown"])
        elif "mouseup" in content:
            self._click_handlers(False, content["mouseup"])
        elif "keydown" in content:
            self._key_handlers(content["keydown"], True)
        elif "keyup" in content:
            self._key_handlers(content["keyup"], False)
        elif "wheel" in content:
            self._wheel_handlers(content["wheel"])
        elif "renderdoc_capture" in content:
            self._renderdoc_capture_handlers()

    def on_heartbeat(self, callback: OnMessageDelegate, remove=False):
        """
        Register a callback to execute when the widget receives a heartbeat from the client.

        :param callback: the function to be called when a heartbeat is received.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._heartbeat_handlers.register_callback(callback, remove=remove)

    def on_play(self, callback: OnMessageDelegate, remove=False):
        """
        Register a callback to execute when the widget's play button is pressed.

        :param callback: the function to be called when the play button is pressed.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._play_handlers.register_callback(callback, remove=remove)

    def on_stop(self, callback: OnMessageDelegate, remove=False):
        """
        Register a callback to execute when the widget's stop button is pressed.

        :param callback: the function to be called when the stop button is pressed.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._stop_handlers.register_callback(callback, remove=remove)

    def on_click(self, callback: OnClickDelegate, remove=False):
        """
        Register a callback to execute when the widget receives a mouseup or mousedown event.

        :param callback: the function to be called when the event is raised.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._click_handlers.register_callback(callback, remove=remove)

    def on_key(self, callback: OnKeyDelegate, remove=False):
        """
        Register a callback to execute when the widget receives a keyup or keydown event.

        :param callback: the function to be called when the event is raised.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._key_handlers.register_callback(callback, remove=remove)

    def on_mouse_wheel(self, callback: OnWheelDelegate, remove=False):
        """
        Register a callback to execute when the widget receives a mouse wheel event.

        :param callback: the function to be called when the event is raised.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._wheel_handlers.register_callback(callback, remove=remove)

    def on_renderdoc_capture(self, callback: OnMessageDelegate, remove=False):
        """
        Register a callback to execute when the widget's renderdoc capture button is pressed.

        :param callback: the function to be called when the event is raised.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._renderdoc_capture_handlers.register_callback(callback, remove=remove)


class SSVRenderWidgetLogIO(StringIO):
    def __init__(self, widget: SSVRenderWidget):
        self._widget = widget

    def write(self, __s: str) -> int:
        self._widget.status_logs = __s
        return len(__s)
