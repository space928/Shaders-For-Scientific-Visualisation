#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
from typing import Optional, Any
import numpy.typing as npt
import math
import time

from .ssv_camera import SSVCamera, MoveDir
from .ssv_render_process_client import SSVRenderProcessClient
from .ssv_render_widget import SSVRenderWidget, SSVRenderWidgetLogIO
from .ssv_shader_preprocessor import SSVShaderPreprocessor
from .ssv_logging import log, set_output_stream
from .ssv_render_buffer import SSVRenderBuffer
from .ssv_texture import SSVTexture


class SSVCanvas:
    """
    An SSV canvas manages the OpenGL rendering context, shaders, and the jupyter widget
    """

    def __init__(self, size: Optional[tuple[int, int]], backend: str = "opengl", standalone: bool = False,
                 target_framerate: int = 60, use_renderdoc: bool = False):
        """
        Creates a new SSV Canvas object which manages the graphics context and render widget/window.

        :param size: the default resolution of the renderer as a tuple: ``(width: int, height: int)``.
        :param backend: the rendering backend to use; currently supports: ``"opengl"``.
        :param standalone: whether the canvas should run standalone, or attempt to create a Jupyter Widget for
                           rendering.
        :param target_framerate: the default framerate to target when running.
        :param use_renderdoc: optionally, an instance of the Renderdoc in-app api to provide support for frame
                               capturing and analysis in renderdoc.
        """
        if size is None:
            size = (640, 480)
        self.size = size
        self.standalone = standalone
        self.target_framerate = target_framerate
        self.streaming_mode = "jpg"
        self.backend = backend
        self._use_renderdoc = False
        if use_renderdoc:
            try:
                from pyRenderdocApp import RENDERDOC_API_1_6_0
                self._use_renderdoc = True
            except ImportError:
                log("Couldn't find pyRenderdocApp module! Renderdoc will not be loaded.", severity=logging.WARN)
        if not standalone:
            self.widget = SSVRenderWidget()
            self.widget.streaming_mode = self.streaming_mode
            self.widget.enable_renderdoc = self._use_renderdoc
            self.widget.on_heartbeat(self.__on_heartbeat)
            self.widget.on_play(self.__on_play)
            self.widget.on_stop(self.__on_stop)
            self.widget.on_key(self.__on_key)
            self.widget.on_click(self.__on_click)
            if self._use_renderdoc:
                self.widget.on_renderdoc_capture(self.__on_renderdoc_capture)
            set_output_stream(SSVRenderWidgetLogIO(self.widget))
            # set_output_stream(sys.stdout)
        self._render_process_client = SSVRenderProcessClient(backend, None if standalone else 3,
                                                             self._use_renderdoc)
        self._preprocessor = SSVShaderPreprocessor(gl_version="420")

        self._mouse_pos = [0, 0]
        self._mouse_down = False
        # Cache the last parameters to the run() method for the widget's "play" button to use
        self._last_run_settings = {}

        # Set up a default render buffer
        self._main_render_buffer = SSVRenderBuffer(self, self._render_process_client, self._preprocessor,
                                                   0, "main_render_buffer",
                                                   999999, size, "f1", 4)
        self.render_buffer_counter = 1
        self.main_camera = SSVCamera()
        self.main_camera.aspect_ratio = size[0]/size[1]
        self._textures = []

    def __del__(self):
        self.stop()
        self._render_process_client.stop()

    def __on_render(self, stream_data):
        self.widget.stream_data = stream_data
        self.main_camera.position[2] = math.sin(time.time())
        self._render_process_client.update_uniform(None, None, "uViewMat", self.main_camera.view_matrix)

    def __on_heartbeat(self):
        self._render_process_client.send_heartbeat()
        self.widget.status_connection = self._render_process_client.is_alive

    def __on_play(self):
        self.run(**self._last_run_settings)

    def __on_stop(self):
        self.stop()

    def __on_click(self, down: bool):
        self._mouse_down = down
        self._render_process_client.update_uniform(None, None, "uMouseDown", down)
        self.main_camera.mouse_change(self._mouse_pos, self._mouse_down)
        self._render_process_client.update_uniform(None, None, "uViewMat", self.main_camera.view_matrix)

    def __on_key(self, key: str, down: bool):
        # TODO: Shader uniform/texture for keyboard support
        if key == "ArrowUp" or key == "w" or key == "W" or key == "z" or key == "Z":
            self.main_camera.move(MoveDir.FORWARD)
        elif key == "ArrowDown" or key == "s" or key == "S":
            self.main_camera.move(MoveDir.BACKWARD)
        elif key == "ArrowLeft" or key == "a" or key == "A" or key == "q" or key == "Q":
            self.main_camera.move(MoveDir.LEFT)
        elif key == "ArrowRight" or key == "d" or key == "D":
            self.main_camera.move(MoveDir.RIGHT)

    def __on_renderdoc_capture(self):
        log("Capturing frame...", severity=logging.INFO)
        self._render_process_client.renderdoc_capture_frame(None)

    def __on_mouse_x_updated(self, x):
        self._mouse_pos[0] = x.new
        self._render_process_client.update_uniform(None, None, "uMouse", tuple(self._mouse_pos))
        self.main_camera.mouse_change(self._mouse_pos, self._mouse_down)
        self._render_process_client.update_uniform(None, None, "uViewMat", self.main_camera.view_matrix)

    def __on_mouse_y_updated(self, y):
        self._mouse_pos[1] = y.new
        self._render_process_client.update_uniform(None, None, "uMouse", tuple(self._mouse_pos))
        self.main_camera.mouse_change(self._mouse_pos, self._mouse_down)
        self._render_process_client.update_uniform(None, None, "uViewMat", self.main_camera.view_matrix)

    @property
    def main_render_buffer(self) -> SSVRenderBuffer:
        """
        Gets the main render buffer associated with this ``SSVCanvas``.

        :return: the main render buffer.
        """
        return self._main_render_buffer

    def run(self, stream_mode="jpg", stream_quality: Optional[int] = None, never_kill=False) -> None:
        """
        Starts the render loop and displays the Jupyter Widget (or render window if in standalone mode).

        :param stream_mode: the encoding format to use to transmit rendered frames from the render process to the
                            Jupyter widget. (Currently supports: `jpg`, `png`).
        :param stream_quality: the encoding quality to use for the given encoding format. (For advanced users only)
        :param never_kill: disables the watchdog responsible for stopping the render process when the widget is no
                           longer being displayed. *Warning*: The only way to stop a renderer started with this enabled
                           is to restart the Jupyter kernel.
        """
        self.streaming_mode = stream_mode
        self._last_run_settings = {"stream_mode": stream_mode,
                                   "stream_quality": stream_quality,
                                   "never_kill": never_kill}

        if not self._render_process_client.is_alive:
            log("Render process is no longer connected. Create a new SSVCanvas and try again.", severity=logging.ERROR)
            return
            # raise ConnectionError("Render process is no longer connected. Create a new SSVCanvas and try again.")

        self._render_process_client.subscribe_on_render(self.__on_render)

        if not self.standalone:
            from IPython.display import display
            self.widget.streaming_mode = self.streaming_mode
            display(self.widget)
            self.widget.observe(lambda x: self.__on_mouse_x_updated(x), names=["mouse_pos_x"])
            self.widget.observe(lambda y: self.__on_mouse_y_updated(y), names=["mouse_pos_y"])

        # Make sure the view and projection matrices are defined before rendering
        self._render_process_client.update_uniform(None, None, "uViewMat", self.main_camera.view_matrix)
        self._render_process_client.update_uniform(None, None, "uProjMat", self.main_camera.projection_matrix)

        self._render_process_client.set_timeout(None if never_kill else 1)
        self._render_process_client.render(self.target_framerate, self.streaming_mode, stream_quality)

    def stop(self, force=False) -> None:
        """
        Stops the current canvas from rendering continuously. The renderer is not released and can be restarted.

        :param force: kills the render process and releases resources. SSVCanvases cannot be restarted if they have
                      been force stopped.
        """
        if force:
            self._render_process_client.stop()
        else:
            self._render_process_client.render(0, self.streaming_mode)

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
        render_buffer_name = name if name is not None else f"render_buffer{self.render_buffer_counter}"
        self.render_buffer_counter += 1
        return SSVRenderBuffer(self, self._render_process_client, self._preprocessor, None,
                               render_buffer_name, order, size, dtype, components)

    def texture(self, data: npt.NDArray, uniform_name: Optional[str], force_2d: bool = False, force_3d: bool = False,
                override_dtype: Optional[str] = None) -> SSVTexture:
        """
        Creates or updates a texture from the NumPy array provided.

        :param data: a NumPy array containing the image data to copy to the texture.
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
        """
        uniform_name = uniform_name if uniform_name is not None else f"uTexture{len(self._textures)}"
        texture = SSVTexture(None, self._render_process_client, self._preprocessor, data, uniform_name,
                             force_2d, force_3d, override_dtype)
        self._textures.append(texture)
        return texture

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
                              compiler_extensions: Optional[list[str]] = None) -> dict[str, str]:
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
        """
        return self._preprocessor.preprocess(shader_source, None, additional_template_directory,
                                             additional_templates, shader_defines, compiler_extensions)

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
