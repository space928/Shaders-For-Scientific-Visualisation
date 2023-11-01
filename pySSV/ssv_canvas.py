#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

from .ssv_render_process_client import SSVRenderProcessClient
from .ssv_render_widget import SSVRenderWidget
from .ssv_logging import log


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
        if not standalone:
            self.widget = SSVRenderWidget()
            self.widget.streaming_mode = self.streaming_mode
            self.widget.on_heartbeat(self.__on_heartbeat)
        self._render_process_client = SSVRenderProcessClient(backend, None if standalone else 1)

        self._mouse_pos = [0, 0]

    def __del__(self):
        self.stop()
        self._render_process_client.stop()

    def __on_render(self, stream_data):
        self.widget.stream_data = stream_data

    def __on_heartbeat(self):
        self._render_process_client.send_heartbeat()

    def __on_mouse_x_updated(self, x):
        self._mouse_pos[0] = x.new
        self._render_process_client.update_uniform(-1, "iMouse", tuple(self._mouse_pos))

    def __on_mouse_y_updated(self, y):
        self._mouse_pos[1] = y.new
        self._render_process_client.update_uniform(-1, "iMouse", tuple(self._mouse_pos))

    def run(self, stream_mode="jpg"):
        self.streaming_mode = stream_mode
        self._render_process_client.subscribe_on_render(self.__on_render)

        if not self.standalone:
            from IPython.display import display
            self.widget.streaming_mode = self.streaming_mode
            display(self.widget)
            self.widget.observe(lambda x: self.__on_mouse_x_updated(x), names=["mouse_pos_x"])
            self.widget.observe(lambda y: self.__on_mouse_y_updated(y), names=["mouse_pos_y"])

        self._render_process_client.render(self.target_framerate, self.streaming_mode)

    def stop(self):
        self._render_process_client.render(0, self.streaming_mode)

    def dbg_shader(self, fragment_shader: str):
        """
        Sets up the pipeline to render a basic ShaderToy compatible shader.
        Note that most ShaderToy uniforms are not yet implemented.

        :param fragment_shader: the GLSL source of the shader to render.
        :return:
        """
        self._render_process_client.register_shader(0, vertex_shader="""
        #version 330
        in vec2 in_vert;
        in vec3 in_color;
        out vec3 color;
        out vec2 position;
        void main() {
            gl_Position = vec4(in_vert, 0.0, 1.0);
            color = in_color;
            position = in_vert*0.5+0.5;
        }
        """, fragment_shader=f"""
        #version 330
        out vec4 fragColor;
        in vec3 color;
        in vec2 position;

        uniform vec2 iResolution;
        uniform float iTime;
        uniform vec2 iMouse;
        
        {fragment_shader}
        
        void main() {{
            // Not using the color attribute causes the compiler to strip it and confuses modernGL.
            fragColor = mainImage(position * iResolution) + vec4(color, 1.0)*1e-6;
        }}
        """)
        self._render_process_client.update_uniform(0, "iResolution", self.size)
        self._render_process_client.update_vertex_buffer(0, None)

    def dbg_render_test(self):
        """
        Sets up the render pipeline to render a demo shader.
        :return:
        """
        self._render_process_client.dbg_render_test()

    def dbg_log_context(self, full=False):
        """
        Logs the OpenGL information to the console for debugging.

        :param full: whether to log *all* of the OpenGL context information (including extensions).
        """
        self._render_process_client.dbg_log_context_info(full)
