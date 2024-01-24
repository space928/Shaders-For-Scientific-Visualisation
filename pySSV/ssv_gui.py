#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import copy
import math

import numpy as np
import numpy.typing as npt
from typing import Callable, Optional, Union, Tuple, List, Dict
from enum import IntFlag, IntEnum
import logging
import sys
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

from .ssv_canvas import SSVCanvas
from .ssv_render_buffer import SSVRenderBuffer
from .ssv_vertex_buffer import SSVVertexBuffer
from .ssv_colour import Colour
from . import ssv_colour
from .ssv_future import Reference
from .ssv_fonts import SSVFont, SSVCharacterDefinition, ssv_font_noto_sans_sb
from .ssv_callback_dispatcher import SSVCallbackDispatcher
from .ssv_logging import log


class SSVGUIShaderMode(IntFlag):
    """
    Represents the shader features needed to render a GUI element when using the built-in UI shader.
    """
    SOLID = 0,
    TRANSPARENT = 1,
    TEXT = 2,
    TEXTURE = 4,
    SHADOWED = 8,
    ROUNDING = 16,
    OUTLINE = 32

    @staticmethod
    def get_vertex_attributes(shader_mode: int) -> Tuple[str, ...]:
        """
        Gets the tuple of vertex attribute names required to support this shader mode.

        :param shader_mode:
        :return:
        """
        attributes = ["in_vert", "in_color"]
        if SSVGUIShaderMode.TEXT & shader_mode > 0:
            attributes.append("in_char")
        if (SSVGUIShaderMode.ROUNDING | SSVGUIShaderMode.TEXTURE) & shader_mode > 0:
            attributes.append("in_texcoord")
        if SSVGUIShaderMode.ROUNDING & shader_mode > 0:
            attributes.append("in_size")

        return tuple(attributes)


class TextAlign(IntEnum):
    LEFT = 0,
    CENTRE = 1,
    CENTER = 1,
    RIGHT = 2


class Rect:
    """
    Represents a 2D rectangle in pixel space.
    """
    x: int
    y: int
    width: int
    height: int

    def __init__(self, x: int = 0, y: int = 0, width: int = 20, height: int = 20):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __copy__(self):
        return Rect(self.x, self.y, self.width, self.height)

    def __str__(self):
        return f"Rect[x: {self.x}, y: {self.y}, width: {self.width}, height: {self.height}]"


class CachedVertexArray:
    """
    Stores an SSVVertexBuffer and a reusable numpy vertex array.

    :meta private:
    """
    vertex_buff: SSVVertexBuffer
    v_array: npt.NDArray
    used_space: int


SSVGUIDrawDelegate: TypeAlias = Callable[["SSVGUI", Rect], None]
"""
A delegate for a GUIElement draw function. It should follow the signature: ``draw(gui: SSVGUI, rect: Rect) -> None``
"""

SSVGUIPreLayoutDelegate: TypeAlias = Callable[["SSVGUI"], Tuple[int, int]]
"""
A delegate for a GUIElement pre layout function. It should follow the signature: 
``draw(gui: SSVGUI) -> tuple[width: int, height: int]``
"""


class SSVGUIElement:
    """
    A class representing a single GUI element for use by the layout engine.
    """
    draw_func: SSVGUIDrawDelegate
    pre_layout_func: Optional[SSVGUIPreLayoutDelegate]
    expand: bool
    layout: bool
    overlay_last: bool
    control_width: int
    control_height: int

    def __init__(self, draw_func: SSVGUIDrawDelegate, control_width: int, control_height: int,
                 expand: bool, layout: bool, overlay_last: bool, pre_layout_func: Optional[SSVGUIPreLayoutDelegate]):
        self.draw_func = draw_func
        self.control_width = control_width
        self.control_height = control_height
        self.expand = expand
        self.layout = layout
        self.overlay_last = overlay_last
        self.pre_layout_func = pre_layout_func


class SSVGUILayoutContainer:
    """
    A GUILayoutContainer stores a list gui elements (represented by their draw functions). It automatically lays out
    all of its elements either vertically or horizontally when its ``draw()`` method is called. An
    ``SSVGUILayoutContainer`` can itself be put inside another layout container.
    """

    def __init__(self, gui: "SSVGUI", vertical: bool = True,
                 enabled: Union[bool, Reference[bool]] = True,
                 squeeze: bool = False, pad: bool = False):
        self.vertical = vertical
        self._squeeze = squeeze
        self._pad = pad
        self._enabled = enabled
        self._gui = gui
        self._gui_elements: List[SSVGUIElement] = []

    def draw(self, gui: "SSVGUI", max_bounds: Rect):
        """
        Lays out and draws all the elements within this container in the order they were added.

        :param gui: the parent ``SSVGUI`` instance.
        :param max_bounds: the rect representing the space to fit elements within.
        """
        if isinstance(self._enabled, Reference):
            if not self._enabled.result:
                return
        else:
            if not self._enabled:
                return

        # log(f"Drawing layout group... bounds={max_bounds} vertical={self.vertical} lw:{gui.layout_control_width} lh:{gui.layout_control_height} elements={len(self._gui_elements)}", severity=logging.INFO)

        # Apply padding if needed
        px0, py0, px1, py1 = gui.padding
        bounds_padded = copy.copy(max_bounds)
        if self._pad:
            Rect(max_bounds.x + px0, max_bounds.y + py0, max_bounds.width - px1, max_bounds.height - py1)
        bound_dim = (bounds_padded.height if self.vertical else bounds_padded.width)

        # Call all the pre-layout callbacks in this group
        for el in self._gui_elements:
            if el.pre_layout_func is not None:
                el.control_width, el.control_height = el.pre_layout_func(gui)

        # Work out if all the elements are going to fit inside this container with the layout width/height
        layout_elements = [e for e in self._gui_elements if e.layout and not e.overlay_last]
        free_space = bound_dim - sum([e.control_height if self.vertical else e.control_width for e in layout_elements])
        if free_space >= 0:
            # There's space to spare => expand any elements that requested it to fill the space
            expanded_elements = [el for el in layout_elements if el.expand]
            pre_exp_free_space = bound_dim - sum([el.control_height if self.vertical else el.control_width
                                                  for el in expanded_elements])
            exp_dim = 0 if len(expanded_elements) == 0 else pre_exp_free_space / len(expanded_elements)
        else:
            # There's not enough space => share it evenly
            exp_dim = bound_dim / len(layout_elements)
        squeezing = self._squeeze and free_space < 0

        x, y = float(bounds_padded.x), float(bounds_padded.y)
        last_bounds = copy.copy(max_bounds)
        for element in self._gui_elements:
            # noinspection PyProtectedMember
            gui._control_ind += 1
            if not element.layout:
                element.draw_func(gui, bounds_padded)
                continue
            if element.overlay_last:
                element.draw_func(gui, last_bounds)
                continue

            # log(f"   element expand={element.expand} cw={element.control_width} exp_dim={exp_dim} x={x} y={y}", severity=logging.INFO)
            if self.vertical:
                flex_dim = exp_dim if element.expand or squeezing else element.control_height
                last_bounds = Rect(round(x), round(y), min(bounds_padded.width, element.control_width), round(flex_dim))
                element.draw_func(gui, last_bounds)
                y += flex_dim
            else:
                flex_dim = exp_dim if element.expand or squeezing else element.control_width
                last_bounds = Rect(round(x), round(y), round(flex_dim), min(bounds_padded.height, element.control_height))
                element.draw_func(gui, last_bounds)
                x += flex_dim

    @property
    def min_width(self) -> int:
        """Measures the minimum width of a given layout group by recursively measuring all of its children."""
        return sum([e.control_width if e.pre_layout_func is None else e.pre_layout_func(self._gui)[0]
                    for e in self._gui_elements if e.layout and not e.overlay_last])

    @property
    def min_height(self) -> int:
        """Measures the minimum height of a given layout group by recursively measuring all of its children."""
        return sum([e.control_height if e.pre_layout_func is None else e.pre_layout_func(self._gui)[1]
                    for e in self._gui_elements if e.layout and not e.overlay_last])

    def add_element(self, draw_callback: SSVGUIDrawDelegate, control_width: int, control_height: int,
                    expand: bool = False, layout: bool = True, overlay_last: bool = False,
                    pre_layout_callback: Optional[SSVGUIPreLayoutDelegate] = None):
        """
        Adds a GUI element to this Layout Container.

        :param draw_callback: the draw function of the GUI element
        :param control_width: the requested width of the control. The layout engine can give a larger width than this
                              if the ``expand`` option is enabled; if the layout group has ``squeeze`` enabled, the
                              actual width may be smaller than requested.
        :param control_height: the requested height of the control. The layout engine can give a larger height than this
                              if the ``expand`` option is enabled; if the layout group has ``squeeze`` enabled, the
                              actual height may be smaller than requested.
        :param expand: whether the element should attempt to fill all remaining space in the container. If multiple
                       elements have ``expand`` set, then the remaining space is shared. The element's minimum size is
                       still determined by the defined layout size.
        :param layout: whether this element should participate in automatic layout. If disabled, the element doesn't
                       count towards layout calculations and is given the full ``Rect`` of the Layout Container. The
                       element will still be drawn in the order specified.
        :param overlay_last: whether this element should be overlaid on top of the last element drawn.
        :param pre_layout_callback: the callback is invoked just before the element is laid out, it's useful for Layout
                                    Group elements which might not know their minimum size until just before layout.
        """
        self._gui_elements.append(SSVGUIElement(draw_callback, control_width, control_height, expand, layout,
                                                overlay_last, pre_layout_callback))


class SSVGUI:
    """
    An immediate mode GUI library for pySSV.
    """

    def __init__(self, canvas: SSVCanvas, render_buffer: SSVRenderBuffer):
        """
        Creates a new GUI and binds its event listeners to the given canvas.

        :param canvas: the canvas to get events from.
        :param render_buffer: the buffer to render into.
        """
        self.canvas = canvas
        self.render_buffer = render_buffer
        self._on_gui_callback: SSVCallbackDispatcher[Callable[[SSVGUI], None]] = SSVCallbackDispatcher()
        self._on_post_gui_callback: SSVCallbackDispatcher[Callable[[SSVGUI], None]] = SSVCallbackDispatcher()

        self._resolution = render_buffer.size
        self._vb_cache: Dict[int, CachedVertexArray] = {}
        self._layout_groups: List[SSVGUILayoutContainer] = []
        self._capturing_control_ind = -1
        self._control_ind = 0

        self._layout_control_height = 26
        self._layout_control_width = 400
        self._padding = (2, 2, 2, 2)
        self._rounding_radius = 3.0
        # TODO: Custom fonts support
        self._font = ssv_font_noto_sans_sb

        # TODO: Support multiple font textures at once
        font_tex = self.canvas.get_texture("uFontTex")
        if font_tex is not None:
            font_tex.release()
        font_tex = self.canvas.texture(self._font.bitmap, "uFontTex")
        font_tex.linear_filtering = True  # type: ignore
        font_tex.linear_mipmap_filtering = True  # type: ignore
        self._set_logging_stream = False
        self._last_mouse_down = False
        self.canvas.on_start(lambda: self._update_gui())
        self.canvas.on_mouse_event(lambda x, y, z: self._update_gui(True))
        self.canvas.on_keyboard_event(lambda x, y: self._update_gui())

    def _update_gui(self, should_set_logging_stream: bool = False):
        """
        This method is called whenever the GUI is invalidated. This is function is bound to the canvas' on_start,
        on_mouse, etc... events.

        :param should_set_logging_stream: a hack to force the logging stream to be directed to the canvas log.
        """
        if should_set_logging_stream and not self._set_logging_stream:
            # noinspection PyProtectedMember
            self.canvas._set_logging_stream()
            self._set_logging_stream = True
        for v in self._vb_cache.values():
            # Reset all the cached arrays
            v.used_space = 0
        self._layout_groups.clear()

        # All gui elements live in one big vertical layout element
        self._control_ind = 0
        self.begin_vertical()
        self._on_gui_callback(self)
        self._layout_groups[0].draw(self, Rect(0, 0, self._resolution[0], self._resolution[1]))

        # Update all the vertex buffers using the cached arrays
        for k, v in self._vb_cache.items():
            v.vertex_buff.update_vertex_buffer(v.v_array[:v.used_space], SSVGUIShaderMode.get_vertex_attributes(k))
            # If the cache array has got much larger than the amount of used space, then trim it
            if v.v_array.shape[0] > v.used_space * 2:
                # log(f"Trimming v_array for type={SSVGUIShaderMode(k).name} "
                #     f"usage={v.used_space}/{v.v_array.shape[0]}...", severity=logging.INFO)
                v.v_array = v.v_array[:v.used_space]

        self._last_mouse_down = self.canvas.mouse_down[0]
        self._on_post_gui_callback(self)

    def _get_vertex_buffer(self, render_type: int, requested_space: int) -> npt.NDArray:
        """
        Gets a vertex buffer array for the given render type to write new vertices into.

        Creates a new vertex buffer and array for the render_type if one doesn't already exist in the cache.

        :param render_type: an ``SSVGUIShaderMode`` with the type of shader needed.
        :param requested_space: how many array items of space
        :return: a slice of a vertex array to write into; all the requested space should be filled.
        """
        if render_type in self._vb_cache:
            cached = self._vb_cache[render_type]
            # Expand the cached array if needed
            if cached.v_array.shape[0] < cached.used_space + requested_space:
                # log(f"Expanding v_array for type={SSVGUIShaderMode(render_type).name} "
                #     f"usage={cached.used_space}/{cached.v_array.shape[0]} "
                #     f"(needed={cached.used_space + requested_space})...",
                #     severity=logging.INFO)
                # Get twice as much space as we need, there's a good chance more space will be requested soon...
                cached.v_array = np.pad(cached.v_array, (0, requested_space*2), 'empty')
            ret = cached.v_array[cached.used_space:cached.used_space + requested_space]
            cached.used_space += requested_space
            return ret

        cached = CachedVertexArray()
        cached.vertex_buff = self.render_buffer.vertex_buffer()
        cached.v_array = np.empty(requested_space, dtype=np.float32)
        cached.used_space = requested_space
        self._vb_cache[render_type] = cached
        options = []
        if SSVGUIShaderMode.TRANSPARENT & render_type > 0:
            options.append("--support_alpha")
        if SSVGUIShaderMode.TEXT & render_type > 0:
            options.append("--support_text")
        if SSVGUIShaderMode.TEXTURE & render_type > 0:
            options.append("--support_texture")
        if SSVGUIShaderMode.SHADOWED & render_type > 0:
            options.append("--support_shadow")
        if SSVGUIShaderMode.ROUNDING & render_type > 0:
            options.append("--support_rounding")
        if SSVGUIShaderMode.OUTLINE & render_type > 0:
            options.append("--support_outline")
        cached.vertex_buff.shader(f"#pragma SSV ui {' '.join(options)}")

        return cached.v_array

    @property
    def layout_control_height(self) -> int:
        """Gets or sets the default GUI element height."""
        return self._layout_control_height

    @layout_control_height.setter
    def layout_control_height(self, value: int):
        self._layout_control_height = value

    @property
    def layout_control_width(self) -> int:
        """Gets or sets the default GUI element width."""
        return self._layout_control_width

    @layout_control_width.setter
    def layout_control_width(self, value: int):
        self._layout_control_width = value

    @property
    def padding(self) -> Tuple[int, int, int, int]:
        """Gets or sets the amount of padding between GUI elements in pixels."""
        return self._padding

    @padding.setter
    def padding(self, value: Tuple[int, int, int, int]):
        self._padding = value

    @property
    def rounding_radius(self) -> float:
        """Gets or sets the default corner radius for GUI elements, in pixels."""
        return self._rounding_radius

    @rounding_radius.setter
    def rounding_radius(self, value: float):
        self._rounding_radius = value

    @property
    def _can_capture_mouse(self) -> bool:
        """Returns ``True`` if the current element can capture the mouse."""
        return self._capturing_control_ind < 0 or self._capturing_control_ind == self._control_ind

    @property
    def _is_capturing(self) -> bool:
        """Returns ``True`` if the current element is capturing the mouse."""
        return self._capturing_control_ind == self._control_ind

    def _capture_mouse(self, release=False):
        """
        Allows a GUI element to capture mouse until the cursor is released.

        This also updates the relevant shader uniform which other shaders can use to know if the current mouse event
        was consumed.

        :param release: whether the mouse should be released from the capture instead.
        """
        if self._can_capture_mouse:
            if release:
                self._capturing_control_ind = -1
                self.canvas.update_uniform("uSSVGUI_isCapturingMouse", 0)
            else:
                self._capturing_control_ind = self._control_ind
                self.canvas.update_uniform("uSSVGUI_isCapturingMouse", 1)

    def on_gui(self, callback: Callable[["SSVGUI"], None], remove: bool = False):
        """
        Registers/unregisters a callback to this GUI's on_gui event which is called any time the GUI is invalidated
        and needs to be redrawn.

        All GUI drawing operations should occur within the callback registered here. Calling GUI drawing functions
        outside of this callback results in undefined behaviour.

        :param callback: the callback function to register to the on_gui event.
        :param remove: whether the function passed in should be removed from the callback list.
        """
        self._on_gui_callback.register_callback(callback, remove)

    def on_post_gui(self, callback: Callable[["SSVGUI"], None], remove: bool = False):
        """
        Registers/unregisters a callback to this GUI's on_post_gui event which is called just after the GUI drawn.

        GUI drawing operations are not permitted within this callback; but any ``Reference`` values returned by GUI
        elements *will* have been updated by the time this callback is invoked.

        :param callback: the callback function to register to the on_post_gui event.
        :param remove: whether the function passed in should be removed from the callback list.
        """
        self._on_post_gui_callback.register_callback(callback, remove)

    def begin_horizontal(self, width: Optional[int] = None, height: Optional[int] = None,
                         pad: bool = False, squeeze: bool = True):
        """
        Starts a new horizontal layout group. All GUI elements created after this call will flow horizontally, left
        to right until ``end_horizontal()`` is called.

        :param width: optionally override the width of this layout group. Defaults to the current
                      ``layout_control_width``.
        :param height: optionally override the height of this layout group. Defaults to the current
                      ``layout_control_height``.
        :param pad: whether padding should be created between this layout group and the last GUI element.
        :param squeeze: whether this layout group should attempt to squeeze the elements contained within if they would
                        have otherwise overflowed.
        """
        layout = SSVGUILayoutContainer(self, False, True, squeeze, pad)

        def pre_layout(gui: "SSVGUI") -> Tuple[int, int]:
            return layout.min_width, self._layout_control_height if height is None else height

        if len(self._layout_groups) > 0:
            self._layout_groups[-1].add_element(layout.draw,
                                                self._layout_control_width if width is None else width,
                                                self._layout_control_height if height is None else height,
                                                False, pre_layout_callback=pre_layout)
        self._layout_groups.append(layout)

    def end_horizontal(self):
        """
        Ends a horizontal layout group.
        """
        if len(self._layout_groups) <= 1:
            raise ValueError(
                "Can't end base layout group! Did you call end_vertical()/end_horizontal()/end_...() too many times?")
        layout = self._layout_groups.pop()
        if layout.vertical:
            raise ValueError("Current layout group is not a horizontal group!")

    def begin_vertical(self, width: Optional[int] = None, height: Optional[int] = None,
                       pad: bool = False, squeeze: bool = False):
        """
        Starts a new vertical layout group. All GUI elements created after this call will flow vertically, top
        to bottom until ``end_vertical()`` is called.

        :param width: optionally override the width of this layout group. Defaults to the current
                      ``layout_control_width``.
        :param height: optionally override the height of this layout group. Defaults to the current
                      ``layout_control_height``.
        :param pad: whether padding should be created between this layout group and the last GUI element.
        :param squeeze: whether this layout group should attempt to squeeze the elements contained within if they would
                        have otherwise overflowed.
        """
        layout = SSVGUILayoutContainer(self, True, True, squeeze, pad)

        def pre_layout(gui: "SSVGUI") -> Tuple[int, int]:
            return self._layout_control_width if width is None else width, layout.min_height

        if len(self._layout_groups) > 0:
            self._layout_groups[-1].add_element(layout.draw,
                                                self._layout_control_width if width is None else width,
                                                self._layout_control_height if height is None else height,
                                                False, pre_layout_callback=pre_layout)
        self._layout_groups.append(layout)

    def end_vertical(self) -> SSVGUILayoutContainer:
        """
        Ends a vertical layout group.
        """
        if len(self._layout_groups) <= 1:
            raise ValueError(
                "Can't end base layout group! Did you call end_vertical()/end_horizontal()/end_...() too many times?")
        layout = self._layout_groups.pop()
        if not layout.vertical:
            raise ValueError("Current layout group is not a vertical group!")
        return layout

    def begin_toggle(self, enabled: Union[bool, Reference[bool]], width: Optional[int] = None,
                     height: Optional[int] = None,
                     pad: bool = False, squeeze: bool = False):
        """
         Starts a new toggle layout group. GUI elements contained within this group can be shown or hidden using the
         ``enabled`` field. All GUI elements created after this call will flow vertically, top  to bottom until
         ``end_toggle()`` is called.

         :param enabled: a boolean or a reference to a boolean for whether the contents of this group should be shown.
         :param width: optionally override the width of this layout group. Defaults to the current
                       ``layout_control_width``.
         :param height: optionally override the height of this layout group. Defaults to the current
                       ``layout_control_height``.
         :param pad: whether padding should be created between this layout group and the last GUI element.
         :param squeeze: whether this layout group should attempt to squeeze the elements contained within if they would
                         have otherwise overflowed.
         """
        # Dereferencing the 'enabled' value here means that it won't have been updated to the latest value from this
        # GUI update yet, but doing so prevents layout issues due to a race condition.
        _enabled = False
        if isinstance(enabled, Reference):
            _enabled = enabled.result
        else:
            _enabled = enabled
        layout = SSVGUILayoutContainer(self, True, _enabled, squeeze, pad)

        def pre_layout(gui: "SSVGUI") -> Tuple[int, int]:
            if _enabled:
                min_height = layout.min_height
            else:
                min_height = 0
            return self._layout_control_width if width is None else width, min_height

        if len(self._layout_groups) > 0:
            self._layout_groups[-1].add_element(layout.draw,
                                                self._layout_control_width if width is None else width,
                                                self._layout_control_height if height is None else height,
                                                False, pre_layout_callback=pre_layout)
        self._layout_groups.append(layout)

    def end_toggle(self):
        """
        Ends a toggle layout group.
        """
        if len(self._layout_groups) <= 1:
            raise ValueError(
                "Can't end base layout group! Did you call end_vertical()/end_horizontal()/end_...() too many times?")
        layout = self._layout_groups.pop()
        if not layout.vertical:
            raise ValueError("Current layout group is not a toggle group!")

    def _get_rect_corners(self, bounds: Rect, local_rect: Optional[Rect]) -> Tuple[float, float, float, float]:
        """
        Gets the coordinates of the bounding corners of a rect.

        :param bounds: the bounds provided by the layout engine.
        :param local_rect: optionally, a user provided rect which will be clipped with the layout engine's bounds.
        :return: x0, x1, y0, y1
        """
        x0 = bounds.x + self._padding[0]
        x1 = bounds.x + bounds.width - self._padding[2]
        y0 = bounds.y + self._padding[1]
        y1 = bounds.y + bounds.height - self._padding[3]
        if local_rect is not None:
            x0 += local_rect.x
            x1 = min(x1, x0 + local_rect.width - self._padding[2])
            y0 += local_rect.y
            y1 = min(y1, y0 + local_rect.height - self._padding[3])
        return x0, x1, y0, y1

    def space(self, width: Optional[int] = None, height: Optional[int] = None):
        """
        Creates a blank space element.

        :param width: optionally, the width of the element.
        :param height: optionally, the height of the element.
        """
        self._layout_groups[-1].add_element(lambda x, y: None,
                                            self._layout_control_width if width is None else width,
                                            self._layout_control_height // 2 if height is None else height,
                                            expand=False)

    def rect(self, colour: Colour, rect: Optional[Rect] = None, overlay_last: bool = False):
        """
        Creates a rectangle GUI element.

        :param colour: the colour of the rectangle.
        :param rect: optionally, the absolute coordinates of the rectangle to draw. These will be clipped to fit
                     within the current layout group.
        :param overlay_last: whether the layout engine should overlay this element onto the last drawn element.
        """

        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.SOLID
            if colour.a != 1:
                render_mode = SSVGUIShaderMode.TRANSPARENT

            verts = gui._get_vertex_buffer(render_mode, 6 * 6)
            col = colour.astuple
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            verts[:] = (x0, y0, *col,
                        x1, y0, *col,
                        x0, y1, *col,

                        x0, y1, *col,
                        x1, y0, *col,
                        x1, y1, *col)
            # self._update_vertex_buffer(render_mode, verts)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None, overlay_last=overlay_last)

    def rounded_rect(self, colour: Colour, outline: bool = False, radius: Optional[float] = None,
                     rect: Optional[Rect] = None, overlay_last: bool = False):
        """
        Creates a rounded rectangle GUI element.

        :param colour: the colour of the rectangle.
        :param outline: whether the rectangle should be outlined.
        :param radius: the rounding radius in pixels. This can be set to an arbitrarily high number to create
                       circles/pills. Set to ``None`` to use the GUI's ``rounding_radius``.
        :param rect: optionally, the absolute coordinates of the rectangle to draw. These will be clipped to fit
                     within the current layout group.
        :param overlay_last: whether the layout engine should overlay this element onto the last drawn element.
        """

        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.ROUNDING
            if outline:
                render_mode |= SSVGUIShaderMode.OUTLINE

            if radius is None:
                _radius = gui._rounding_radius
            else:
                _radius = radius

            verts = gui._get_vertex_buffer(render_mode, (2+4+2+2+1)*6)
            col = colour.astuple
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour,
            # vec2 texcoord, vec2 size, float radius)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            verts[:] = (x0, y0, *col, 0, 0, bounds.width, bounds.height, _radius,
                        x1, y0, *col, 1, 0, bounds.width, bounds.height, _radius,
                        x0, y1, *col, 0, 1, bounds.width, bounds.height, _radius,

                        x0, y1, *col, 0, 1, bounds.width, bounds.height, _radius,
                        x1, y0, *col, 1, 0, bounds.width, bounds.height, _radius,
                        x1, y1, *col, 1, 1, bounds.width, bounds.height, _radius)
            # verts = np.concatenate((verts, n_verts), dtype=np.float32)
            # self._update_vertex_buffer(render_mode, verts)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None, overlay_last=overlay_last)

    def _draw_chars(self, char_defs: List[SSVCharacterDefinition], pos: Tuple[float, float],
                    font_tex_size: Tuple[int, int],
                    colour: Colour, scale: float, weight: float, shear_x: float, enforce_hinting: bool,
                    render_mode: SSVGUIShaderMode):
        """
        Draws a string of characters to the GUI. This function expects that the text has already been transformed and
        clipped as needed by the caller.

        :param char_defs: a list of character definitions to draw from the font file.
        :param pos: the position in screen-space to start drawing from. The first character's bottom-left corner is
                    placed at this position; subsequent characters are placed according to the font file.
        :param font_tex_size: the size of the font bitmap in pixels. (width, height)
        :param colour: the text colour.
        :param scale: a float to scale the characters by. A value of 1 would draw the characters at the font file's
                      native size.
        :param weight: the font weight modifier (0-1).
        :param shear_x: the amount of horizontal shear to apply to characters in pixels.
        :param enforce_hinting: whether positions should be rounded to pixels to help with hinting.
        :param render_mode: the shader render mode flags for this text.
        """
        verts = self._get_vertex_buffer(render_mode, (2 + 4 + 2 + 1) * 6 * len(char_defs))
        col = colour.astuple
        vert_ind = 0
        font_width, font_height = font_tex_size[0], font_tex_size[1]
        draw_x, draw_y = pos[0], pos[1]
        if enforce_hinting:
            draw_x, draw_y = round(draw_x), round(draw_y)
        for char_def in char_defs:
            # Compute the pixel space coordinates of the character quad
            x0 = draw_x + char_def.x_offset * scale
            x1 = draw_x + char_def.x_offset * scale + char_def.width * scale
            y0 = draw_y + char_def.y_offset * scale
            y1 = draw_y + char_def.y_offset * scale + char_def.height * scale
            # Compute texture-space coordinates of the character
            bm_x0 = char_def.x / font_width
            bm_x1 = (char_def.x + char_def.width) / font_width
            bm_y0 = char_def.y / font_height
            bm_y1 = (char_def.y + char_def.height) / font_height
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour, vec2 char,
            # float weight)
            verts[vert_ind:vert_ind + (2 + 4 + 2 + 1) * 6] = (
                x0, y0, *col, bm_x0, bm_y0, 1. - weight,
                x1, y0, *col, bm_x1, bm_y0, 1. - weight,
                x0 + shear_x, y1, *col, bm_x0, bm_y1, 1. - weight,

                x0 + shear_x, y1, *col, bm_x0, bm_y1, 1. - weight,
                x1, y0, *col, bm_x1, bm_y0, 1. - weight,
                x1 + shear_x, y1, *col, bm_x1, bm_y1, 1. - weight
            )
            vert_ind += (2 + 4 + 2 + 1) * 6
            draw_x += char_def.x_advance * scale
            if enforce_hinting:
                draw_x = round(draw_x)

    def label(self, text: str, colour: Colour = ssv_colour.ui_text, font_size: Optional[float] = None,
              x_offset: int = 0, weight: float = 0.5, italic: bool = False, shadow: bool = False,
              align: TextAlign = TextAlign.LEFT, enforce_hinting: bool = True,
              rect: Optional[Rect] = None, overlay_last: bool = False):
        """
        Creates a label GUI element.

        :param text: the text to display.
        :param colour: the colour of the rectangle.
        :param font_size: the font size in pt.
        :param x_offset: how far to indent the text in pixels.
        :param weight: the font weight [0-1], where 0.5 is the native font weight. The font renderer uses SDF fonts
                       which allows variable font weight rendering for free within certain limits (since this is only
                       an effect, at the extremes type quality is degraded).
        :param italic: whether the text should be rendered in faux italic. This effect simply applies a shear
                       transformation to the rendered characters, so it will work on any font, but won't look as good
                       as a proper italic font.
        :param shadow: whether the text should be rendered with a shadow. This incurs a very small extra rendering
                       cost, and tends to have visual artifacts when the font weight is high.
        :param align: the horizontal alignment of the text.
        :param enforce_hinting: this option applies rounding to the font size and position to force it to line up with
                                the pixel grid to improve sharpness. This is only effective if the font texture was
                                rendered with hinting enabled in the first place. This can result in aliasing when
                                animating font size/text position.
        :param rect: optionally, the absolute coordinates of the rectangle to draw. These will be clipped to fit
                     within the current layout group.
        :param overlay_last: whether the layout engine should overlay this element onto the last drawn element.
        """

        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.TEXT
            if shadow:
                render_mode |= SSVGUIShaderMode.SHADOWED

            # Font sizing & positioning
            _font_size = (font_size if font_size is not None else self._font.size)
            if enforce_hinting:
                _font_size = round(_font_size)
            if font_size is not None:
                scale = _font_size / self._font.size
            else:
                scale = 1

            _weight = weight

            shear_x = -0.2 * _font_size if italic else 0
            bx, by, bwidth, bheight = (bounds.x + self._padding[0] + x_offset, bounds.y + self._padding[1],
                                       bounds.width - self._padding[2], bounds.height + self._padding[3])
            if rect is not None:
                bx += rect.x
                by += rect.y
                bwidth = min(bx + rect.width - self._padding[2], bx + bounds.width) - bx
                bheight = min(by + rect.height - self._padding[3], by + bounds.height) - by
            draw_x = bx

            # Centre on the y-axis, there's some janky tuning in here to make it behave
            diff_y = (self._font.base_height + (self._font.base_height - self._font.size * 1.3)) * scale
            draw_y = by + bheight / 2 - (min(diff_y, bheight) + diff_y) / 2
            max_x = bx + bwidth
            max_y = by + bheight
            font_width, font_height = self._font.width, self._font.height
            # if font_height*scale > bheight * 1.5:
            #     # Let's allow a little bit of overflow for now, until we have proper clipping
            #     return

            # Align on the x-axis
            if align == TextAlign.CENTER:
                fulltext_width = sum(
                    [self._font.chars.get(char, self._font.chars[' ']).x_advance for char in text]) * scale
                draw_x = round((draw_x + max_x - fulltext_width) / 2)
            elif align == TextAlign.RIGHT:
                fulltext_width = sum(
                    [self._font.chars.get(char, self._font.chars[' ']).x_advance for char in text]) * scale
                draw_x = round(max_x - fulltext_width)

            char_defs = [self._font.chars.get(char, self._font.chars[' ']) for char in text]
            # Trim the chars to fit the bounds
            trim_x = float(draw_x)
            for i, c in enumerate(char_defs):
                trim_x += c.x_advance * scale
                if trim_x > max_x:
                    # This char won't fit...
                    char_defs = char_defs[:i]
                    break

            # Now create the actual geometry for the text
            gui._draw_chars(char_defs, (draw_x, draw_y), (font_width, font_height), colour, scale,
                            _weight, shear_x, enforce_hinting, render_mode)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None, overlay_last=overlay_last)

    def label_3d(self, text: str, pos: Tuple[float, float, float],
                 colour: Colour = ssv_colour.ui_text, font_size: Optional[float] = None,
                 weight: float = 0.5, italic: bool = False, shadow: bool = False,
                 align: TextAlign = TextAlign.LEFT, enforce_hinting: bool = True):
        """
        Creates a label GUI element which is transformed in 3d space using the canvas's camera.

        :param text: the text to display.
        :param pos: the 3d position of the label.
        :param colour: the colour of the rectangle.
        :param font_size: the font size in pt.
        :param weight: the font weight [0-1], where 0.5 is the native font weight. The font renderer uses SDF fonts
                       which allows variable font weight rendering for free within certain limits (since this is only
                       an effect, at the extremes type quality is degraded).
        :param italic: whether the text should be rendered in faux italic. This effect simply applies a shear
                       transformation to the rendered characters, so it will work on any font, but won't look as good
                       as a proper italic font.
        :param shadow: whether the text should be rendered with a shadow. This incurs a very small extra rendering
                       cost, and tends to have visual artifacts when the font weight is high.
        :param align: the horizontal alignment of the text.
        :param enforce_hinting: this option applies rounding to the font size and position to force it to line up with
                                the pixel grid to improve sharpness. This is only effective if the font texture was
                                rendered with hinting enabled in the first place. This can result in aliasing when
                                animating font size/text position.
        """
        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.TEXT
            if shadow:
                render_mode |= SSVGUIShaderMode.SHADOWED

            # TODO: The camera view/projection matrix should be cached to avoid calculating it so often...
            pos_clip = gui.canvas.main_camera.view_matrix @ gui.canvas.main_camera.projection_matrix @ pos
            # Clipping planes
            if 0 > pos_clip[2] > 1:
                return
            screen_x = float((pos_clip[0]*0.5+0.5) * gui._resolution[0])
            screen_y = float((pos_clip[1]*0.5+0.5) * gui._resolution[1])

            # Font sizing & positioning
            _font_size = (font_size if font_size is not None else self._font.size)
            if enforce_hinting:
                _font_size = round(_font_size)
            if font_size is not None:
                scale = _font_size / self._font.size
            else:
                scale = 1

            _weight = weight

            shear_x = -0.2 * _font_size if italic else 0
            draw_x = screen_x

            # Centre on the y-axis, there's some janky tuning in here to make it behave
            diff_y = self._font.base_height * scale
            draw_y = screen_y + diff_y
            font_width, font_height = self._font.width, self._font.height

            # Align on the x-axis
            if align == TextAlign.CENTER:
                fulltext_width = sum(
                    [self._font.chars.get(char, self._font.chars[' ']).x_advance for char in text]) * scale
                draw_x -= fulltext_width / 2
            elif align == TextAlign.RIGHT:
                fulltext_width = sum(
                    [self._font.chars.get(char, self._font.chars[' ']).x_advance for char in text]) * scale
                draw_x -= fulltext_width

            char_defs = [self._font.chars.get(char, self._font.chars[' ']) for char in text]
            # Trim the chars to fit the bounds
            trim_x = draw_x
            i_0 = 0
            for i, c in enumerate(char_defs):
                if trim_x > gui._resolution[0]:
                    # This char (and consequently all subsequent chars) is entirely off the right edge of the screen
                    char_defs = char_defs[i_0:i]
                    break
                trim_x += c.x_advance * scale
                if trim_x < 0:
                    # This char is entirely off the left edge of the screen
                    i_0 = i

            # Now create the actual geometry for the text
            gui._draw_chars(char_defs, (draw_x, draw_y), (font_width, font_height), colour, scale,
                            _weight, shear_x, enforce_hinting, render_mode)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=False, overlay_last=False)

    def button(self, text: str, colour: Optional[Colour] = None, radius: Optional[float] = None,
               rect: Optional[Rect] = None) -> Reference[bool]:
        """
        Creates a button GUI element.

        Since the actual drawing of GUI elements is deferred till after layout has been updated (which occurs just
        after the on_gui event finishes), the result of whether the button has been clicked or not is not known when
        this method returns. Wait until the ``on_post_gui`` event (or the start of the next ``on_gui``) event to get
        the value of the button.

        :param text: the button text.
        :param colour: the colour of the button rectangle.
        :param radius: optionally, the corner radius of the button rectangle.
        :param rect: optionally, the absolute coordinates of the rectangle to draw. These will be clipped to fit
                     within the current layout group.
        :return: a reference to a boolean which will be set to ``True`` if the button was clicked.
        """
        # We want the GUI to behave like an immediate mode GUI, but since layout is deferred until after all elements
        # have been created, the result of the button press can't be checked until well after this function has been
        # called as such we return a promise which is fulfilled after the on_gui() function has finished. This still
        # allows gui elements defined *after* this one to use the result since at draw time the button's result becomes
        # available. Since this is all single threaded, the future's result should never be waited for.
        res = Reference(False)

        # noinspection DuplicatedCode
        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.ROUNDING

            verts = gui._get_vertex_buffer(render_mode, (2+4+2+2+1)*6)
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour,
            # vec2 texcoord, vec2 size, float radius)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            hover = (x0 <= gui.canvas.mouse_pos[0] <= x1) and (y0 <= gui._resolution[1] - gui.canvas.mouse_pos[1] <= y1)
            if gui._is_capturing:
                click = hover and gui.canvas.mouse_down[0]
                gui._capture_mouse(not gui.canvas.mouse_down[0])
            elif gui._can_capture_mouse:
                click = hover and gui.canvas.mouse_down[0]
                if click:
                    gui._capture_mouse()
            else:
                hover = False
                click = False
            res.result = click
            if radius is None:
                _radius = gui._rounding_radius
            else:
                _radius = radius
            if colour is None:
                if click:
                    col = ssv_colour.ui_element_bg_click.astuple
                elif hover:
                    col = ssv_colour.ui_element_bg_hover.astuple
                else:
                    col = ssv_colour.ui_element_bg.astuple
            else:
                colour_tinted = colour
                if click:
                    colour_tinted *= 0.8
                elif hover:
                    colour_tinted += .3
                col = colour_tinted.astuple
            verts[:] = (x0, y0, *col, 0, 0, bounds.width, bounds.height, _radius,
                        x1, y0, *col, 1, 0, bounds.width, bounds.height, _radius,
                        x0, y1, *col, 0, 1, bounds.width, bounds.height, _radius,

                        x0, y1, *col, 0, 1, bounds.width, bounds.height, _radius,
                        x1, y0, *col, 1, 0, bounds.width, bounds.height, _radius,
                        x1, y1, *col, 1, 1, bounds.width, bounds.height, _radius)
            # verts = np.concatenate((verts, n_verts), dtype=np.float32)
            # self._update_vertex_buffer(render_mode, verts)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None)
        self.label(text, ssv_colour.ui_text, rect=rect, font_size=14, overlay_last=True, align=TextAlign.CENTRE)
        # res.set_result(False)
        return res

    def slider(self, text: str, value: float, min_value: float = 0., max_value: float = 1., step_size: float = 0,
               power: float = 1., colour: Optional[Colour] = None, track_thickness: float = 4,
               rect: Optional[Rect] = None) -> Reference[float]:
        """
        Creates a slider GUI element.

        Since the actual drawing of GUI elements is deferred till after layout has been updated (which occurs just
        after the on_gui event finishes), the updated value of this slider is not known when this method returns.
        Wait until the ``on_post_gui`` event (or the start of the next ``on_gui``) event to get the new value of this
        slider. Until then the value returned by the slider will be the value passed in to it.

        :param text: the label of the slider.
        :param value: the current value of the slider.
        :param min_value: the minimum value of the slider.
        :param max_value: the maximum value of the slider.
        :param step_size: the step size to round the slider value to.
        :param power: an exponent to raise the value of the slider to, useful for creating non-linear sliders.
        :param colour: the colour of the rectangle.
        :param track_thickness: the thickness of the slider track in pixels.
        :param rect: optionally, the absolute coordinates of the rectangle to draw. These will be clipped to fit
                     within the current layout group.
        :return: a reference to a float which will be set to the new value of the slider.
        """
        res = value if isinstance(value, Reference) else Reference(value)

        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.ROUNDING | SSVGUIShaderMode.OUTLINE

            verts = gui._get_vertex_buffer(render_mode, (2+4+2+2+1) * 6 * 2)
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour,
            # vec2 texcoord, vec2 size, float radius)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            handle_thickness = max((y1 - y0) - 2, 2)
            half_h_thick = handle_thickness / 2
            hover = (x0 <= gui.canvas.mouse_pos[0] <= x1) and (y0 <= gui._resolution[1] - gui.canvas.mouse_pos[1] <= y1)
            if gui._is_capturing:
                click = gui.canvas.mouse_down[0]
                gui._capture_mouse(not click)
            elif gui._can_capture_mouse:
                click = hover and gui.canvas.mouse_down[0]
                if click:
                    gui._capture_mouse()
            else:
                hover = False
                click = False
            if isinstance(value, Reference):
                pos = value.result
            else:
                pos = value
            if click:
                pos = (gui.canvas.mouse_pos[0] - x0 - half_h_thick) / (x1 - x0 - handle_thickness)
                pos = min(max(pos, 0), 1)
                pos = (pos * (max_value - min_value) + min_value)
                if power != 1:
                    sign = pos
                    pos = math.copysign((abs(pos) ** power) / (max_value**power) * max_value, sign)
                if step_size > 0:
                    pos = round(pos/step_size)*step_size

            res.result = pos

            if power != 1:
                sign = pos
                pos = math.copysign((abs(pos) * (max_value ** power) / max_value) ** (1/power), sign)
            handle_x = (pos - min_value) / (max_value - min_value)
            handle_x = handle_x * (x1 - x0 - handle_thickness) + x0 + half_h_thick

            y_mid = (y0+y1)/2
            tx0 = x0 + half_h_thick
            tx1 = x1 - half_h_thick
            ty0 = y_mid - track_thickness / 2
            ty1 = y_mid + track_thickness / 2
            hx0 = handle_x - half_h_thick
            hx1 = handle_x + half_h_thick
            hy0 = y_mid - half_h_thick
            hy1 = y_mid + half_h_thick

            if colour is None:
                col_track = ssv_colour.ui_element_bg_click.astuple
                if click:
                    col = ssv_colour.ui_element_bg_click.astuple
                elif hover:
                    col = ssv_colour.ui_element_bg_hover.astuple
                else:
                    col = ssv_colour.ui_element_bg.astuple
            else:
                colour_tinted = colour
                col_track = (colour * 0.8).astuple
                if click:
                    colour_tinted *= 0.8
                elif hover:
                    colour_tinted *= 1.4
                col = colour_tinted.astuple
            # Track
            verts[:] = (tx0, ty0, *col_track, 0, 0, bounds.width, track_thickness, 1.,
                        tx1, ty0, *col_track, 1, 0, bounds.width, track_thickness, 1.,
                        tx0, ty1, *col_track, 0, 1, bounds.width, track_thickness, 1.,

                        tx0, ty1, *col_track, 0, 1, bounds.width, track_thickness, 1.,
                        tx1, ty0, *col_track, 1, 0, bounds.width, track_thickness, 1.,
                        tx1, ty1, *col_track, 1, 1, bounds.width, track_thickness, 1.,
                        # Handle
                        hx0, hy0, *col, 0, 0, handle_thickness, handle_thickness, 10.,
                        hx1, hy0, *col, 1, 0, handle_thickness, handle_thickness, 10.,
                        hx0, hy1, *col, 0, 1, handle_thickness, handle_thickness, 10.,

                        hx0, hy1, *col, 0, 1, handle_thickness, handle_thickness, 10.,
                        hx1, hy0, *col, 1, 0, handle_thickness, handle_thickness, 10.,
                        hx1, hy1, *col, 1, 1, handle_thickness, handle_thickness, 10.)
            # verts = np.concatenate((verts, n_verts), dtype=np.float32)
            # self._update_vertex_buffer(render_mode, verts)

        self.begin_horizontal(squeeze=True)
        self._layout_groups[-1].add_element(draw, self._layout_control_height, self._layout_control_height,
                                            expand=False, layout=rect is None)
        self.label(text, ssv_colour.ui_text, x_offset=4, rect=rect, font_size=14, align=TextAlign.LEFT)
        self.end_horizontal()
        return res

    def checkbox(self, text: str, value: Union[bool, Reference[bool]], colour: Optional[Colour] = None,
                 radius: Optional[float] = None,
                 rect: Optional[Rect] = None) -> Reference[bool]:
        """
        Creates a checkbox GUI element.

        Since the actual drawing of GUI elements is deferred till after layout has been updated (which occurs just
        after the on_gui event finishes), the updated value of this checkbox is not known when this method returns.
        Wait until the ``on_post_gui`` event (or the start of the next ``on_gui``) event to get the new value of this
        checkbox. Until then the value returned by the checkbox will be the value passed in to it.

        :param text: the label of the checkbox.
        :param value: whether the checkbox is currently checked.
        :param colour: the colour of the checkbox.
        :param radius: optionally, the corner radius of the checkbox.
        :param rect: optionally, the absolute coordinates of the rectangle to draw. These will be clipped to fit
                     within the current layout group.
        :return: a reference to a float which will be set to the new value of the checkbox.
        """
        res = value if isinstance(value, Reference) else Reference(value)

        # noinspection DuplicatedCode
        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.ROUNDING | SSVGUIShaderMode.OUTLINE

            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            hover = (x0 <= gui.canvas.mouse_pos[0] <= x1) and (y0 <= gui._resolution[1] - gui.canvas.mouse_pos[1] <= y1)
            if gui._is_capturing:
                click = hover and gui.canvas.mouse_down[0]
                gui._capture_mouse(not gui.canvas.mouse_down[0])
            elif gui._can_capture_mouse:
                click = hover and gui.canvas.mouse_down[0]
                if click:
                    gui._capture_mouse()
            else:
                hover = False
                click = False
            if radius is None:
                _radius = gui._rounding_radius
            else:
                _radius = radius
            if isinstance(value, Reference):
                checked = value.result
            else:
                checked = value
            if click and click != self._last_mouse_down:
                checked = not checked

            res.result = checked
            if colour is None:
                if click or checked:
                    col = ssv_colour.ui_element_bg_click.astuple
                elif hover:
                    col = ssv_colour.ui_element_bg_hover.astuple
                else:
                    col = ssv_colour.ui_element_bg.astuple
            else:
                colour_tinted = colour
                if click or checked:
                    colour_tinted *= 0.8
                elif hover:
                    colour_tinted *= 1.4
                col = colour_tinted.astuple
            verts = gui._get_vertex_buffer(render_mode, (2+4+2+2+1)*(6*3 if checked else 6))
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour,
            # vec2 texcoord, vec2 size, float radius)
            verts[:(2+4+2+2+1)*6] = (x0, y0, *col, 0, 0, bounds.width, bounds.height, _radius,
                                     x1, y0, *col, 1, 0, bounds.width, bounds.height, _radius,
                                     x0, y1, *col, 0, 1, bounds.width, bounds.height, _radius,

                                     x0, y1, *col, 0, 1, bounds.width, bounds.height, _radius,
                                     x1, y0, *col, 1, 0, bounds.width, bounds.height, _radius,
                                     x1, y1, *col, 1, 1, bounds.width, bounds.height, _radius)
            if checked:
                check_col = ssv_colour.ui_element_bg_hover.astuple
                verts[(2+4+2+2+1)*6:] = (
                    # \
                    x0, (y0 * .9 + y1 * .1), *check_col, 0, .1, bounds.width, bounds.height, _radius,
                    (x0 * .9 + x1 * .1), y0, *check_col, .1, 0, bounds.width, bounds.height, _radius,
                    (x0 * .1 + x1 * .9), y1, *check_col, .9, 1, bounds.width, bounds.height, _radius,

                    (x0 * .1 + x1 * .9), y1, *check_col, .9, 1, bounds.width, bounds.height, _radius,
                    (x0 * .9 + x1 * .1), y0, *check_col, .1, 0, bounds.width, bounds.height, _radius,
                    x1, (y0 * .1 + y1 * .9), *check_col, 1, .9, bounds.width, bounds.height, _radius,
                    # /
                    (x0 * .1 + x1 * .9), y0, *check_col, .9, 0, bounds.width, bounds.height, _radius,
                    x1, (y0 * .9 + y1 * .1), *check_col, 1, .1, bounds.width, bounds.height, _radius,
                    x0, (y0 * .1 + y1 * .9), *check_col, 0, .9, bounds.width, bounds.height, _radius,

                    x1, (y0 * .9 + y1 * .1), *check_col, 1, .1, bounds.width, bounds.height, _radius,
                    x0, (y0 * .1 + y1 * .9), *check_col, 0, .9, bounds.width, bounds.height, _radius,
                    (x0 * .9 + x1 * .1), y1, *check_col, .1, 1, bounds.width, bounds.height, _radius)
            # verts = np.concatenate((verts, n_verts), dtype=np.float32)
            # self._update_vertex_buffer(render_mode, verts)

        self.begin_horizontal(squeeze=False)
        self._layout_groups[-1].add_element(draw, self._layout_control_height, self._layout_control_height,
                                            expand=False, layout=rect is None)
        self.label(text, ssv_colour.ui_text, x_offset=4, rect=rect, font_size=14, align=TextAlign.LEFT)
        self.end_horizontal()
        return res


def create_gui(canvas: SSVCanvas) -> SSVGUI:
    """
    Creates a new full screen GUI and render buffer and binds it to the canvas (the render buffer's order defaults to
    100).

    :param canvas: the canvas to bind to.
    :return: a new ``SSVGUI`` object
    """
    rb = canvas.render_buffer(canvas.size, order=100)
    # Empty the full screen vertex buffer so that it has no effect
    rb.shader("""#pragma SSV full_screen_colour --colour "vec4(0.)" """)
    vb = canvas.main_render_buffer.vertex_buffer()
    # The default vertex array in a vertex buffer is the full screen vertex array, so no need to change it
    # vb.update_vertex_buffer()
    # Now render our GUI on top of the main render buffer
    vb.shader(f"""
    #pragma SSV pixel mainImage
    vec4 mainImage(in vec2 fragCoord)
    {{
        vec2 uv = fragCoord/uResolution.xy;
        vec4 col = texture({rb.render_buffer_name}, uv);
        col.rgb /= col.a;
        return col;
    }}
    """)
    gui = SSVGUI(canvas, rb)
    return gui
