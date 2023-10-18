#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import time
from typing import Optional

import moderngl
import numpy as np
import numpy.typing as npt

from .environment import ENVIRONMENT, Env
from .ssv_logging import log
from .ssv_render import SSVRender


class SSVRenderOpenGL(SSVRender):
    """
    A rendering backend for SSV based on OpenGL
    """

    _default_vertices = np.array([
        # X   Y     R    G    B
        -1.0, -1.0, 1.0, 0.0, 0.0,
        1.0, -1.0, 0.0, 1.0, 0.0,
        -1.0, 1.0, 0.0, 0.0, 1.0,
        1.0, 1.0, 0.0, 0.0, 1.0,
        -1.0, 1.0, 0.0, 0.0, 1.0,
        1.0, -1.0, 0.0, 0.0, 1.0],
        dtype='f4',
    )

    def __init__(self):
        self._frame_buffers: dict[int, moderngl.Framebuffer] = {}
        self._programs: dict[int, moderngl.Program] = {}
        self._vertex_buffers: dict[int, moderngl.VertexArray] = {}
        self.__create_context()
        self._start_time = time.time()

        # Create a default output framebuffer
        self.update_frame_buffer(0, (640, 480), 4)

    def __create_context(self):
        """
        Creates an OpenGL context and a framebuffer.
        """
        if ENVIRONMENT == Env.COLAB:
            # TODO: Test if any other platforms require specific backends
            # In Google Colab we need to explicitly specify the EGL backend, otherwise it tries (and fails) to use X11
            self.ctx = moderngl.create_context(standalone=True, backend="egl")
        else:
            # Otherwise let ModernGL try to automatically determine the correct backend
            self.ctx = moderngl.create_context(standalone=True)

        # To use moderngl with threading we need call the garbage collector manually
        # self.ctx.gc_mode = "context_gc"

    def log_context_info(self, full=False):
        """
        Logs the OpenGL information to the console for debugging.
        :param full: whether to log *all* of the OpenGL context information (including extensions)
        """
        log(f"Got OpenGL context:\n"
            f"\tGL_VENDOR={self.ctx.info['GL_VENDOR']}\n"
            f"\tGL_RENDERER={self.ctx.info['GL_RENDERER']}\n"
            f"\tGL_VERSION={self.ctx.info['GL_VERSION']}", severity=logging.INFO)
        if full:
            from pprint import pformat
            info = pformat(self.ctx.info, indent=4)
            log(f"Full info: \n{info}", severity=logging.INFO)
            extensions = pformat(self.ctx.extensions, indent=4)
            log(f"GL Extensions: \n{extensions}", severity=logging.INFO)

    def update_frame_buffer(self, buffer_id: int, size: (int, int), pixel_format: int):
        if buffer_id < 0:
            log(f"Attempted to update an invalid framebuffer id: {buffer_id}!", logging.ERROR)
            return

        resolution = (min(size[0], self.ctx.info["GL_MAX_VIEWPORT_DIMS"][0]),
                      min(size[1], self.ctx.info["GL_MAX_VIEWPORT_DIMS"][1]))
        # if buffer_id not in self._frame_buffers:
        # TODO: Support different framebuffer pixel formats
        if buffer_id == 0:
            self._frame_buffers[buffer_id] = self.ctx.simple_framebuffer(resolution, components=4)
        else:
            self._frame_buffers[buffer_id] = self.ctx.framebuffer(self.ctx.texture(resolution, components=4))

    def delete_frame_buffer(self, buffer_id: int):
        if buffer_id < 1:
            log(f"Attempted to update an invalid (or required) framebuffer id: {buffer_id}!", logging.ERROR)
            return

        try:
            self._frame_buffers.pop(buffer_id)
        except KeyError:
            log(f"Couldn't delete framebuffer {buffer_id} as it doesn't exist!", severity=logging.ERROR)

    def update_uniform(self, buffer_id: int, uniform_name: str, value):
        if buffer_id < 0:
            for prog in self._programs.values():
                if uniform_name in prog:
                    prog[uniform_name].value = value
        else:
            if buffer_id in self._programs and uniform_name in self._programs[buffer_id]:
                self._programs[buffer_id][uniform_name].value = value

    def update_vertex_buffer(self, buffer_id: int, array: Optional[npt.NDArray]):
        if buffer_id not in self._programs:
            log(f"Attempted to update the vertex buffer for a non-existant program (id={buffer_id})!",
                logging.ERROR)
            return

        # TODO: Custom vertex buffers
        if array is None:
            vertex_buff = self.ctx.buffer(self._default_vertices)
            self._vertex_buffers[buffer_id] = self.ctx.simple_vertex_array(self._programs[buffer_id], vertex_buff,
                                                                           'in_vert', 'in_color')
        else:
            raise NotImplementedError()

    def register_shader(self, buffer_id: int, vertex_shader: str, fragment_shader: Optional[str],
                        tess_control_shader: Optional[str], tess_evaluation_shader: Optional[str],
                        geometry_shader: Optional[str], compute_shader: Optional[str]):
        if buffer_id not in self._frame_buffers:
            log(f"Attempted to register a shader to a non-existant framebuffer (id={buffer_id})!",
                logging.ERROR)
            return

        try:
            self._programs[buffer_id] = self.ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader,
                                                         geometry_shader=geometry_shader,
                                                         tess_control_shader=tess_control_shader,
                                                         tess_evaluation_shader=tess_evaluation_shader)
        except moderngl.Error as e:
            log(e, severity=logging.ERROR)

    def dbg_render_test(self):
        # Create a vertex buffer
        vertices = np.array([
            # X      Y      R    G    B
            -1.0, -1.0, 1.0, 0.0, 0.0,
            1.0, -1.0, 0.0, 1.0, 0.0,
            0.0, 1.0, 0.0, 0.0, 1.0],
            dtype='f4',
        )

        self._programs[0] = self.ctx.program(vertex_shader="""
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
        """,
                                             fragment_shader="""
        #version 330
        out vec4 fragColor;
        in vec3 color;
        in vec2 position;

        uniform vec2 iResolution;
        uniform float iTime;

        float amod(float x, float y)
        {
            return x - y * floor(x/y);
        }

        vec4 mainImage(in vec2 fragCoord)
        {
            // Normalized pixel coordinates (from 0 to 1)
            vec2 uv = fragCoord/iResolution.xy;

            float coord = floor(fragCoord.x) + floor(fragCoord.y/10.) + (iTime*60.);
            //vec3 col = vec3(amod(coord, 16.)>=8.?1.:0., amod(coord, 32.)>=16.?1.:0., amod(coord, 64.)>=32.?1.:0.);
            //col = amod(coord, 128.)>64.?(col*0.3333+.3333):col;

            vec3 col = vec3(amod(coord, 64.) >= 56. ? 1. : 0.,
                            amod(coord + 16., 64.) >= 56. ? 1. : 0.,
                            amod(coord + 32., 64.) >= 56. ? 1. : 0.);
            col += amod(coord + 48., 64.) >= 56. ? 1. : 0.;
            col = amod(coord, 128.) > 64. ? (col * 0.3333 + .3333) : col;

            // Output to screen
            return vec4(col,1.0);
        }

        void main() {
            fragColor = mainImage(position * iResolution) + vec4(color, 1.0)*0.01;
            //fragColor = vec4(color, 1.0);
        }
        """)

        # Set uniforms
        self._programs[0]["iResolution"].value = self._frame_buffers[0].size
        self._programs[0]["iTime"].value = time.time() - self._start_time

        # Assign buffers and render
        vert_buff = self.ctx.buffer(vertices)
        self._vertex_buffers[0] = self.ctx.simple_vertex_array(self._programs[0], vert_buff,
                                                               'in_vert', 'in_color')

    def render(self):
        if 0 not in self._vertex_buffers:
            log("Render pipeline not yet initialised! No vertex buffer bound to the output framebuffer.",
                severity=logging.ERROR)
            return False

        if "iTime" in self._programs[0]:
            self._programs[0]["iTime"].value = time.time() - self._start_time

        self._frame_buffers[0].use()
        self.ctx.clear()
        self._vertex_buffers[0].render(mode=moderngl.TRIANGLES)
        return True

    def get_frame(self, components=4):
        return self._frame_buffers[0].read(components=components)
