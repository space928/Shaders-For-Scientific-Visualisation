#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
from multiprocessing import Process, Queue
from queue import Empty
from threading import Thread
from typing import Callable, NewType, Optional

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
                    observer(command_args[0])
                log(command_args[0], raw=True, severity=logging.INFO)
            elif command == "Stop":
                # Render server stopping
                log("Render server shut down.", severity=logging.INFO)
            else:
                log(f"Received unknown command from render process '{command}' with args: {command_args}!",
                    severity=logging.ERROR)

    def subscribe_on_render(self, observer: OnRenderObserverDelegate):
        """

        :param observer:
        :return:
        """
        self._on_render_observers.append(observer)

    def unsubscribe_on_render(self, observer: OnRenderObserverDelegate):
        """

        :param observer:
        :return:
        """
        self._on_render_observers.remove(observer)

    def subscribe_on_log(self, observer: OnRenderObserverDelegate):
        """

        :param observer:
        :return:
        """
        self._on_log_observers.append(observer)

    def unsubscribe_on_log(self, observer: OnRenderObserverDelegate):
        """

        :param observer:
        :return:
        """
        self._on_log_observers.remove(observer)

    def update_frame_buffer(self, buffer_id: int, size: (int, int), pixel_format: int):
        """
        Updates the resolution/format of the given frame buffer. Note that framebuffer 0 is always used for output.
        If the given framebuffer id does not exist, it is created.
        
        :param buffer_id: the id of the framebuffer to update/create. Buffer 0 is the output framebuffer.
        :param size: the new resolution of the framebuffer.
        :param pixel_format: the new pixel format of the framebuffer.
        :return:
        """
        self._command_queue_tx.put(("UFBO", buffer_id, size, pixel_format))

    def delete_frame_buffer(self, buffer_id: int):
        """
        Destroys the given framebuffer. *Note* that framebuffer 0 can't be destroyed as it is the output framebuffer.

        :param buffer_id: the id of the framebuffer to destroy.
        :return:
        """
        self._command_queue_tx.put(("DFBO", buffer_id))

    def render(self, target_framerate: float, stream_mode: str):
        """
        Starts rendering frames at the given framerate.

        :param target_framerate: the framerate to render at. Set to -1 to render a single frame.
        :param stream_mode: the streaming format to use to send the frames to the widget.
        :return:
        """
        self._command_queue_tx.put(("Rndr", target_framerate, stream_mode))

    def stop(self):
        """
        Kills the render process.

        :return:
        """
        self._command_queue_tx.put(("Stop", ))

    def send_heartbeat(self):
        """
        Sends a heartbeat to the render process to keep it alive.

        :return:
        """
        self._command_queue_tx.put(("HrtB",))

    def set_timeout(self, time=1):
        """
        Sets the maximum time the render process will wait for a heartbeat before killing itself.
        Set to None to disable the watchdog.

        :param time: timeout in seconds.
        :return:
        """
        self._command_queue_tx.put(("SWdg", time))

    def update_uniform(self, buffer_id: int, uniform_name: str, value):
        """
        Updates the value of a named shader uniform.

        :param buffer_id: the id of the program of the uniform to update. Set to -1 to update across all buffers.
        :param uniform_name: the name of the shader uniform to update.
        :param value: the new value of the shader uniform. (Must be convertible to GLSL type)
        :return:
        """
        self._command_queue_tx.put(("UpdU", buffer_id, uniform_name, value))

    def update_vertex_buffer(self, buffer_id: int, array: Optional[npt.NDArray]):
        """
        Updates the data inside a vertex buffer.

        :param buffer_id: the buffer_id of the vertex array to update.
        :param array: a numpy array containing the new vertex data.
        :return:
        """
        self._command_queue_tx.put(("UpdV", buffer_id, array))

    def register_shader(self, buffer_id: int, vertex_shader: str, fragment_shader: Optional[str] = None,
                        tess_control_shader: Optional[str] = None, tess_evaluation_shader: Optional[str] = None,
                        geometry_shader: Optional[str] = None, compute_shader: Optional[str] = None):
        """
        Compiles and registers a shader to a given framebuffer.

        :param buffer_id: the framebuffer id to register the shader to.
        :param vertex_shader: the preprocessed vertex shader GLSL source.
        :param fragment_shader: the preprocessed fragment shader GLSL source.
        :param tess_control_shader: the preprocessed tessellation control shader GLSL source.
        :param tess_evaluation_shader: the preprocessed tessellation evaluation shader GLSL source.
        :param geometry_shader: the preprocessed geometry shader GLSL source.
        :param compute_shader: *[Not implemented]* the preprocessed compute shader GLSL source.
        :return:
        """
        self._command_queue_tx.put(("RegS", buffer_id, vertex_shader, fragment_shader, tess_control_shader,
                                    tess_evaluation_shader, geometry_shader, compute_shader))

    def dbg_log_context_info(self, full=False):
        """
        Logs the OpenGL information to the console for debugging.

        :param full: whether to log *all* of the OpenGL context information (including extensions).
        """
        self._command_queue_tx.put(("LogC", full))

    def dbg_render_test(self):
        """
        *[For debugging only]* Sets up the pipeline to render with a demo shader.

        :return:
        """
        self._command_queue_tx.put(("DbRT",))

    def dbg_render_command(self, command: str, *args):
        """
        *[For debugging only]* Sends a custom command to the render process.

        :param command: the custom command to send
        :param args: the arguments to send with the command
        :return:
        """
        self._command_queue_tx.put((command, *args))
