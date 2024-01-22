#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
from typing import Optional, Any, Union, Callable, NewType, Type
import asyncio
import numpy.typing as npt
try:
    from PIL import Image
    _PIL_SUPPORTED = True
except ImportError:
    Image = None
    _PIL_SUPPORTED = False

from .ssv_camera import SSVCameraController, SSVOrbitCameraController, SSVLookCameraController, MoveDir
from .ssv_render_process_client import SSVRenderProcessClient
from .ssv_render_process_server import SSVStreamingMode
from .ssv_render_widget import SSVRenderWidget, SSVRenderWidgetLogIO
from .ssv_shader_preprocessor import SSVShaderPreprocessor
from .ssv_logging import log, set_output_stream
from .ssv_render_buffer import SSVRenderBuffer
from .ssv_texture import SSVTexture
from .ssv_callback_dispatcher import SSVCallbackDispatcher
from .ssv_canvas_stream_server import SSVCanvasStreamServer
from .environment import ENVIRONMENT, Env


OnMouseDelegate = NewType("OnMouseDelegate", Callable[[tuple[bool, bool, bool], tuple[int, int], float], None])
"""
A callable with parameters matching the signature::

    on_mouse(mouse_down: tuple[bool, bool, bool], mouse_pos: tuple[int, int], mouse_wheel_delta: float) -> None:
        ...
        
| mouse_down: a tuple of booleans representing the mouse button state (left, right, middle).
| mouse_pos: a tuple of ints representing the mouse position relative to the canvas in pixels.
| mouse_wheel_delta: how many pixels the mousewheel has scrolled since the last callback.
"""
OnKeyDelegate = NewType("OnKeyDelegate", Callable[[str, bool], None])
"""
A callable with parameters matching the signature::

    on_key(key: str, down: bool) -> None:
        ...
        
| key: the name of key in this event. Possible values can be found here: 
       https://developer.mozilla.org/en-US/docs/Web/API/UI_Events/Keyboard_event_key_values
| down: whether the key is being pressed.
"""


class SSVCanvas:
    """
    An SSV canvas manages the OpenGL rendering context, shaders, and the jupyter widget
    """

    def __init__(self, size: Optional[tuple[int, int]], backend: str = "opengl", standalone: bool = False,
                 target_framerate: int = 60, use_renderdoc: bool = False,
                 supports_line_directives: Optional[bool] = None):
        """
        Creates a new SSV Canvas object which manages the graphics context and render widget/window.

        :param size: the default resolution of the renderer as a tuple: ``(width: int, height: int)``.
        :param backend: the rendering backend to use; currently supports: ``"opengl"``.
        :param standalone: whether the canvas should run standalone, or attempt to create a Jupyter Widget for
                           rendering.
        :param target_framerate: the default framerate to target when running.
        :param use_renderdoc: optionally, an instance of the Renderdoc in-app api to provide support for frame
                               capturing and analysis in renderdoc.
        :param supports_line_directives: whether the shader compiler supports ``#line`` directives (Nvidia GPUs only).
                                         Set to ``None`` for automatic detection. If you get
                                         'extension not supported: GL_ARB_shading_language_include' errors, set this to
                                         ``False``.
        """
        if size is None:
            size = (640, 480)
        self._size = size
        self._standalone = standalone
        self._target_framerate = target_framerate
        self._streaming_mode = SSVStreamingMode.JPG
        self._backend = backend
        self._use_renderdoc = False
        self._on_mouse_event: SSVCallbackDispatcher[OnMouseDelegate] = SSVCallbackDispatcher()
        self._on_keyboard_event: SSVCallbackDispatcher[OnKeyDelegate] = SSVCallbackDispatcher()
        self._on_frame_rendered: SSVCallbackDispatcher[Callable[[], None]] = SSVCallbackDispatcher()
        self._on_start: SSVCallbackDispatcher[Callable[[], None]] = SSVCallbackDispatcher()
        if use_renderdoc:
            try:
                from pyRenderdocApp import RENDERDOC_API_1_6_0
                self._use_renderdoc = True
            except ImportError:
                log("Couldn't find pyRenderdocApp module! Renderdoc will not be loaded.", severity=logging.WARN)
        self._widget = None
        if not standalone:
            self._widget = SSVRenderWidget()
            self._widget.streaming_mode = self._streaming_mode
            self._widget.enable_renderdoc = self._use_renderdoc
            self._widget.on_heartbeat(self.__on_heartbeat)
            self._widget.on_play(self.__on_play)
            self._widget.on_stop(self.__on_stop)
            self._widget.on_key(self.__on_key)
            self._widget.on_click(self.__on_click)
            self._widget.on_mouse_wheel(self.__on_mouse_wheel)
            if self._use_renderdoc:
                self._widget.on_renderdoc_capture(self.__on_renderdoc_capture)
            self._update_frame_rate_task: Optional[asyncio.Task] = None
            self._set_logging_stream()
            # set_output_stream(sys.stdout)
        self._render_timeout = 10
        self._render_process_client = SSVRenderProcessClient(backend, None if standalone else self._render_timeout,
                                                             self._use_renderdoc)
        if supports_line_directives is None:
            supported_extensions = self._render_process_client.get_supported_extensions()
            supports_line_directives = "GL_ARB_shading_language_include" in supported_extensions
        self._preprocessor = SSVShaderPreprocessor(gl_version="420", supports_line_directives=supports_line_directives)

        self._supports_websockets = ENVIRONMENT != Env.COLAB or ENVIRONMENT != Env.JUPYTERLITE
        self._websocket_url = None
        self._canvas_stream_server = None
        if self._supports_websockets:
            self._canvas_stream_server = SSVCanvasStreamServer()
        self._canvas_mjpg_stream_server = SSVCanvasStreamServer(http=True)

        self._mouse_pos = (0, 0)
        self._mouse_down = (False, False, False)
        # Cache the last parameters to the run() method for the widget's "play" button to use
        self._last_run_settings = {}

        # Set up a default render buffer
        self._main_render_buffer = SSVRenderBuffer(self, self._render_process_client, self._preprocessor,
                                                   0, "main_render_buffer",
                                                   999999, size, "f1", 4)
        self._render_buffer_counter = 1
        self._main_camera = SSVOrbitCameraController()
        self._main_camera.aspect_ratio = size[1] / size[0]
        self._textures: dict[str, SSVTexture] = {}

    def __del__(self):
        self.stop()
        self._render_process_client.stop()

    async def __update_frame_rate(self):
        """
        An async task to periodically update the frame rate display in the widget.
        """
        while self._render_process_client.is_alive:
            frame_times = self._render_process_client.get_frame_times(10)
            if frame_times is not None:
                self._widget.frame_rate = min(1 / (frame_times[0] + frame_times[2]),
                                              self._target_framerate)  # Avg frame+encode
                self._widget.frame_times = (
                    f"Avg {frame_times[0] * 1000:.3f} ms;Avg encode {frame_times[2] * 1000:.3f} ms;"
                    f"Max {frame_times[1] * 1000:.3f} ms;Max encode {frame_times[3] * 1000:.3f} ms")
            else:
                self._widget.frame_rate = 0
                self._widget.frame_times = "Took longer than 10s to get stats;;;"
            await asyncio.sleep(0.5)

    def __on_render(self, stream_data: bytes):
        if self._streaming_mode == SSVStreamingMode.MJPEG and self._canvas_mjpg_stream_server is not None:
            self._canvas_mjpg_stream_server.send(stream_data)
        elif self._supports_websockets and self._canvas_stream_server is not None:
            # log(f"Sending frame len={len(stream_data)}", severity=logging.INFO)
            self._canvas_stream_server.send(stream_data)
        else:
            self._widget.stream_data = stream_data
            # log(f"Sending frame len={len(stream_data)}", severity=logging.INFO)
            # self._widget.send({"stream_data": len(stream_data)}, buffers=[stream_data])

    def __on_heartbeat(self):
        self._render_process_client.send_heartbeat()
        self._widget.status_connection = self._render_process_client.is_alive

    def __on_play(self):
        self.run(**self._last_run_settings)

    def __on_stop(self):
        self.stop()

    def __on_click(self, down: bool, button: int):
        self._mouse_down = (self._mouse_down[0] if button != 0 else down,
                            self._mouse_down[1] if button != 1 else down,
                            self._mouse_down[2] if button != 2 else down)
        self._render_process_client.update_uniform(None, None, "uMouseDown", down)
        self._main_camera.mouse_change(self._mouse_pos, self._mouse_down)
        self._render_process_client.update_uniform(None, None, "uViewMat", self._main_camera.view_matrix)
        self._on_mouse_event(self._mouse_down, self._mouse_pos, 0)

    def __on_key(self, key: str, down: bool):
        # TODO: Shader uniform/texture for keyboard support
        if key == "ArrowUp" or key == "w" or key == "W" or key == "z" or key == "Z":
            self._main_camera.move(MoveDir.FORWARD)
        elif key == "ArrowDown" or key == "s" or key == "S":
            self._main_camera.move(MoveDir.BACKWARD)
        elif key == "ArrowLeft" or key == "a" or key == "A" or key == "q" or key == "Q":
            self._main_camera.move(MoveDir.LEFT)
        elif key == "ArrowRight" or key == "d" or key == "D":
            self._main_camera.move(MoveDir.RIGHT)
        self._render_process_client.update_uniform(None, None, "uViewMat", self._main_camera.view_matrix)
        self._on_keyboard_event(key, down)

    def __on_renderdoc_capture(self):
        log("Capturing frame...", severity=logging.INFO)
        self._render_process_client.renderdoc_capture_frame(None)

    def __on_mouse_wheel(self, value: float):
        self._main_camera.zoom(value * 0.05)
        self._render_process_client.update_uniform(None, None, "uViewMat", self._main_camera.view_matrix)
        self._on_mouse_event(self._mouse_down, self._mouse_pos, value)

    def __on_mouse_x_updated(self, x):
        self._mouse_pos = (x.new, self._mouse_pos[1])
        self._render_process_client.update_uniform(None, None, "uMouse", tuple(self._mouse_pos))
        self._main_camera.mouse_change(self._mouse_pos, self._mouse_down)
        self._render_process_client.update_uniform(None, None, "uViewMat", self._main_camera.view_matrix)
        self._on_mouse_event(self._mouse_down, self._mouse_pos, 0)

    def __on_mouse_y_updated(self, y):
        self._mouse_pos = (self._mouse_pos[0], y.new)
        self._render_process_client.update_uniform(None, None, "uMouse", tuple(self._mouse_pos))
        self._main_camera.mouse_change(self._mouse_pos, self._mouse_down)
        self._render_process_client.update_uniform(None, None, "uViewMat", self._main_camera.view_matrix)
        self._on_mouse_event(self._mouse_down, self._mouse_pos, 0)

    @property
    def main_render_buffer(self) -> SSVRenderBuffer:
        """
        Gets the main render buffer associated with this ``SSVCanvas``.

        :return: the main render buffer.
        """
        return self._main_render_buffer

    @property
    def size(self) -> tuple[int, int]:
        """Gets the size of the canvas in pixels"""
        return self._size

    @property
    def standalone(self) -> bool:
        """Gets whether this canvas outputs to a standalone window as opposed to a jupyter widget."""
        return self._standalone

    @property
    def widget(self) -> Optional[SSVRenderWidget]:
        """Gets the render widget object. Only defined when ``standalone`` is ``False``."""
        return self._widget

    @property
    def main_camera(self) -> SSVCameraController:
        """Gets the main camera controller."""
        return self._main_camera

    @property
    def mouse_down(self) -> tuple[bool, bool, bool]:
        """Gets the current mouse button state as a tuple of ``bool``s. [left, right, middle]"""
        return self._mouse_down

    @property
    def mouse_pos(self) -> tuple[int, int]:
        """Gets the current mouse position relative to the canvas in pixels."""
        return self._mouse_pos

    def _set_logging_stream(self):
        """
        Sets the logger output to this SSVCanvas' widget if it exists.
        """
        if self._widget is not None:
            set_output_stream(SSVRenderWidgetLogIO(self._widget))

    def on_start(self, callback: Callable[[], None], remove: bool = False):
        """
        Registers/unregisters a callback which is invoked when this canvas's ``run()`` method is called, before any
        frames are rendered.

        :param callback: the callback to invoke.
        :param remove: whether the given callback should be removed.
        """
        self._on_start.register_callback(callback, remove)

    def on_mouse_event(self, callback: OnMouseDelegate, remove: bool = False):
        """
        Registers/unregisters a callback which is invoked when.

        :param callback: the callback to invoke.
        :param remove: whether the given callback should be removed.
        """
        self._on_mouse_event.register_callback(callback, remove)

    def on_keyboard_event(self, callback: OnKeyDelegate, remove: bool = False):
        """
        Registers/unregisters a callback which is invoked when.

        :param callback: the callback to invoke.
        :param remove: whether the given callback should be removed.
        """
        self._on_keyboard_event.register_callback(callback, remove)

    def on_frame_rendered(self, callback: Callable[[], None], remove: bool = False):
        """
        Registers/unregisters a callback which is invoked when.

        :param callback: the callback to invoke.
        :param remove: whether the given callback should be removed.
        """
        self._on_frame_rendered.register_callback(callback, remove)

    def run(self, stream_mode: Union[str, SSVStreamingMode] = SSVStreamingMode.JPG,
            stream_quality: Optional[int] = None, never_kill=False) -> None:
        """
        Starts the render loop and displays the Jupyter Widget (or render window if in standalone mode).

        :param stream_mode: the encoding format to use to transmit rendered frames from the render process to the
                            Jupyter widget.
        :param stream_quality: the encoding quality to use for the given encoding format. (For advanced users only)
        :param never_kill: disables the watchdog responsible for stopping the render process when the widget is no
                           longer being displayed. *Warning*: The only way to stop a renderer started with this enabled
                           is to restart the Jupyter kernel.
        """
        if isinstance(stream_mode, str):
            try:
                stream_mode = SSVStreamingMode(stream_mode)
            except KeyError:
                raise KeyError(f"'{stream_mode}' is not a valid streaming mode. Supported streaming modes are: \n"
                               f"{list(SSVStreamingMode)}")
        self._streaming_mode = stream_mode
        self._last_run_settings = {"stream_mode": stream_mode,
                                   "stream_quality": stream_quality,
                                   "never_kill": never_kill}

        if not self._render_process_client.is_alive:
            log("Render process is no longer connected. Create a new SSVCanvas and try again.", severity=logging.ERROR)
            return
            # raise ConnectionError("Render process is no longer connected. Create a new SSVCanvas and try again.")

        self._render_process_client.subscribe_on_render(self.__on_render)
        self._on_start()

        if not self._standalone:
            from IPython.display import display
            self._widget.streaming_mode = self._streaming_mode
            self._widget.use_websockets = self._supports_websockets
            self._widget.canvas_width, self._widget.canvas_height = self._size
            if self._canvas_stream_server is not None:
                self._widget.websocket_url = self._canvas_stream_server.url
            if self._streaming_mode == SSVStreamingMode.MJPEG:
                # A bit of a hack for now
                self._widget.use_websockets = False
                self._widget.websocket_url = self._canvas_mjpg_stream_server.url
            display(self._widget)
            self._widget.observe(lambda x: self.__on_mouse_x_updated(x), names=["mouse_pos_x"])
            self._widget.observe(lambda y: self.__on_mouse_y_updated(y), names=["mouse_pos_y"])
            if self._update_frame_rate_task is None or self._update_frame_rate_task.done():
                self._update_frame_rate_task = asyncio.create_task(self.__update_frame_rate())

        # Make sure the view and projection matrices are defined before rendering
        self._render_process_client.update_uniform(None, None, "uViewMat", self._main_camera.view_matrix)
        self._render_process_client.update_uniform(None, None, "uProjMat", self._main_camera.projection_matrix)

        self._render_process_client.set_timeout(None if never_kill else self._render_timeout)
        self._render_process_client.render(self._target_framerate, str(self._streaming_mode), stream_quality)

    def stop(self, force=False) -> None:
        """
        Stops the current canvas from rendering continuously. The renderer is not released and can be restarted.

        :param force: kills the render process and releases resources. SSVCanvases cannot be restarted if they have
                      been force stopped.
        """
        if force:
            self._render_process_client.stop()
        else:
            self._render_process_client.render(0, str(self._streaming_mode))

    def shader(self, shader_source: str, additional_template_directory: Optional[str] = None,
               additional_templates: Optional[list[str]] = None,
               shader_defines: Optional[dict[str, str]] = None,
               compiler_extensions: Optional[list[str]] = None):
        """
        Registers, compiles and attaches a shader to the main render buffer.

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
        self._main_render_buffer.shader(shader_source, additional_template_directory, additional_templates,
                                        shader_defines, compiler_extensions)

    def update_uniform(self, uniform_name: str, value: Any, share_with_render_buffer: bool = False,
                       share_with_canvas: bool = False) -> None:
        """
        Sets the value of a uniform associated with the main full-screen shader.

        :param uniform_name: the name of the uniform to set.
        :param value: the value to set. Must be compatible with the destination uniform.
        :param share_with_render_buffer: update this uniform across all shaders in this render buffer.
        :param share_with_canvas: update this uniform across all shaders in this canvas.
        """
        self._main_render_buffer.update_uniform(uniform_name, value, share_with_render_buffer, share_with_canvas)

    def render_buffer(self, size: tuple[int, int], name: Optional[str] = None, order: int = 0, dtype: str = "f1",
                      components: int = 4) -> SSVRenderBuffer:
        """
        Creates a new render buffer for this canvas. Useful for effects requiring multi pass rendering.

        :param size: the resolution of the new render buffer to create.
        :param name: the name of this render buffer. This is the name given to the automatically generated uniform
                     declaration. If set to ``None`` a name is automatically generated.
        :param order: a number to hint the renderer as to the order to render the buffers in. Smaller values are
                      rendered first; the main render buffer has an order of 999999.
        :param dtype: the data type for each pixel component (see: https://moderngl.readthedocs.io/en/5.8.2/topics/texture_formats.html).
        :param components: how many vector components should each pixel have (RGB=3, RGBA=4).
        :return: a new render buffer object.
        """
        render_buffer_name = name if name is not None else f"render_buffer{self._render_buffer_counter}"
        self._render_buffer_counter += 1
        return SSVRenderBuffer(self, self._render_process_client, self._preprocessor, None,
                               render_buffer_name, order, size, dtype, components)

    def texture(self, data: Union[npt.NDArray, Image], uniform_name: Optional[str], force_2d: bool = False, force_3d: bool = False,
                override_dtype: Optional[str] = None, treat_as_normalized_integer: bool = True,
                declare_uniform: bool = True) -> SSVTexture:
        """
        Creates or updates a texture from the NumPy array provided.

        :param data: a NumPy array or a PIL/Pillow Image containing the image data to copy to the texture.
        :param uniform_name: optionally, the name of the shader uniform to associate this texture with. If ``None`` is
                             specified, a name is automatically generated in the form 'uTexture{n}'
        :param force_2d: when set, forces the texture to be treated as 2-dimensional, even if it could be represented
                         by a 1D texture. This only applies in the ambiguous case where a 2D single component texture
                         has a height <= 4 (eg: ``np.array([[0.0, 0.1, 0.2], [0.3, 0.4, 0.5], [0.6, 0.7, 0.8]])``),
                         with this parameter set to ``False``, the array would be converted to a 1D texture with a
                         width of 3 and 3 components; setting this to ``True`` ensures that it becomes a 3x3 texture
                         with 1 component.
        :param force_3d: when set, forces the texture to be treated as 3-dimensional, even if it could be represented
                         by a 2D texture. See the description of the ``force_2d`` parameter for a full explanation.
        :param override_dtype: optionally, a moderngl datatype to force on the texture. See
                               https://moderngl.readthedocs.io/en/latest/topics/texture_formats.html for the full list
                               of available texture formats.
        :param treat_as_normalized_integer: when enabled, integer types (singed/unsigned) are treated as normalized
                                            integers by OpenGL, such that when the texture is sampled values in the
                                            texture are mapped to floats in the range [0, 1] or [-1, 1]. See:
                                            https://www.khronos.org/opengl/wiki/Normalized_Integer for more details.
        :param declare_uniform: when set, a shader uniform is automatically declared for this uniform in shaders.
        """
        uniform_name = uniform_name if uniform_name is not None else f"uTexture{len(self._textures)}"
        if uniform_name in self._textures:
            if self._textures[uniform_name] is not None and self._textures[uniform_name].is_valid:
                raise ValueError(f"A texture with the name '{uniform_name}' is already defined on this canvas. Call "
                                 f"update_texture() on the existing texture object or call release()")
        texture = SSVTexture(None, self._render_process_client, self._preprocessor, data, uniform_name,
                             force_2d, force_3d, override_dtype, treat_as_normalized_integer, declare_uniform)
        self._textures[uniform_name] = texture
        return texture

    def get_texture(self, uniform_name: str) -> Optional[SSVTexture]:
        """
        Gets a texture that's already been defined on this canvas.

        :param uniform_name: the name of the uniform associated with this texture.
        :return: the texture object or ``None`` if no texture was found with that name.
        """
        return self._textures.get(uniform_name, None)

    def dbg_query_shader_template(self, shader_template_name: str, additional_template_directory: Optional[str] = None,
                                  additional_templates=None) -> str:
        """
        Gets the list of arguments a given shader template expects and returns a string containing their usage info.

        :param shader_template_name: the name of the template to look for.
        :param additional_template_directory: a path to a directory containing custom shader templates.
        :param additional_templates: a list of custom shader templates (source code, not paths).
        :return: the shader template's auto generated help string.
        """
        return self._preprocessor.dbg_query_shader_template(shader_template_name, additional_template_directory,
                                                            additional_templates)

    def dbg_query_shader_templates(self, additional_template_directory: Optional[str] = None) -> str:
        """
        Gets a list of all the shader templates available to the preprocessor.

        :param additional_template_directory: a path to a directory containing custom shader templates.
        :return: A string of all the shader templates which were found.
        """
        metadata = self._preprocessor.dbg_query_shader_templates(additional_template_directory)
        shaders = "\n\n".join([f"\t'{shader.name}'\n"
                               f"\t\tAuthor: {shader.author if shader.author else ''}\n"
                               f"\t\tDescription: {shader.description if shader.description else ''}"
                               for shader in metadata])
        return f"Found shader templates: \n\n{shaders}"

    def dbg_preprocess_shader(self, shader_source: str, additional_template_directory: Optional[str] = None,
                              additional_templates: Optional[list[str]] = None,
                              shader_defines: Optional[dict[str, str]] = None,
                              compiler_extensions: Optional[list[str]] = None,
                              pretty_print: bool = True) -> Union[str, dict[str, str]]:
        """
        Runs the preprocessor on a shader and returns the results. Useful for debugging shaders.

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
        :param pretty_print: when enabled returns a single string containing all the preprocessed shaders
        """

        shaders = self._preprocessor.preprocess(shader_source, None, additional_template_directory,
                                                additional_templates, shader_defines, compiler_extensions)
        if not pretty_print:
            return shaders

        from ._version import VERSION

        # Primitive type is always defined but often set to None (so that it defaults to triangles); in this case it
        # isn't relevant to show, so we strip it.
        if "primitive_type" in shaders and shaders["primitive_type"] is None:
            del shaders["primitive_type"]

        stages = shaders.keys()
        shaders = shaders.values()
        stages = [f"////////////////////////////////////////\n"
                  f"// {stage.upper():^34} //\n"
                  f"////////////////////////////////////////\n\n" for stage in stages]
        shaders = [f"{shader}\n\n\n" for shader in shaders]
        preproc_src = f"/************************************************************\n" \
                      f" * {f'pySSV Shader Preprocessor version: {VERSION}':^56} *\n" \
                      f" ************************************************************/\n\n"
        preproc_src += "".join([str(s) for shader in zip(stages, shaders) for s in shader])

        return preproc_src

    def dbg_render_test(self):
        """
        Sets up the render pipeline to render a demo shader.
        """
        self._render_process_client.dbg_render_test()

    def dbg_log_context(self, full=False):
        """
        Logs the OpenGL information to the console for debugging.

        :param full: whether to log *all* of the OpenGL context information (including extensions).
        """
        self._render_process_client.dbg_log_context_info(full)

    def dbg_log_frame_times(self, enabled=True):
        """
        Enables or disables frame time logging.

        :param enabled: whether to log frame times.
        """
        self._render_process_client.dbg_log_frame_times(enabled)

    def dbg_capture_frame(self):
        """
        Triggers a frame capture with RenderDoc if this canvas has it enabled.

        Due to the asynchronous nature of the renderer, the frame may be capture 1 frame late.
        """
        if self._use_renderdoc:
            log("Capturing frame...", severity=logging.INFO)
            self._render_process_client.renderdoc_capture_frame(None)
        else:
            log("Renderdoc is not enabled on this canvas! Frame will not be captured.", severity=logging.WARN)
