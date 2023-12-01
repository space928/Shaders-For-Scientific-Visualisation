#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
from typing import Optional

from .ssv_render_process_client import SSVRenderProcessClient
from .ssv_render_widget import SSVRenderWidget, SSVRenderWidgetLogIO
from .ssv_shader_preprocessor import SSVShaderPreprocessor
from .ssv_logging import log, set_output_stream


class SSVCanvas:
    """
    An SSV canvas manages the OpenGL rendering context, shaders, and the jupyter widget
    """

    def __init__(self, size, backend="opengl", standalone=False, target_framerate=60):
        """
        Creates a new SSV Canvas object which manages the graphics context and render widget/window.

        :param size: the default resolution of the renderer as a tuple: ``(width: int, height: int)``
        :param backend: the rendering backend to use; currently supports: ``"opengl"``
        :param standalone: whether the canvas should run standalone, or attempt to create a Jupyter Widget for
                           rendering.
        :param target_framerate: the default framerate to target when running.
        """
        if size is None:
            size = (640, 480)
        self.size = size
        self.standalone = standalone
        self.target_framerate = target_framerate
        self.streaming_mode = "jpg"
        self.backend = backend
        if not standalone:
            self.widget = SSVRenderWidget()
            self.widget.streaming_mode = self.streaming_mode
            self.widget.on_heartbeat(self.__on_heartbeat)
            self.widget.on_play(self.__on_play)
            self.widget.on_stop(self.__on_stop)
            set_output_stream(SSVRenderWidgetLogIO(self.widget))
            # set_output_stream(sys.stdout)
        self._render_process_client = SSVRenderProcessClient(backend, None if standalone else 1)
        self._preprocessor = SSVShaderPreprocessor(gl_version="420")

        self._mouse_pos = [0, 0]
        # Cache the last parameters to the run() method for the widget's "play" button to use
        self._last_run_settings = {}

    def __del__(self):
        self.stop()
        self._render_process_client.stop()

    def __on_render(self, stream_data):
        self.widget.stream_data = stream_data

    def __on_heartbeat(self):
        self._render_process_client.send_heartbeat()
        self.widget.status_connection = self._render_process_client.is_alive

    def __on_play(self):
        self.run(**self._last_run_settings)

    def __on_stop(self):
        self.stop()

    def __on_mouse_x_updated(self, x):
        self._mouse_pos[0] = x.new
        self._render_process_client.update_uniform(None, None, "uMouse", tuple(self._mouse_pos))

    def __on_mouse_y_updated(self, y):
        self._mouse_pos[1] = y.new
        self._render_process_client.update_uniform(None, None, "uMouse", tuple(self._mouse_pos))

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
        Registers, compiles and attaches a shader to a given render buffer.

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
        shaders = self._preprocessor.preprocess(shader_source, None, additional_template_directory,
                                                additional_templates, shader_defines, compiler_extensions)
        self._render_process_client.register_shader(0, 0, **shaders)

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
