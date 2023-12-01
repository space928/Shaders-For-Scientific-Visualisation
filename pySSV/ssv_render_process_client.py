#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
from multiprocessing import Process, Queue
from queue import Empty
from threading import Thread
from typing import Callable, NewType, Optional, Any

import numpy.typing as npt

from . import ssv_logging
from .ssv_logging import log
from .ssv_render_process_server import SSVRenderProcessServer


OnRenderObserverDelegate = NewType("OnRenderObserverDelegate", Callable[[bytes], None])
OnLogObserverDelegate = NewType("OnLogObserverDelegate", Callable[[str], None])


class SSVRenderProcessClient:
    """
    This class creates, manages, and provides a communication interface for the render process (an
    ``SSVRenderProcessServer``).
    """

    def __init__(self, backend, timeout=1):
        """
        Initialises a new Render Process Client and starts the render process.

        :param backend: the rendering backend to use.
        :param timeout: the render process watchdog timeout, set to None to disable.
        """
        self._command_queue_tx = Queue()
        self._command_queue_rx = Queue()
        self._rx_thread = Thread(target=self.__rx_thread_process, daemon=True)
        self._rx_thread.start()
        self._on_render_observers: list[OnRenderObserverDelegate] = []
        self._on_log_observers: list[OnLogObserverDelegate] = []

        # Construct the render process server in its own process, passing it the backend string and the command queues
        # (note that the rx and tx queues are flipped here, the rx queue of the server is the tx queue of the client)
        self._render_process = Process(target=SSVRenderProcessServer, daemon=True,
                                       args=(backend, self._command_queue_rx, self._command_queue_tx,
                                             ssv_logging.get_severity(), timeout))
        self._render_process.start()
        self._is_alive = True

    def __rx_thread_process(self):
        while True:
            try:
                command, *command_args = self._command_queue_rx.get(block=True)
            except Empty:
                command = None
                command_args = None

            if command == "NFrm":
                # New frame data is available
                for observer in self._on_render_observers:
                    observer(command_args[0])
            elif command == "LogM":
                # Log message
                for observer in self._on_log_observers:
                    observer(command_args[1])
                log(command_args[1], raw=True, severity=command_args[0])
            elif command == "Stop":
                # Render server stopping
                log("Render server shut down.", severity=logging.INFO)
                self._is_alive = False
            else:
                log(f"Received unknown command from render process '{command}' with args: {command_args}!",
                    severity=logging.ERROR)

    @property
    def is_alive(self):
        return self._is_alive

    def subscribe_on_render(self, observer: OnRenderObserverDelegate):
        """
        Subscribes an event handler to the on_render event, triggered after each frame is rendered.

        :param observer: a function to handle the event (must have the signature: `callback(data: bytes) -> None`).
        """
        self._on_render_observers.append(observer)

    def unsubscribe_on_render(self, observer: OnRenderObserverDelegate):
        """
        Unsubscribes an event handler from the on_render event.

        :param observer: a function currently registered to handle the event.
        """
        self._on_render_observers.remove(observer)

    def subscribe_on_log(self, observer: OnRenderObserverDelegate):
        """
        Subscribes an event handler to the on_log event, triggered when the render process logs a message.

        :param observer: a function to handle the event (must have the signature: `callback(data: bytes) -> None`).
        """
        self._on_log_observers.append(observer)

    def unsubscribe_on_log(self, observer: OnRenderObserverDelegate):
        """
        Unsubscribes an event handler from the on_log event.

        :param observer: a function currently registered to handle the event.
        """
        self._on_log_observers.remove(observer)

    def update_frame_buffer(self, buffer_id: int, size: (int, int), pixel_format: int):
        """
        Updates the resolution/format of the given frame buffer. Note that framebuffer 0 is always used for output.
        If the given framebuffer id does not exist, it is created.
        
        :param buffer_id: the id of the framebuffer to update/create. Buffer 0 is the output framebuffer.
        :param size: the new resolution of the framebuffer.
        :param pixel_format: the new pixel format of the framebuffer.
        """
        self._command_queue_tx.put(("UFBO", buffer_id, size, pixel_format))

    def delete_frame_buffer(self, buffer_id: int):
        """
        Destroys the given framebuffer. *Note* that framebuffer 0 can't be destroyed as it is the output framebuffer.

        :param buffer_id: the id of the framebuffer to destroy.
        """
        self._command_queue_tx.put(("DFBO", buffer_id))

    def render(self, target_framerate: float, stream_mode: str, encode_quality: Optional[int] = None):
        """
        Starts rendering frames at the given framerate.

        :param target_framerate: the framerate to render at. Set to -1 to render a single frame.
        :param stream_mode: the streaming format to use to send the frames to the widget.
        :param encode_quality: the quality value for the stream encoder. When using jpg, setting to 100 disables
                               compression; when using png, setting to 0 disables compression.
        """
        self._command_queue_tx.put(("Rndr", target_framerate, stream_mode, encode_quality))

    def stop(self):
        """
        Kills the render process.
        """
        self._command_queue_tx.put(("Stop", ))

    def send_heartbeat(self):
        """
        Sends a heartbeat to the render process to keep it alive.
        """
        self._command_queue_tx.put(("HrtB",))

    def set_timeout(self, time=1):
        """
        Sets the maximum time the render process will wait for a heartbeat before killing itself.
        Set to None to disable the watchdog.

        :param time: timeout in seconds.
        """
        self._command_queue_tx.put(("SWdg", time))

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
        self._command_queue_tx.put(("UpdU", frame_buffer_uid, draw_call_uid, uniform_name, value))

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
        self._command_queue_tx.put(("UpdV", frame_buffer_uid, draw_call_uid, vertex_array, index_array,
                                    vertex_attributes))

    def update_texture(self, texture_uid: int, data: npt.NDArray, rect: Optional[tuple[int, int, int, int]]):
        """
        Creates or updates a texture from the NumPy array provided.

        :param texture_uid: the uid of the texture to create or update.
        :param data: a NumPy array containing the image data to copy to the texture.
        :param rect: optionally, a rectangle (left, top, right, bottom) specifying the area of the target texture to
                     update.
        """
        self._command_queue_tx.put(("UpdT", texture_uid, data, rect))

    def delete_texture(self, texture_uid: int):
        """
        Destroys the given texture object.

        :param texture_uid: the uid of the texture to destroy.
        """
        self._command_queue_tx.put(("DelT", texture_uid))

    def register_shader(self, frame_buffer_uid: int, draw_call_uid: int,
                        vertex_shader: str, fragment_shader: Optional[str] = None,
                        tess_control_shader: Optional[str] = None, tess_evaluation_shader: Optional[str] = None,
                        geometry_shader: Optional[str] = None, compute_shader: Optional[str] = None):
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
        self._command_queue_tx.put(("RegS", frame_buffer_uid, draw_call_uid, vertex_shader, fragment_shader,
                                    tess_control_shader, tess_evaluation_shader, geometry_shader, compute_shader))

    def dbg_log_context_info(self, full=False):
        """
        Logs the OpenGL information to the console for debugging.

        :param full: whether to log *all* of the OpenGL context information (including extensions).
        """
        self._command_queue_tx.put(("LogC", full))

    def dbg_log_frame_times(self, enabled=True):
        """
        Enables or disables frame time logging.

        :param enabled: whether to log frame times.
        """
        self._command_queue_tx.put(("LogT", enabled))

    def dbg_render_test(self):
        """
        **DEPRECATED**

        *[For debugging only]* Sets up the pipeline to render with a demo shader.
        """
        self._command_queue_tx.put(("DbRT",))

    def dbg_render_command(self, command: str, *args):
        """
        *[For debugging only]* Sends a custom command to the render process.

        :param command: the custom command to send
        :param args: the arguments to send with the command
        """
        self._command_queue_tx.put((command, *args))
