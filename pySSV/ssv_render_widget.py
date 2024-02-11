#!/usr/bin/env python
# coding: utf-8

#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

from ipywidgets import DOMWidget, CallbackDispatcher  # type: ignore
import logging
from io import TextIOBase
from typing import Callable, Optional, Tuple
import sys
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias
from traitlets import Unicode, Enum, Int, Bool, Float, Bytes  # type: ignore
from ._frontend import module_name, module_version
from .ssv_render import SSVStreamingMode
from .ssv_logging import log


OnMessageDelegate: TypeAlias = Callable[[], None]
OnClickDelegate: TypeAlias = Callable[[bool, int], None]
OnKeyDelegate: TypeAlias = Callable[[str, bool], None]
OnWheelDelegate: TypeAlias = Callable[[float], None]
OnSaveImageDelegate: TypeAlias = Callable[[SSVStreamingMode, float, Optional[Tuple[int, int]], int, bool], None]
"""
A callable with parameters matching the signature::

    on_save_image(image_type: SSVStreamingMode, quality: float, size: Optional[Tuple[int, int]], render_buffer: int):
        ...
        
| image_type: the image codec to save the image with.
| quality: a value between 0-100, indicating the image quality (larger values are higher quality). For ``png`` this 
           represents compression quality (higher values result in smaller files, but take longer to compress).
| size: the resolution of the saved image. When set to ``None``, uses the current resolution of the render buffer (this 
        also prevents an additional frame from being rendered).
| render_buffer: the uid of the render buffer to save.
| suppress_ui: whether any active SSVGUIs should be supressed.
"""


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

    streaming_mode = Enum([e.name for e in SSVStreamingMode], SSVStreamingMode.JPG.name).tag(sync=True)
    stream_data_binary = Bytes(b"test").tag(sync=True)
    stream_data_ascii = Unicode("test").tag(sync=True)
    use_websockets = Bool(False).tag(sync=True)
    websocket_url = Unicode("").tag(sync=True)
    canvas_width = Int(0).tag(sync=True)
    canvas_height = Int(0).tag(sync=True)
    status_connection = Bool(False).tag(sync=True)
    status_logs = Unicode("").tag(sync=True)
    mouse_pos_x = Int(0).tag(sync=True)
    mouse_pos_y = Int(0).tag(sync=True)
    enable_renderdoc = Bool(False).tag(sync=True)
    frame_rate = Float(0).tag(sync=True)
    frame_times = Unicode("").tag(sync=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._heartbeat_handlers = CallbackDispatcher()
        self._play_handlers = CallbackDispatcher()
        self._stop_handlers = CallbackDispatcher()
        self._click_handlers = CallbackDispatcher()
        self._key_handlers = CallbackDispatcher()
        self._wheel_handlers = CallbackDispatcher()
        self._img_save_handlers = CallbackDispatcher()
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
        elif "save_image" in content:
            settings = content["save_image"]
            stream_mode = settings["image_type"]
            try:
                stream_mode = SSVStreamingMode(stream_mode)
            except ValueError:
                raise KeyError(f"'{stream_mode}' is not a valid streaming mode. Supported streaming modes are: "
                               f"{[e.value for e in SSVStreamingMode]}")
            size = None if settings["size"] is None else (settings["size"]["width"], settings["size"]["height"])
            self._img_save_handlers(stream_mode, settings["quality"], size, settings["render_buffer"],
                                    settings["suppress_ui"])

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

    def on_save_image(self, callback: OnSaveImageDelegate, remove=False):
        """
        Register a callback to execute when the widget's 'save image' button is pressed.

        :param callback: the function to be called when the event is raised.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._img_save_handlers.register_callback(callback, remove=remove)

    def on_renderdoc_capture(self, callback: OnMessageDelegate, remove=False):
        """
        Register a callback to execute when the widget's renderdoc capture button is pressed.

        :param callback: the function to be called when the event is raised.
        :param remove: set to true to remove the callback from the list of callbacks.
        """
        self._renderdoc_capture_handlers.register_callback(callback, remove=remove)

    def download_file(self, filename: str, data: bytes):
        """
        Triggers a file download in the client's web browser.

        :param filename: the file name of the file to download.
        :param data: the data to be downloaded.
        """
        self.send({"download_file": {"name": filename, "length": len(data)}}, buffers=[data])


class SSVRenderWidgetLogIO(TextIOBase):
    def __init__(self, widget: SSVRenderWidget):
        self._widget = widget

    def write(self, __s: str) -> int:
        self._widget.status_logs = __s
        return len(__s)
