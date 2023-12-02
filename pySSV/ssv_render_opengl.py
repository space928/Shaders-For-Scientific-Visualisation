#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import time
from typing import Optional, Any
from dataclasses import dataclass

import moderngl
import numpy as np
import numpy.typing as npt

from .environment import ENVIRONMENT, Env
from .ssv_logging import log
from .ssv_render import SSVRender


class SSVDrawCall:
    """
    Stores a reference to all the objects needed to represent a single draw call belonging to a render buffer.
    """
    __slots__ = ["order", "vertex_buffer", "index_buffer", "vertex_attributes", "vertex_array", "shader_program"]
    order: int
    vertex_buffer: Optional[moderngl.Buffer]
    index_buffer: Optional[moderngl.Buffer]
    vertex_attributes: tuple[str, ...]
    vertex_array: Optional[moderngl.VertexArray]
    shader_program: Optional[moderngl.Program]

    def __init__(self):
        self.order = 0
        self.vertex_buffer = None
        self.index_buffer = None
        self.vertex_attributes = ()
        self.vertex_array = None
        self.shader_program = None

    def release(self, needs_gc: bool):
        if needs_gc:
            self.vertex_array.release()
            self.vertex_buffer.release()
            self.index_buffer.release()
            self.shader_program.release()


@dataclass
class SSVRenderBufferOpenGL:
    """
    Stores a reference to all the OpenGL objects needed to render a single render buffer.
    """
    order: int
    needs_gc: bool
    frame_buffer: moderngl.Framebuffer
    render_texture: moderngl.Texture
    draw_calls: dict[int, SSVDrawCall]

    def release(self):
        """
        Releases the resources within this render buffer, clearing the draw call list.
        """
        for draw_call in self.draw_calls.values():
            draw_call.release(self.needs_gc)
        self.draw_calls.clear()
        # self.ordered_draw_calls.clear()
        if self.needs_gc:
            self.frame_buffer.release()
            self.render_texture.release()


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
        self._render_buffers: dict[int, SSVRenderBufferOpenGL] = {}
        self._ordered_render_buffers: list[SSVRenderBufferOpenGL] = []
        self._texture_objects: dict[int, moderngl.Texture] = {}
        self.__create_context()
        self._start_time = time.time()

        # Create a default output framebuffer
        self.update_frame_buffer(0, 999999, (640, 480))
        self._default_vertex_buffer = self.ctx.buffer(self._default_vertices)
        self._default_vertex_buffer_vertex_attributes = ("in_vert", "in_color")

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

    def update_frame_buffer(self, frame_buffer_uid: int, order: int, size: (int, int), components: int = 4,
                            dtype: str = "f1"):
        # TODO: It might make sense to decouple the moderngl dtype from our dtype if this is meant to be used by an
        #  abstract class.
        resolution = (min(size[0], self.ctx.info["GL_MAX_VIEWPORT_DIMS"][0]),
                      min(size[1], self.ctx.info["GL_MAX_VIEWPORT_DIMS"][1]))

        fb = self.ctx.simple_framebuffer(resolution, components=components, dtype=dtype)

        if frame_buffer_uid in self._render_buffers:
            render_buffer = self._render_buffers[frame_buffer_uid]
            render_buffer.frame_buffer = fb
            render_buffer.render_texture = fb.color_attachments[0]
        else:
            self._render_buffers[frame_buffer_uid] = SSVRenderBufferOpenGL(order, self.ctx.gc_mode is None, fb,
                                                                           fb.color_attachments[0], {})

        # Update the resolution uniform in this buffer
        self.update_uniform(frame_buffer_uid, None, "uResolution", (*resolution, 0, 0))

        # Re-sort the render buffers
        self._ordered_render_buffers = sorted(self._render_buffers.values(), key=lambda x: x.order)

    def delete_frame_buffer(self, frame_buffer_uid: int):
        if frame_buffer_uid == 0:
            log(f"Can't delete output framebuffer (uid = 0)!", severity=logging.ERROR)
            return
        if frame_buffer_uid not in self._render_buffers:
            log(f"Couldn't delete render buffer {frame_buffer_uid} as it doesn't exist!", severity=logging.ERROR)
            return

        self._render_buffers[frame_buffer_uid].release()
        del self._render_buffers[frame_buffer_uid]

        # Re-sort the render buffers
        self._ordered_render_buffers = sorted(self._render_buffers.values(), key=lambda x: x.order)

    def update_uniform(self, frame_buffer_uid: Optional[int], draw_call_uid: Optional[int],
                       uniform_name: str, value: Any):
        def update_internal(program: moderngl.Program):
            if program is not None and uniform_name in program:
                program[uniform_name].value = value

        if frame_buffer_uid is not None and frame_buffer_uid not in self._render_buffers:
            log(f"Couldn't set uniform in render buffer {frame_buffer_uid} as it doesn't exist!",
                severity=logging.ERROR)
            return
        if (draw_call_uid is not None and
                (frame_buffer_uid is None or
                 draw_call_uid not in self._render_buffers[frame_buffer_uid].draw_calls)):
            log(f"Couldn't set uniform in draw call {draw_call_uid} for render buffer {frame_buffer_uid} as it doesn't exist!",
                severity=logging.ERROR)
            return

        # Based on whether a frame buffer and/or vertex buffer are specified we either update the uniform
        # locally or globally.
        # TODO: For high-performance scenarios we could probably improve performance by using uniform blocks
        if frame_buffer_uid is not None:
            if draw_call_uid is not None:
                update_internal(self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid].shader_program)
            else:
                [update_internal(vb.shader_program) for vb in
                 self._render_buffers[frame_buffer_uid].draw_calls.values()]
        else:
            [update_internal(vb.shader_program) for rb in self._ordered_render_buffers for vb in rb.draw_calls.values()]

    def update_vertex_buffer(self, frame_buffer_uid: int, draw_call_uid: int,
                             vertex_array: Optional[npt.NDArray], index_array: Optional[npt.NDArray],
                             vertex_attributes: Optional[tuple[str]]):
        if frame_buffer_uid not in self._render_buffers:
            log(f"Attempted to update the vertex buffer for a non-existant render buffer (id={frame_buffer_uid})!",
                severity=logging.ERROR)
            return

        if draw_call_uid not in self._render_buffers[frame_buffer_uid].draw_calls:
            draw_call = SSVDrawCall()
            draw_call.order = 0
            draw_call.shader_program = None
            self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid] = draw_call
        else:
            draw_call = self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid]

        draw_call.vertex_buffer = self._default_vertex_buffer if vertex_array is None else self.ctx.buffer(vertex_array)
        draw_call.index_buffer = None if index_array is None else self.ctx.buffer(index_array)
        draw_call.vertex_attributes = self._default_vertex_buffer_vertex_attributes if vertex_attributes is None else vertex_attributes
        try:
            if draw_call.shader_program is not None:
                draw_call.vertex_array = self.ctx.vertex_array(draw_call.shader_program, draw_call.vertex_buffer,
                                                               *draw_call.vertex_attributes,
                                                               index_buffer=draw_call.index_buffer)
        except KeyError as e:
            log(f"Couldn't find required vertex attribute '{e.args[0]}' in shader!", severity=logging.ERROR)
            return

    def register_shader(self, frame_buffer_uid: int, draw_call_uid: int,
                        vertex_shader: str, fragment_shader: Optional[str],
                        tess_control_shader: Optional[str], tess_evaluation_shader: Optional[str],
                        geometry_shader: Optional[str], compute_shader: Optional[str]):
        if frame_buffer_uid not in self._render_buffers:
            log(f"Attempted to register a shader to a non-existant render buffer (id={frame_buffer_uid})!",
                severity=logging.ERROR)
            return

        if draw_call_uid not in self._render_buffers[frame_buffer_uid].draw_calls:
            log(f"Attempted to register a shader to a non-existant draw call (id={draw_call_uid})!",
                severity=logging.ERROR)
            return
            # This is a hack to allow a draw call to have a default vertex buffer. This means that if the user calls
            # the shader() method, a shader is registered correctly to render to the full screen even if no vertex
            # buffer is given afterwards.
            # draw_call = SSVDrawCall()
            # draw_call.vertex_buffer = self._default_vertex_buffer
            # draw_call.index_buffer = None
            # draw_call.vertex_attributes = self._default_vertex_buffer_vertex_attributes
            # self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid] = draw_call

        draw_call = self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid]

        # draw_call.shader_program.release()
        # draw_call.vertex_array.release()

        try:
            draw_call.shader_program = (
                self.ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader,
                                 geometry_shader=geometry_shader,
                                 tess_control_shader=tess_control_shader,
                                 tess_evaluation_shader=tess_evaluation_shader))

            # Creating a new shader program invalidates any previously bound vertex arrays, so we need to recreate it.
            # Annoyingly, to support the "default" case where the user doesn't call update_vertex_buffer() we need to
            # create this vertex array no matter what; even if the user subsequently calls update_vertex_buffer which
            # would replace this vertex array.
            try:
                draw_call.vertex_array = self.ctx.vertex_array(draw_call.shader_program, draw_call.vertex_buffer,
                                                               *draw_call.vertex_attributes,
                                                               index_buffer=draw_call.index_buffer)
            except KeyError as e:
                log(f"Couldn't find required vertex attribute '{e.args[0]}' in shader!", severity=logging.ERROR)
                return
        except moderngl.Error as e:
            log(e, severity=logging.ERROR)

        # Set the resolution uniform as soon as the program is created
        fb = self._render_buffers[frame_buffer_uid].frame_buffer
        self.update_uniform(draw_call_uid, draw_call_uid, "uResolution", (fb.width, fb.height, 0, 0))

    def update_texture(self, texture_uid: int, data: npt.NDArray, rect: Optional[tuple[int, int, int, int]]):
        ...

    def delete_texture(self, texture_uid: int):
        ...

    def render(self):
        if 0 not in self._render_buffers:
            log("Render pipeline not yet initialised! No render buffer bound to the output framebuffer.",
                severity=logging.ERROR)
            return False

        self.update_uniform(None, None, "uTime", time.time() - self._start_time)

        for rb in self._ordered_render_buffers:
            rb.frame_buffer.use()

            # Sort the draw calls
            # TODO: This puts unnecessary pressure on the GC, it would be faster if sorting was only done when needed
            #  and didn't allocate a new list.
            draw_calls = sorted(rb.draw_calls.values(), key=lambda x: x.order)

            self.ctx.clear()
            for dc in draw_calls:
                dc.vertex_array.render(mode=moderngl.TRIANGLES)

        return True

    def read_frame(self, components: int = 4, frame_buffer_uid: int = 0):
        return self._render_buffers[frame_buffer_uid].frame_buffer.read(components=components)

    def read_frame_into(self, buffer, components: int = 4, frame_buffer_uid: int = 0):
        self._render_buffers[frame_buffer_uid].frame_buffer.read_into(buffer, components=components)
