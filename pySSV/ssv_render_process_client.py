#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
from multiprocessing import Process, Queue, set_start_method
from queue import Empty
from threading import Thread, Lock
from typing import Callable, Optional, Any, Union, Set, Tuple, Dict, List
import sys
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

import numpy as np
import numpy.typing as npt

from . import ssv_logging
from .ssv_future import Future
from .ssv_logging import log
from .ssv_render import SSVStreamingMode
from .ssv_render_process_server import SSVRenderProcessServer
from .environment import ENVIRONMENT, Env


OnRenderObserverDelegate: TypeAlias = Callable[[bytes], None]
OnLogObserverDelegate: TypeAlias = Callable[[str], None]


class SSVRenderProcessClient:
    """
    This class creates, manages, and provides a communication interface for the render process (an
    ``SSVRenderProcessServer``).
    """

    def __init__(self, backend: str, gl_version: Optional[int] = None, timeout: Optional[float] = 1,
                 use_renderdoc_api: bool = False):
        """
        Initialises a new Render Process Client and starts the render process.

        :param backend: the rendering backend to use.
        :param gl_version: optionally, the minimum version of OpenGL to support.
        :param timeout: the render process watchdog timeout, set to None to disable.
        :param use_renderdoc_api: whether the renderdoc_api should be initialised.
        """
        self._command_queue_tx: Queue[Tuple[Any, ...]] = Queue()
        self._command_queue_rx: Queue[Tuple[Any, ...]] = Queue()
        self._query_futures: Dict[int, Future] = dict()
        self._query_future_id_counter = 0
        self._query_futures_lock = Lock()
        self._rx_thread = Thread(target=self.__rx_thread_process, daemon=True,
                                 name=f"SSV Render Process Client RX Thread - {id(self):#08x}")
        self._rx_thread.start()
        self._on_render_observers: List[OnRenderObserverDelegate] = []
        self._on_log_observers: List[OnLogObserverDelegate] = []

        # Set the multiprocessing start method
        if ENVIRONMENT != Env.COLAB:
            try:
                set_start_method("spawn")
            except RuntimeError:
                pass

        # Construct the render process server in its own process, passing it the backend string and the command queues
        # (note that the rx and tx queues are flipped here, the rx queue of the server is the tx queue of the client)
        self._render_process = Process(target=SSVRenderProcessServer, daemon=True,
                                       name=f"SSV Render Process - {id(self):#08x}",
                                       args=(backend, gl_version, self._command_queue_rx, self._command_queue_tx,
                                             ssv_logging.get_severity(), timeout, use_renderdoc_api))
        self._render_process.start()
        self._is_alive = True

    def __del__(self):
        self._render_process.kill()
        self._render_process.close()

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
            elif command == "ARes":
                # Async result
                with self._query_futures_lock:
                    if command_args[0] in self._query_futures:
                        res = command_args[1:] if len(command_args) > 2 else command_args[1]
                        self._query_futures[command_args[0]].set_result(res)
                        del self._query_futures[command_args[0]]
            else:
                log(f"Received unknown command from render process '{command}' with args: {command_args}!",
                    severity=logging.ERROR)

    def __create_async_query(self, command: str, *args) -> Future[Any]:
        """
        Runs a command which returns an async result and waits for its result to be returned.

        :param command: the command to run.
        :param args: any additional args to pass to the command.
        :return: the result of the async query command.
        """
        # While dictionaries are atomic in python, it's still a good idea to use a lock
        with self._query_futures_lock:
            result: Future[Any] = Future()
            query_id = self._query_future_id_counter
            self._query_future_id_counter += 1
            self._query_futures[query_id] = result

        self._command_queue_tx.put((command, query_id, *args))
        return result

    @property
    def is_alive(self):
        return self._is_alive and self._render_process.is_alive()

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

    def subscribe_on_log(self, observer: OnLogObserverDelegate):
        """
        Subscribes an event handler to the on_log event, triggered when the render process logs a message.

        :param observer: a function to handle the event (must have the signature: `callback(data: bytes) -> None`).
        """
        self._on_log_observers.append(observer)

    def unsubscribe_on_log(self, observer: OnLogObserverDelegate):
        """
        Unsubscribes an event handler from the on_log event.

        :param observer: a function currently registered to handle the event.
        """
        self._on_log_observers.remove(observer)

    def update_frame_buffer(self, frame_buffer_uid: int, order: Optional[int], size: Optional[Tuple[int, int]],
                            uniform_name: Optional[str], components: Optional[int] = 4,
                            dtype: Optional[str] = "f1"):
        """
        Updates the resolution/format of the given frame buffer. Note that framebuffer 0 is always used for output.
        If the given framebuffer id does not exist, it is created.

        Setting a parameter to ``None`` preserves the current value for that frame buffer.

        :param frame_buffer_uid: the uid of the framebuffer to update/create. Buffer 0 is the output framebuffer.
        :param order: the sorting order to render the frame buffers in, smaller values are rendered first.
        :param size: the new resolution of the framebuffer.
        :param uniform_name: the name of the uniform to bind this frame buffer to.
        :param components: how many vector components should each pixel have (RGB=3, RGBA=4).
        :param dtype: the data type for each pixel component (see:
                      https://moderngl.readthedocs.io/en/5.8.2/topics/texture_formats.html).
        """
        self._command_queue_tx.put(("UFBO", frame_buffer_uid, order, size, uniform_name, components, dtype))

    def delete_frame_buffer(self, buffer_uid: int):
        """
        Destroys the given framebuffer. *Note* that framebuffer 0 can't be destroyed as it is the output framebuffer.

        :param buffer_uid: the id of the framebuffer to destroy.
        """
        self._command_queue_tx.put(("DFBO", buffer_uid))

    def render(self, target_framerate: float, stream_mode: str, encode_quality: Optional[float] = None):
        """
        Starts rendering frames at the given framerate.

        :param target_framerate: the framerate to render at. Set to -1 to render a single frame.
        :param stream_mode: the streaming format to use to send the frames to the widget.
        :param encode_quality: the encoding quality to use for the given encoding format. Takes a float between 0-100
                               (some stream modes support values larger than 100, others clamp it internally), where 100
                               results in the highest quality. This value is scaled to give a bit rate target or
                               quality factor for the chosen encoder. Pass in ``None`` to use the encoder's default
                               quality settings.
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

    def set_timeout(self, time: Optional[float] = 1):
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
        if isinstance(value, np.ndarray):
            if len(value.shape) > 1:
                value = value.flatten()
        self._command_queue_tx.put(("UpdU", frame_buffer_uid, draw_call_uid, uniform_name, value))

    def update_vertex_buffer(self, frame_buffer_uid: int, draw_call_uid: int,
                             vertex_array: Optional[npt.NDArray], index_array: Optional[npt.NDArray],
                             vertex_attributes: Optional[Tuple[str, ...]]):
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

    def delete_vertex_buffer(self, frame_buffer_uid: int, draw_call_uid: int):
        """
        Deletes an existing vertex buffer.

        :param frame_buffer_uid: the uid of the framebuffer of the vertex buffer to delete.
        :param draw_call_uid: the uid of the draw call of the vertex buffer to delete.
        """
        self._command_queue_tx.put(("DelV", frame_buffer_uid, draw_call_uid))

    def update_texture(self, texture_uid: int, data: npt.NDArray, uniform_name: Optional[str],
                       override_dtype: Optional[str],
                       rect: Optional[Union[Tuple[int, int, int, int], Tuple[int, int, int, int, int, int]]],
                       treat_as_normalized_integer: bool):
        """
        Creates or updates a texture from the NumPy array provided.

        :param texture_uid: the uid of the texture to create or update.
        :param data: a NumPy array containing the image data to copy to the texture.
        :param uniform_name: the name of the shader uniform to associate this texture with.
        :param override_dtype: Optionally, a moderngl override
        :param rect: optionally, a rectangle (left, top, right, bottom) specifying the area of the target texture to
                     update.
        :param treat_as_normalized_integer: when enabled, integer types (singed/unsigned) are treated as normalized
                                            integers by OpenGL, such that when the texture is sampled values in the
                                            texture are mapped to floats in the range [0, 1] or [-1, 1]. See:
                                            https://www.khronos.org/opengl/wiki/Normalized_Integer for more details.
        """
        # TODO: Optimise data transport by using shared buffers
        self._command_queue_tx.put(("UpdT", texture_uid, data, uniform_name, override_dtype, rect,
                                    treat_as_normalized_integer))

    def update_texture_sampler(self, texture_uid: int, repeat_x: Optional[bool] = None, repeat_y: Optional[bool] = None,
                               linear_filtering: Optional[bool] = None, linear_mipmap_filtering: Optional[bool] = None,
                               anisotropy: Optional[int] = None,
                               build_mip_maps: bool = False):
        """
        Updates a texture's sampling settings. Parameters set to ``None`` are not updated.

        :param texture_uid: the uid of the texture to update.
        :param repeat_x: whether the texture should repeat or be clamped in the x-axis.
        :param repeat_y: whether the texture should repeat or be clamped in the y-axis.
        :param linear_filtering: whether the texture should use nearest neighbour (``False``) or linear (``True``)
                                 interpolation.
        :param linear_mipmap_filtering: whether different mipmap levels should blend linearly (``True``) or not
                                        (``False``).
        :param anisotropy: the number of anisotropy samples to use. (minimum of 1 = disabled, maximum of 16)
        :param build_mip_maps: when set to ``True``, immediately builds mipmaps for the texture.
        """
        self._command_queue_tx.put(("UpdS", texture_uid, repeat_x, repeat_y, linear_filtering, linear_mipmap_filtering,
                                    anisotropy, build_mip_maps))

    def delete_texture(self, texture_uid: int):
        """
        Destroys the given texture object.

        :param texture_uid: the uid of the texture to destroy.
        """
        self._command_queue_tx.put(("DelT", texture_uid))

    def register_shader(self, frame_buffer_uid: int, draw_call_uid: int,
                        vertex_shader: str, fragment_shader: Optional[str] = None,
                        tess_control_shader: Optional[str] = None, tess_evaluation_shader: Optional[str] = None,
                        geometry_shader: Optional[str] = None, compute_shader: Optional[str] = None,
                        primitive_type: Optional[str] = None):
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
        :param primitive_type: what type of input primitive to treat the vertex data as. One of ("TRIANGLES", "LINES",
                               "POINTS), defaults to "TRIANGLES" if ``None``.
        """
        self._command_queue_tx.put(("RegS", frame_buffer_uid, draw_call_uid, vertex_shader, fragment_shader,
                                    tess_control_shader, tess_evaluation_shader, geometry_shader, compute_shader,
                                    primitive_type))

    def renderdoc_capture_frame(self, filename: Optional[str]):
        """
        Triggers a frame capture with Renderdoc if it's initialised.

        :param filename: optionally, the filename and path to save the capture with.
        """
        self._command_queue_tx.put(("RdCp", filename))

    def set_start_time(self, start_time: float) -> None:
        """
        Sets the renderer's start time; this is used by the renderer to compute the canvas time which is injected into
        shaders.

        :param start_time: the start time of the renderer in seconds since the start of the epoch.
        """
        self._command_queue_tx.put(("StTm", start_time))

    def get_context_info(self, timeout: Optional[float] = None) -> Optional[Dict[str, str]]:
        """
        Returns the OpenGL context information.

        :param timeout: the maximum amount of time in seconds to wait for the result. Set to ``None`` to wait
                        indefinitely.
        """
        return self.__create_async_query("GtCt").wait_result(timeout)

    def get_frame_times(self, timeout: Optional[float] = None) -> Optional[Tuple[float, float, float, float]]:
        """
        Gets the frame time statistics from the renderer. This function is blocking and shouldn't be called too often.

        Returns the following statistics:
         - avg_frame_time: Average time taken to render a frame (calculated each
           frame using: ``last_avg_frame_time * 0.9 + frame_time * 0.1``)
         - max_frame_time: The maximum frame time since this
           function was last called. (Using ``dbg_log_frame_times`` interferes with this value.)
         - avg_encode_time: Average time taken to encode a frame for streaming (calculated each
           frame using: ``last_avg_encode_time * 0.9 + encode_time * 0.1``)
         - max_encode_time: The maximum time taken to encode a frame for streaming since this
           function was last called. (Using ``dbg_log_frame_times`` interferes with this value.)

        :param timeout: the maximum amount of time in seconds to wait for the result. Set to ``None`` to wait
                        indefinitely.
        :return: (avg_frame_time, max_frame_time, avg_encode_time, max_encode_time)
        """
        return self.__create_async_query("GtFt").wait_result(timeout)

    def get_supported_extensions(self, timeout: Optional[float] = None) -> Optional[Set[str]]:
        """
        Gets the set of supported OpenGL shader compiler extensions.

        :param timeout: the maximum amount of time in seconds to wait for the result. Set to ``None`` to wait
                        indefinitely.
        """
        return self.__create_async_query("GtEx").wait_result(timeout)

    def save_image(self, image_type: SSVStreamingMode, quality: float, size: Optional[Tuple[int, int]],
                   render_buffer: int, suppress_ui: bool) -> Future[bytes]:
        """
        Saves the current frame as an image.

        :param image_type: the image compression algorithm to use.
        :param quality: the encoding quality to use for the given encoding format. Takes a float between 0-100
                        (some stream modes support values larger than 100, others clamp it internally), where 100
                        results in the highest quality. This value is scaled to give a bit rate target or
                        quality factor for the chosen encoder.
        :param size: optionally, the width and height of the saved image. If set to ``None`` uses the current
                     resolution of the render buffer.
        :param render_buffer: the uid of the render buffer to save.
        :param suppress_ui: whether any active SSVGUIs should be suppressed.
        :return: the bytes representing the compressed image.
        """
        return self.__create_async_query("SvIm", image_type, quality, size, render_buffer, suppress_ui)

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
