#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import sys
import time
import os
from typing import Optional, Any, Union, Tuple, Set, Dict, List, cast
from dataclasses import dataclass

import moderngl
import numpy as np
import numpy.typing as npt

from .environment import ENVIRONMENT, Env
from .ssv_logging import log
from .ssv_render import SSVRender
from .ssv_texture import determine_texture_shape

# Optional support for pyRenderdocApp
try:
    from pyRenderdocApp import load_render_doc, RENDERDOC_API_1_6_0  # type: ignore
except ImportError:
    class RENDERDOC_API_1_6_0:  # type: ignore[no-redef]
        ...


    def load_render_doc(renderdoc_path: Optional[str] = None) -> RENDERDOC_API_1_6_0:  # type: ignore[no-redef]
        return RENDERDOC_API_1_6_0()

PRIMITIVE_TYPES: Dict[str, int] = {
    "POINTS": cast(int, moderngl.POINTS),
    "LINES": cast(int, moderngl.LINES),
    "LINE_LOOP": cast(int, moderngl.LINE_LOOP),
    "LINE_STRIP": cast(int, moderngl.LINE_STRIP),
    "TRIANGLES": cast(int, moderngl.TRIANGLES),
    "TRIANGLE_STRIP": cast(int, moderngl.TRIANGLE_STRIP),
    "TRIANGLE_FAN": cast(int, moderngl.TRIANGLE_FAN),
    "LINES_ADJACENCY": cast(int, moderngl.LINES_ADJACENCY),
    "LINE_STRIP_ADJACENCY": cast(int, moderngl.LINE_STRIP_ADJACENCY),
    "TRIANGLES_ADJACENCY": cast(int, moderngl.TRIANGLES_ADJACENCY),
    "TRIANGLE_STRIP_ADJACENCY": cast(int, moderngl.TRIANGLE_STRIP_ADJACENCY),
    "PATCHES": cast(int, moderngl.PATCHES)
}


class SSVDrawCall:
    """
    Stores a reference to all the objects needed to represent a single draw call belonging to a render buffer.
    """
    __slots__ = ["order", "vertex_buffer", "index_buffer", "vertex_attributes", "gl_vertex_array", "shader_program",
                 "primitive_type"]
    order: int
    vertex_buffer: Optional[moderngl.Buffer]
    index_buffer: Optional[moderngl.Buffer]
    vertex_attributes: Tuple[str, ...]
    gl_vertex_array: Optional[moderngl.VertexArray]
    shader_program: Optional[moderngl.Program]
    primitive_type: int

    def __init__(self):
        self.order = 0
        self.vertex_buffer = None
        self.index_buffer = None
        self.vertex_attributes = ()
        self.gl_vertex_array = None
        self.shader_program = None
        self.primitive_type = int(moderngl.TRIANGLES)

    def release(self, needs_gc: bool, release_vb: bool = True):
        if needs_gc:
            if self.gl_vertex_array is not None:
                self.gl_vertex_array.release()
            if self.vertex_buffer is not None and release_vb:
                self.vertex_buffer.release()
            if self.index_buffer is not None:
                self.index_buffer.release()
            if self.shader_program is not None:
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
    draw_calls: Dict[int, SSVDrawCall]
    uniform_name: str

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


@dataclass
class SSVTextureOpenGL:
    """
    Stores a reference to an OpenGL texture object.
    """
    texture: Union[moderngl.Texture, moderngl.Texture3D]
    uniform_name: str

    def release(self, needs_gc: bool):
        if needs_gc:
            self.texture.release()


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

    def __init__(self, gl_version: Optional[int] = None, use_renderdoc_api: bool = False):
        self._render_buffers: Dict[int, SSVRenderBufferOpenGL] = {}
        self._ordered_render_buffers: List[SSVRenderBufferOpenGL] = []
        self._texture_objects: Dict[int, SSVTextureOpenGL] = {}
        self._renderdoc_api = None
        self._renderdoc_is_capturing = False
        if use_renderdoc_api:
            self._renderdoc_api = load_render_doc()
        self.__create_context(gl_version)
        self._start_time = time.time()
        self._frame_no = 0

        # Create a default output framebuffer
        self.update_frame_buffer(0, 999999, (640, 480), "main_render_buffer")
        self._default_vertex_buffer = self.ctx.buffer(self._default_vertices)
        self._default_vertex_buffer_vertex_attributes = ("in_vert", "in_color")

    def __create_context(self, gl_version: Optional[int]):
        """
        Creates an OpenGL context and a framebuffer.
        """

        # Hack for WSL
        if "linux" in sys.platform:
            # On WSL2, setting this environment variable allows us to specify a GPU preference:
            # https://github.com/microsoft/wslg/wiki/GPU-selection-in-WSLg
            # If the user hasn't already set it, then we set it to NVIDIA, just in case the user has an NVIDIA GPU,
            # because they probably want to use that. While this doesn't help laptop users with dedicated AMD GPUs,
            # the user can still set this env variable themselves.
            if "MESA_D3D12_DEFAULT_ADAPTER_NAME" not in os.environ:
                os.environ["MESA_D3D12_DEFAULT_ADAPTER_NAME"] = "NVIDIA"

        # TODO: Come up with a more legible way of creating the context... This is a mess...
        if ENVIRONMENT == Env.COLAB:
            # TODO: Test if any other platforms require specific backends
            # In Google Colab we need to explicitly specify the EGL backend, otherwise it tries (and fails) to use X11
            # noinspection PyTypeChecker
            self.ctx = moderngl.create_context(standalone=True, backend="egl")  # type: ignore
        else:
            # Otherwise let ModernGL try to automatically determine the correct backend
            if gl_version is None:
                # noinspection PyBroadException
                try:
                    # Try to load OpenGL 4.2 by default
                    self.ctx = moderngl.create_context(standalone=True, require=420)
                except Exception:
                    # If unavailable, try any other version that might be available on the system
                    try:
                        self.ctx = moderngl.create_context(standalone=True)
                    except Exception as ex:
                        if "linux" in sys.platform:
                            # Try using EGL...
                            # noinspection PyBroadException
                            try:
                                # Try to load OpenGL 4.2 by default
                                self.ctx = moderngl.create_context(standalone=True, require=420,
                                                                   backend="egl")  # type: ignore
                            except Exception:
                                # If unavailable, try any other version that might be available on the system
                                try:
                                    self.ctx = moderngl.create_context(standalone=True, backend="egl")  # type: ignore
                                except Exception as ex_egl:
                                    raise Exception(f"Couldn't create context using X11 or EGL: \n{ex}\n{ex_egl}")
                        else:
                            raise ex
            else:
                self.ctx = moderngl.create_context(standalone=True, require=gl_version)

        # To use moderngl with threading we need call the garbage collector manually
        # self.ctx.gc_mode = "context_gc"

        # Enable depth testing and set the compare function to LEQUAL so that multiple passes can render on top of each
        # other.
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.depth_func = "<="
        self.ctx.enable(moderngl.BLEND)
        # A bit of a weird blending function, but it plays 'nice' with the GUI...
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA,  # type: ignore
                               moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
        self.ctx.blend_equation = moderngl.FUNC_ADD, moderngl.FUNC_ADD

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

    def get_context_info(self) -> Dict[str, str]:
        return self.ctx.info

    def get_supported_extensions(self) -> Set[str]:
        return self.ctx.extensions

    def update_frame_buffer(self, frame_buffer_uid: int, order: Optional[int], size: Optional[Tuple[int, int]],
                            uniform_name: Optional[str], components: Optional[int] = 4, dtype: Optional[str] = "f1"):
        if frame_buffer_uid not in self._render_buffers:
            if order is None or size is None or uniform_name is None or components is None or dtype is None:
                log("Attempted to update a non-existant frame buffer! When creating a new frame buffer, no "
                    "arguments can be set to None.", severity=logging.ERROR)
                return
        else:
            old_rb = self._render_buffers[frame_buffer_uid]
            order = old_rb.order if order is None else order
            size = old_rb.render_texture.size if size is None else size
            uniform_name = old_rb.uniform_name if uniform_name is None else uniform_name
            components = old_rb.render_texture.components if components is None else components
            dtype = old_rb.render_texture.dtype if dtype is None else dtype

        # TODO: It might make sense to decouple the moderngl dtype from our dtype if this is meant to be used by an
        #  abstract class.
        resolution = (min(size[0], self.ctx.info["GL_MAX_VIEWPORT_DIMS"][0]),
                      min(size[1], self.ctx.info["GL_MAX_VIEWPORT_DIMS"][1]))

        # Note that this is less efficient than a 'renderbuffer', but it allows for read back
        color_attachment = self.ctx.texture(resolution, components=components, dtype=dtype)
        depth_attachment = self.ctx.depth_texture(resolution)
        fb = self.ctx.framebuffer(color_attachment, depth_attachment)

        if frame_buffer_uid in self._render_buffers:
            render_buffer = self._render_buffers[frame_buffer_uid]
            render_buffer.frame_buffer = fb
            render_buffer.render_texture = cast(moderngl.Texture, fb.color_attachments[0])
            render_buffer.uniform_name = uniform_name
        else:
            self._render_buffers[frame_buffer_uid] = SSVRenderBufferOpenGL(
                order, self.ctx.gc_mode is None, fb, cast(moderngl.Texture, fb.color_attachments[0]), {}, uniform_name
            )

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
                program[uniform_name].value = value  # type: ignore

        if frame_buffer_uid is not None and frame_buffer_uid not in self._render_buffers:
            log(f"Couldn't set uniform in render buffer {frame_buffer_uid} as it doesn't exist!",
                severity=logging.ERROR)
            return
        if (draw_call_uid is not None and
                (frame_buffer_uid is None or
                 draw_call_uid not in self._render_buffers[frame_buffer_uid].draw_calls)):
            log(f"Couldn't set uniform in draw call {draw_call_uid} for render buffer {frame_buffer_uid} as it "
                f"doesn't exist!", severity=logging.ERROR)
            return

        # Based on whether a frame buffer and/or vertex buffer are specified we either update the uniform
        # locally or globally.
        # TODO: For high-performance scenarios we could probably improve performance by using uniform blocks
        if frame_buffer_uid is not None:
            if draw_call_uid is not None:
                shader = self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid].shader_program
                update_internal(shader)  # type: ignore
            else:
                [update_internal(vb.shader_program) for vb in  # type: ignore
                 self._render_buffers[frame_buffer_uid].draw_calls.values()]
        else:
            [update_internal(vb.shader_program)  # type: ignore
             for rb in self._ordered_render_buffers for vb in rb.draw_calls.values()]

    def update_vertex_buffer(self, frame_buffer_uid: int, draw_call_uid: int,
                             vertex_array: Optional[npt.NDArray], index_array: Optional[npt.NDArray],
                             vertex_attributes: Optional[Tuple[str]]):
        if frame_buffer_uid not in self._render_buffers:
            log(f"Attempted to update the vertex buffer for a non-existant render buffer (id={frame_buffer_uid})!",
                severity=logging.ERROR)
            return

        if draw_call_uid not in self._render_buffers[frame_buffer_uid].draw_calls:
            # Create a new draw call
            draw_call = SSVDrawCall()
            draw_call.order = 0
            draw_call.shader_program = None
            self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid] = draw_call
            draw_call.vertex_buffer = (self._default_vertex_buffer if vertex_array is None else
                                       self.ctx.buffer(vertex_array))
            draw_call.index_buffer = None if index_array is None else self.ctx.buffer(index_array)
        else:
            # Update an existing draw call
            draw_call = self._render_buffers[frame_buffer_uid].draw_calls[draw_call_uid]
            if (vertex_array is not None
                    and draw_call.vertex_buffer is not None
                    and not isinstance(draw_call.vertex_buffer.mglo, moderngl.InvalidObject)
                    and draw_call.vertex_buffer.size == len(vertex_array) * vertex_array.dtype.itemsize):
                draw_call.vertex_buffer.write(vertex_array)
            else:
                if draw_call.vertex_buffer is not None and draw_call.vertex_buffer is not self._default_vertex_buffer:
                    draw_call.vertex_buffer.release()
                draw_call.vertex_buffer = (self._default_vertex_buffer if vertex_array is None else
                                           self.ctx.buffer(vertex_array))

            if (index_array is not None
                    and draw_call.index_buffer is not None
                    and not isinstance(draw_call.index_buffer.mglo, moderngl.InvalidObject)
                    and draw_call.index_buffer.size == len(index_array) * index_array.dtype.itemsize):
                draw_call.index_buffer.write(index_array)
            else:
                if draw_call.index_buffer is not None:
                    draw_call.index_buffer.release()
                draw_call.index_buffer = None if index_array is None else self.ctx.buffer(index_array)

        draw_call.vertex_attributes = (self._default_vertex_buffer_vertex_attributes if vertex_attributes is None else
                                       vertex_attributes)
        try:
            if draw_call.shader_program is not None:
                if draw_call.gl_vertex_array is not None:
                    draw_call.gl_vertex_array.release()
                draw_call.gl_vertex_array = self.ctx.vertex_array(draw_call.shader_program, draw_call.vertex_buffer,
                                                                  *draw_call.vertex_attributes,
                                                                  index_buffer=draw_call.index_buffer)
        except KeyError as e:
            log(f"Couldn't find required vertex attribute '{e.args[0]}' in shader!", severity=logging.ERROR)
            return

    def delete_vertex_buffer(self, frame_buffer_uid: int, draw_call_uid: int):
        if frame_buffer_uid not in self._render_buffers:
            log(f"Can't delete vertex buffer from non existant frame buffer fb_uid={frame_buffer_uid}!",
                severity=logging.ERROR)
            return
        if draw_call_uid not in self._render_buffers[frame_buffer_uid].draw_calls:
            log(f"Can't delete non existant vertex buffer fb_uid={frame_buffer_uid} vb_uid={draw_call_uid}!",
                severity=logging.ERROR)
            return
        rb = self._render_buffers[frame_buffer_uid]
        draw_call = rb.draw_calls.pop(draw_call_uid)
        draw_call.release(rb.needs_gc, release_vb=draw_call.vertex_buffer != self._default_vertex_buffer)

    def register_shader(self, frame_buffer_uid: int, draw_call_uid: int,
                        vertex_shader: str, fragment_shader: Optional[str],
                        tess_control_shader: Optional[str], tess_evaluation_shader: Optional[str],
                        geometry_shader: Optional[str], compute_shader: Optional[str],
                        primitive_type: Optional[str] = None):
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
        # draw_call.gl_vertex_array.release()

        try:
            draw_call.shader_program = (
                self.ctx.program(vertex_shader=vertex_shader, fragment_shader=fragment_shader,
                                 geometry_shader=geometry_shader,
                                 tess_control_shader=tess_control_shader,
                                 tess_evaluation_shader=tess_evaluation_shader))

            draw_call.primitive_type = cast(int, moderngl.TRIANGLES if primitive_type is None
                                            else PRIMITIVE_TYPES[primitive_type])

            # Creating a new shader program invalidates any previously bound vertex arrays, so we need to recreate it.
            # Annoyingly, to support the "default" case where the user doesn't call update_vertex_buffer() we need to
            # create this vertex array no matter what; even if the user subsequently calls update_vertex_buffer which
            # would replace this vertex array.
            try:
                # log(f"Registering shader! fb_uid={frame_buffer_uid}; dc_uid={draw_call_uid}. "
                #     f"vb={draw_call.vertex_buffer}", severity=logging.INFO)
                draw_call.gl_vertex_array = self.ctx.vertex_array(draw_call.shader_program, draw_call.vertex_buffer,
                                                                  *draw_call.vertex_attributes,
                                                                  index_buffer=draw_call.index_buffer)
            except KeyError as e:
                log(f"Couldn't find required vertex attribute '{e.args[0]}' in shader! Check that the attribute "
                    f"is defined in the vertex shader and that it's being used by the shader, otherwise the shader "
                    f"compiler may have optimised it out.", severity=logging.ERROR)
                return
        except moderngl.Error as e:
            log(f"Error while registering shader! fb_uid={frame_buffer_uid}; dc_uid={draw_call_uid}. "
                f"Exception details:\n{e}", severity=logging.ERROR)

        # Set the resolution uniform as soon as the program is created
        fb = self._render_buffers[frame_buffer_uid].frame_buffer
        self.update_uniform(frame_buffer_uid, draw_call_uid, "uResolution", (fb.width, fb.height, 0, 0))

    def update_texture(self, texture_uid: int, data: npt.NDArray, uniform_name: Optional[str],
                       override_dtype: Optional[str],
                       rect: Optional[Union[Tuple[int, int, int, int], Tuple[int, int, int, int, int, int]]],
                       treat_as_normalized_integer: bool):
        if texture_uid not in self._texture_objects:
            # Try to determine the shape of the texture to create
            components, depth, height, width, dtype = determine_texture_shape(data, override_dtype,
                                                                              treat_as_normalized_integer)

            if width <= 0 or dtype is None:
                log(f"Couldn't create texture, invalid format", severity=logging.ERROR)
                return

            # Texture doesn't already exist, create a new one
            if uniform_name is None:
                log(f"Couldn't create texture, uniform_name must not be None", severity=logging.ERROR)
                return
            try:
                texture: Union[moderngl.Texture, moderngl.Texture3D]
                if depth > 1:
                    texture = self.ctx.texture3d((depth, height, width), components, data, dtype=dtype)
                else:
                    texture = self.ctx.texture((height, width), components, data, dtype=dtype)
                self._texture_objects[texture_uid] = SSVTextureOpenGL(texture, uniform_name)
            except Exception as e:
                log(f"Couldn't create texture: \n{e}", severity=logging.ERROR)
                return
        else:
            # Update an existing texture
            # We don't call determine_texture_shape() as we assume shape matches our current texture shape, but just in
            # case we try except the texture write in case the shape is grossly wrong.
            ssv_texture = self._texture_objects[texture_uid]
            if uniform_name is not None:
                ssv_texture.uniform_name = uniform_name
            try:
                if rect is not None:
                    if isinstance(ssv_texture.texture, moderngl.Texture):
                        assert len(rect) == 4
                    else:
                        assert len(rect) == 6
                # The type constraint is validated just above, but mypy doesn't recognise it...
                ssv_texture.texture.write(data, rect)  # type: ignore
            except Exception as e:
                log(f"Couldn't update texture: \n{e}", severity=logging.ERROR)
                return

    def update_texture_sampler(self, texture_uid: int, repeat_x: Optional[bool], repeat_y: Optional[bool],
                               linear_filtering: Optional[bool], linear_mipmap_filtering: Optional[bool],
                               anisotropy: Optional[int],
                               build_mip_maps: bool):
        if texture_uid not in self._texture_objects:
            log(f"Couldn't update texture sampling settings for non-existant texture: {texture_uid}",
                severity=logging.ERROR)
            return

        texture = self._texture_objects[texture_uid].texture
        if build_mip_maps:
            texture.build_mipmaps()

        # Only update parameters which are not None
        if repeat_x is not None:
            texture.repeat_x = repeat_x
        if repeat_y is not None:
            texture.repeat_y = repeat_y

        if linear_filtering is not None:
            old_filter = texture.filter
            if old_filter[0] >= cast(int, moderngl.NEAREST_MIPMAP_NEAREST):
                # Texture has mipmaps
                mipmap = (old_filter[0] == moderngl.LINEAR_MIPMAP_LINEAR
                          or old_filter[0] == moderngl.NEAREST_MIPMAP_LINEAR)
                if linear_filtering:
                    texture.filter = (cast(int, moderngl.LINEAR_MIPMAP_LINEAR if mipmap
                                           else moderngl.LINEAR_MIPMAP_NEAREST),
                                      cast(int, moderngl.LINEAR))
                else:
                    texture.filter = (cast(int, moderngl.NEAREST_MIPMAP_LINEAR if mipmap
                                           else moderngl.NEAREST_MIPMAP_NEAREST),
                                      cast(int, moderngl.NEAREST))
            else:
                # Texture doesn't use mipmaps
                if linear_filtering:
                    texture.filter = (cast(int, moderngl.LINEAR), cast(int, moderngl.LINEAR))
                else:
                    texture.filter = (cast(int, moderngl.NEAREST), cast(int, moderngl.NEAREST))

        if linear_mipmap_filtering is not None:
            if texture.filter[0] >= cast(int, moderngl.NEAREST_MIPMAP_NEAREST):
                # Texture has mipmaps
                linear = texture.filter[1] == cast(int, moderngl.LINEAR)
                if linear:
                    texture.filter = (cast(int, moderngl.LINEAR_MIPMAP_LINEAR if linear_mipmap_filtering else
                                           moderngl.LINEAR_MIPMAP_NEAREST),
                                      cast(int, moderngl.LINEAR))
                else:
                    texture.filter = (cast(int, moderngl.NEAREST_MIPMAP_LINEAR if linear_mipmap_filtering else
                                           moderngl.NEAREST_MIPMAP_NEAREST),
                                      cast(int, moderngl.NEAREST))

        if anisotropy is not None:
            if 1 < anisotropy < 16:
                texture.anisotropy = float(anisotropy)  # type: ignore
            else:
                log(f"Texture anisotropy must be between 1 and 16. (got: {anisotropy})", logging.WARN)

    def delete_texture(self, texture_uid: int):
        if texture_uid in self._texture_objects:
            del self._texture_objects[texture_uid]

    def _bind_textures(self, program: moderngl.Program):
        image_unit = 0
        # Bind all the render buffers
        for fb in self._render_buffers.values():
            if fb.uniform_name in program:
                program[fb.uniform_name].value = image_unit  # type: ignore
                fb.render_texture.use(image_unit)  # type: ignore
                image_unit += 1
        # Bind all the user textures
        # log(f"Textures: [{', '.join([x.uniform_name for x in self._texture_objects.values()])}]; "
        #     f"Program uniforms: [{', '.join([x for x in program._members.keys()])}]", severity=logging.INFO)
        for texture in self._texture_objects.values():
            if texture.uniform_name in program:
                program[texture.uniform_name].value = image_unit  # type: ignore
                texture.texture.use(image_unit)
                image_unit += 1

    def render(self):
        if 0 not in self._render_buffers:
            log("Render pipeline not yet initialised! No render buffer bound to the output framebuffer.",
                severity=logging.ERROR)
            return False

        if self._renderdoc_is_capturing:
            self._renderdoc_api.start_frame_capture(None, None)

        self.update_uniform(None, None, "uTime", time.time() - self._start_time)
        self.update_uniform(None, None, "uFrame", self._frame_no)
        self._frame_no += 1

        for rb in self._ordered_render_buffers:
            rb.frame_buffer.use()

            # Sort the draw calls
            # TODO: This puts unnecessary pressure on the GC, it would be faster if sorting was only done when needed
            #  and didn't allocate a new list.
            draw_calls = sorted(rb.draw_calls.values(), key=lambda x: x.order)

            self.ctx.clear()
            # log(f"#### BEGIN DRAW ####", severity=logging.INFO)
            for dc in draw_calls:
                if dc.gl_vertex_array is not None:
                    # log(f"DRAW CALL: o={dc.order} v_attrs={dc.vertex_attributes}", severity=logging.INFO)
                    self._bind_textures(dc.shader_program)
                    dc.gl_vertex_array.render(mode=dc.primitive_type)

        if self._renderdoc_is_capturing:
            result = self._renderdoc_api.end_frame_capture(None, None)
            if result:
                n = self._renderdoc_api.get_num_captures()
                valid, filepath, _, timestamp = self._renderdoc_api.get_capture(n - 1)
                log(f"Renderdoc captured frame successfully! Capture index = {n - 1}; filepath = '{filepath}'",
                    severity=logging.INFO)
            else:
                log(f"Renderdoc failed to capture the frame!", severity=logging.WARN)
        self._renderdoc_is_capturing = False

        return True

    def read_frame(self, components: int = 4, frame_buffer_uid: int = 0):
        return self._render_buffers[frame_buffer_uid].frame_buffer.read(components=components)

    def read_frame_into(self, buffer, components: int = 4, frame_buffer_uid: int = 0):
        self._render_buffers[frame_buffer_uid].frame_buffer.read_into(buffer, components=components)

    def renderdoc_capture_frame(self, filename: Optional[str]):
        if self._renderdoc_api is not None:
            self._renderdoc_api.set_capture_file_path_template(filename)
            if not self._renderdoc_api.is_target_control_connected():
                self._renderdoc_api.launch_replay_ui(True, None)
            else:
                self._renderdoc_api.show_replay_ui()
            self._renderdoc_is_capturing = True

    def set_start_time(self, start_time: float):
        self._start_time = start_time
