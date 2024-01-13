#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import copy

import numpy as np
import numpy.typing as npt
from typing import Callable, Optional, Union, NewType
from enum import IntFlag, IntEnum
import logging

from .ssv_canvas import SSVCanvas
from .ssv_render_buffer import SSVRenderBuffer
from .ssv_vertex_buffer import SSVVertexBuffer
from .ssv_colour import Colour
from . import ssv_colour
from .ssv_future import Reference
from .ssv_fonts import SSVFont, ssv_font_noto_sans_sb
from . import log


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
    def get_vertex_attributes(shader_mode: int) -> tuple[str, ...]:
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


SSVGUIDrawDelegate = NewType("SSVGUIDrawDelegate", Callable[["SSVGUI", Rect], None])
"""
A delegate for a GUIElement draw function. It should follow the signature: ``draw(gui: SSVGUI, rect: Rect) -> None``
"""

SSVGUIPreLayoutDelegate = NewType("SSVGUIPreLayoutDelegate", Callable[["SSVGUI"], tuple[int, int]])
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
        self._gui_elements: list[SSVGUIElement] = []

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

        x, y = bounds_padded.x, bounds_padded.y
        last_bounds = copy.copy(max_bounds)
        for element in self._gui_elements:
            if not element.layout:
                element.draw_func(gui, bounds_padded)
                continue
            if element.overlay_last:
                element.draw_func(gui, last_bounds)
                continue

            # log(f"   element expand={element.expand} cw={element.control_width} exp_dim={exp_dim} x={x} y={y}", severity=logging.INFO)
            if self.vertical:
                flex_dim = exp_dim if element.expand or squeezing else element.control_height
                last_bounds = Rect(x, y, min(bounds_padded.width, element.control_width), flex_dim)
                element.draw_func(gui, last_bounds)
                y += flex_dim
            else:
                flex_dim = exp_dim if element.expand or squeezing else element.control_width
                last_bounds = Rect(x, y, flex_dim, min(bounds_padded.height, element.control_height))
                element.draw_func(gui, last_bounds)
                x += flex_dim

    @property
    def min_width(self) -> int:
        """Measures the minimum width of a given layout group by recursively measuring all of its children."""
        return sum([e.control_width if e.pre_layout_func is None else e.pre_layout_func(self)[0] for e in self._gui_elements if e.layout and not e.overlay_last])

    @property
    def min_height(self) -> int:
        """Measures the minimum height of a given layout group by recursively measuring all of its children."""
        return sum([e.control_height if e.pre_layout_func is None else e.pre_layout_func(self)[1] for e in self._gui_elements if e.layout and not e.overlay_last])

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
        self.canvas = canvas
        self.render_buffer = render_buffer
        self._on_gui_callback = lambda x: None

        self._resolution = render_buffer.size
        self._vb_cache: dict[int, tuple[SSVVertexBuffer, npt.NDArray]] = {}
        self._layout_groups: list[SSVGUILayoutContainer] = []

        self._layout_control_height = 26
        self._layout_control_width = 400
        self._padding = (2, 2, 2, 2)
        # TODO: Custom fonts support
        self._font = ssv_font_noto_sans_sb

        # TODO: Support multiple font textures at once
        font_tex = self.canvas.get_texture("uFontTex")
        if font_tex is not None:
            font_tex.release()
        font_tex = self.canvas.texture(self._font.bitmap, "uFontTex")
        font_tex.linear_filtering = True
        font_tex.linear_mipmap_filtering = True
        self._set_logging_stream = False
        self._last_mouse_down = False
        self.canvas.on_start(lambda: self._update_gui())
        self.canvas.on_mouse_event(lambda x, y, z: self._update_gui(True))
        self.canvas.on_keyboard_event(lambda x, y: self._update_gui())

    def _update_gui(self, should_set_logging_stream: bool = False):
        if should_set_logging_stream and not self._set_logging_stream:
            self.canvas._set_logging_stream()
            self._set_logging_stream = True
        for k, v in self._vb_cache.items():
            self._vb_cache[k] = (v[0], np.empty(0, np.float32))
        self._layout_groups.clear()

        # All gui elements live in one big vertical layout element
        self.begin_vertical()
        self._on_gui_callback(self)
        self._layout_groups[0].draw(self, Rect(0, 0, self._resolution[0], self._resolution[1]))
        for k, v in self._vb_cache.items():
            v[0].update_vertex_buffer(v[1], SSVGUIShaderMode.get_vertex_attributes(k))
        self._last_mouse_down = self.canvas.mouse_down[0]

    def _get_vertex_buffer(self, render_type: int) -> npt.NDArray:
        if render_type in self._vb_cache:
            return self._vb_cache[render_type][1]

        vb = self.render_buffer.vertex_buffer()
        v_array = np.empty(0, dtype=np.float32)
        self._vb_cache[render_type] = vb, v_array
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
            # options.append("--rounding_radius 20.")
        if SSVGUIShaderMode.OUTLINE & render_type > 0:
            options.append("--support_outline")
        vb.shader(f"#pragma SSV ui {' '.join(options)}")

        return v_array

    def _update_vertex_buffer(self, render_type: int, vertex_array: npt.NDArray):
        assert render_type in self._vb_cache

        vb = self._vb_cache[render_type][0]
        self._vb_cache[render_type] = vb, vertex_array

    @property
    def layout_control_height(self) -> int:
        return self._layout_control_height

    @layout_control_height.setter
    def layout_control_height(self, value: int):
        self._layout_control_height = value

    @property
    def layout_control_width(self) -> int:
        return self._layout_control_width

    @layout_control_width.setter
    def layout_control_width(self, value: int):
        self._layout_control_width = value

    @property
    def padding(self):
        return self._padding

    @padding.setter
    def padding(self, value: tuple[int, int, int, int]):
        self._padding = value

    def on_gui(self, callback: Callable[["SSVGUI"], None]):
        self._on_gui_callback = callback

    def begin_horizontal(self, width: Optional[int] = None, height: Optional[int] = None,
                         pad: bool = False, squeeze: bool = True):
        layout = SSVGUILayoutContainer(self, False, True, squeeze, pad)

        def pre_layout(gui: "SSVGUI") -> tuple[int, int]:
            return layout.min_width, self._layout_control_height if height is None else height

        if len(self._layout_groups) > 0:
            self._layout_groups[-1].add_element(layout.draw,
                                                self._layout_control_width if width is None else width,
                                                self._layout_control_height if height is None else height,
                                                False, pre_layout_callback=pre_layout)
        self._layout_groups.append(layout)

    def end_horizontal(self):
        if len(self._layout_groups) <= 1:
            raise ValueError(
                "Can't end base layout group! Did you call end_vertical()/end_horizontal()/end_...() too many times?")
        layout = self._layout_groups.pop()
        if layout.vertical:
            raise ValueError("Current layout group is not a horizontal group!")

    def begin_vertical(self, width: Optional[int] = None, height: Optional[int] = None,
                       pad: bool = False, squeeze: bool = False):
        layout = SSVGUILayoutContainer(self, True, True, squeeze, pad)

        def pre_layout(gui: "SSVGUI") -> tuple[int, int]:
            return self._layout_control_width if width is None else width, layout.min_height

        if len(self._layout_groups) > 0:
            self._layout_groups[-1].add_element(layout.draw,
                                                self._layout_control_width if width is None else width,
                                                self._layout_control_height if height is None else height,
                                                False, pre_layout_callback=pre_layout)
        self._layout_groups.append(layout)

    def end_vertical(self) -> SSVGUILayoutContainer:
        if len(self._layout_groups) <= 1:
            raise ValueError(
                "Can't end base layout group! Did you call end_vertical()/end_horizontal()/end_...() too many times?")
        layout = self._layout_groups.pop()
        if not layout.vertical:
            raise ValueError("Current layout group is not a vertical group!")
        return layout

    def begin_toggle(self, enabled: Union[bool, Reference[bool]], width: Optional[int] = None, height: Optional[int] = None,
                     pad: bool = False, squeeze: bool = False):
        layout = SSVGUILayoutContainer(self, True, enabled, squeeze, pad)

        def pre_layout(gui: "SSVGUI") -> tuple[int, int]:
            if isinstance(enabled, Reference):
                if not enabled.result:
                    min_height = 0
                else:
                    min_height = layout.min_height
                # min_height = layout.min_height
            elif not enabled:
                min_height = 0
            else:
                min_height = layout.min_height
            return self._layout_control_width if width is None else width, min_height

        if len(self._layout_groups) > 0:
            self._layout_groups[-1].add_element(layout.draw,
                                                self._layout_control_width if width is None else width,
                                                self._layout_control_height if height is None else height,
                                                False, pre_layout_callback=pre_layout)
        self._layout_groups.append(layout)

    def end_toggle(self):
        if len(self._layout_groups) <= 1:
            raise ValueError(
                "Can't end base layout group! Did you call end_vertical()/end_horizontal()/end_...() too many times?")
        layout = self._layout_groups.pop()
        if not layout.vertical:
            raise ValueError("Current layout group is not a toggle group!")

    def _get_rect_corners(self, bounds: Rect, local_rect: Optional[Rect]) -> tuple[float, float, float, float]:
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
        self._layout_groups[-1].add_element(lambda x, y: None,
                                            self._layout_control_width if width is None else width,
                                            self._layout_control_height/2 if height is None else height,
                                            expand=False)

    def rect(self, colour: Colour, rect: Optional[Rect] = None, overlay_last: bool = False):
        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.SOLID
            if colour.a != 1:
                render_mode = SSVGUIShaderMode.TRANSPARENT

            verts = gui._get_vertex_buffer(render_mode)
            col = colour.astuple
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            n_verts = [x0, y0, *col,
                       x1, y0, *col,
                       x0, y1, *col,

                       x0, y1, *col,
                       x1, y0, *col,
                       x1, y1, *col]
            verts.resize()
            verts = np.concatenate((verts, n_verts), dtype=np.float32)
            self._update_vertex_buffer(render_mode, verts)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None, overlay_last=overlay_last)

    def rounded_rect(self, colour: Colour, outline: bool = False, rect: Optional[Rect] = None,
                     overlay_last: bool = False):
        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.ROUNDING
            if outline:
                render_mode |= SSVGUIShaderMode.OUTLINE

            verts = gui._get_vertex_buffer(render_mode)
            col = colour.astuple
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour,
            # vec2 texcoord, vec2 size)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            n_verts = [x0, y0, *col, 0, 0, bounds.width, bounds.height,
                       x1, y0, *col, 1, 0, bounds.width, bounds.height,
                       x0, y1, *col, 0, 1, bounds.width, bounds.height,

                       x0, y1, *col, 0, 1, bounds.width, bounds.height,
                       x1, y0, *col, 1, 0, bounds.width, bounds.height,
                       x1, y1, *col, 1, 1, bounds.width, bounds.height]
            verts = np.concatenate((verts, n_verts), dtype=np.float32)
            self._update_vertex_buffer(render_mode, verts)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None, overlay_last=overlay_last)

    def label(self, text: str, colour: Colour = ssv_colour.ui_text, font_size: Optional[float] = None,
              x_offset: int = 0, rect: Optional[Rect] = None, overlay_last: bool = False,
              align: TextAlign = TextAlign.LEFT):
        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.TEXT

            if font_size is not None:
                scale = font_size / self._font.size
            else:
                scale = 1

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
                draw_x = (draw_x + max_x - fulltext_width) / 2
            elif align == TextAlign.RIGHT:
                fulltext_width = sum(
                    [self._font.chars.get(char, self._font.chars[' ']).x_advance for char in text]) * scale
                draw_x = max_x - fulltext_width

            verts = gui._get_vertex_buffer(render_mode)
            col = colour.astuple
            n_verts = []

            for char in text:
                char_def = self._font.chars.get(char, self._font.chars[' '])
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
                # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour, vec2 char)
                n_verts.extend([x0, y0, *col, bm_x0, bm_y0,
                                x1, y0, *col, bm_x1, bm_y0,
                                x0, y1, *col, bm_x0, bm_y1,

                                x0, y1, *col, bm_x0, bm_y1,
                                x1, y0, *col, bm_x1, bm_y0,
                                x1, y1, *col, bm_x1, bm_y1])
                draw_x += char_def.x_advance * scale
                if draw_x > max_x:
                    break
            verts = np.concatenate((verts, n_verts), dtype=np.float32)
            self._update_vertex_buffer(render_mode, verts)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None, overlay_last=overlay_last)

    def button(self, text: str, colour: Optional[Colour] = None, rect: Optional[Rect] = None) -> Reference[bool]:
        # We want the GUI to behave like an immediate mode GUI, but since layout is deferred until after all elements
        # have been created, the result of the button press can't be checked until well after this function has been
        # called as such we return a promise which is fulfilled after the on_gui() function has finished. This still
        # allows gui elements defined *after* this one to use the result since at draw time the button's result becomes
        # available. Since this is all single threaded, the future's result should never be waited for.
        res = Reference(False)

        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.ROUNDING

            verts = gui._get_vertex_buffer(render_mode)
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour,
            # vec2 texcoord, vec2 size)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            hover = (x0 <= gui.canvas.mouse_pos[0] <= x1) and (y0 <= gui._resolution[1] - gui.canvas.mouse_pos[1] <= y1)
            click = hover and gui.canvas.mouse_down[0]
            res.result = click
            if colour is None:
                if click:
                    col = ssv_colour.ui_element_bg_click.astuple
                elif hover:
                    col = ssv_colour.ui_element_bg_hover.astuple
                else:
                    col = ssv_colour.ui_element_bg.astuple
            else:
                col = colour
                if click:
                    col *= 0.8
                elif hover:
                    col *= 1.4
                col = col.astuple
            n_verts = [x0, y0, *col, 0, 0, bounds.width, bounds.height,
                       x1, y0, *col, 1, 0, bounds.width, bounds.height,
                       x0, y1, *col, 0, 1, bounds.width, bounds.height,

                       x0, y1, *col, 0, 1, bounds.width, bounds.height,
                       x1, y0, *col, 1, 0, bounds.width, bounds.height,
                       x1, y1, *col, 1, 1, bounds.width, bounds.height]
            verts = np.concatenate((verts, n_verts), dtype=np.float32)
            self._update_vertex_buffer(render_mode, verts)

        self._layout_groups[-1].add_element(draw, self._layout_control_width, self._layout_control_height,
                                            expand=False, layout=rect is None)
        self.label(text, ssv_colour.ui_text, rect=rect, font_size=14, overlay_last=True, align=TextAlign.CENTRE)
        # res.set_result(False)
        return res

    def slider(self, text: str, value: float, rect: Optional[Rect] = None) -> Reference[float]:
        ...

    def check_box(self, text: str, value: Union[bool, Reference[bool]], colour: Optional[Colour] = None,
                  rect: Optional[Rect] = None) -> Reference[bool]:
        res = value if isinstance(value, Reference) else Reference(value)

        def draw(gui: SSVGUI, bounds: Rect):
            render_mode = SSVGUIShaderMode.TRANSPARENT | SSVGUIShaderMode.ROUNDING

            verts = gui._get_vertex_buffer(render_mode)
            # Generate vertices for a quad. The vertex attributes to fill are (vec2 pos, vec4 colour,
            # vec2 texcoord, vec2 size)
            x0, x1, y0, y1 = gui._get_rect_corners(bounds, rect)
            hover = (x0 <= gui.canvas.mouse_pos[0] <= x1) and (y0 <= gui._resolution[1] - gui.canvas.mouse_pos[1] <= y1)
            click = hover and gui.canvas.mouse_down[0]
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
                col = colour
                if click or checked:
                    col *= 0.8
                elif hover:
                    col *= 1.4
                col = col.astuple
            n_verts = [x0, y0, *col, 0, 0, bounds.width, bounds.height,
                       x1, y0, *col, 1, 0, bounds.width, bounds.height,
                       x0, y1, *col, 0, 1, bounds.width, bounds.height,

                       x0, y1, *col, 0, 1, bounds.width, bounds.height,
                       x1, y0, *col, 1, 0, bounds.width, bounds.height,
                       x1, y1, *col, 1, 1, bounds.width, bounds.height]
            if checked:
                check_col = ssv_colour.ui_element_bg_hover.astuple
                # \
                n_verts.extend([x0, (y0 * .9 + y1 * .1), *check_col, 0, .1, bounds.width, bounds.height,
                                (x0 * .9 + x1 * .1), y0, *check_col, .1, 0, bounds.width, bounds.height,
                                (x0 * .1 + x1 * .9), y1, *check_col, .9, 0, bounds.width, bounds.height,

                                (x0 * .1 + x1 * .9), y1, *check_col, .9, 0, bounds.width, bounds.height,
                                (x0 * .9 + x1 * .1), y0, *check_col, .1, 0, bounds.width, bounds.height,
                                x1, (y0 * .1 + y1 * .9), *check_col, 1, .9, bounds.width, bounds.height])
                # /
                n_verts.extend([(x0 * .1 + x1 * .9), y0, *check_col, .9, 0, bounds.width, bounds.height,
                                x1, (y0 * .9 + y1 * .1), *check_col, 1, .1, bounds.width, bounds.height,
                                x0, (y0 * .1 + y1 * .9), *check_col, 0, .9, bounds.width, bounds.height,

                                x1, (y0 * .9 + y1 * .1), *check_col, 0, .9, bounds.width, bounds.height,
                                x0, (y0 * .1 + y1 * .9), *check_col, 1, .1, bounds.width, bounds.height,
                                (x0 * .9 + x1 * .1), y1, *check_col, .1, 1, bounds.width, bounds.height])
            verts = np.concatenate((verts, n_verts), dtype=np.float32)
            self._update_vertex_buffer(render_mode, verts)

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
