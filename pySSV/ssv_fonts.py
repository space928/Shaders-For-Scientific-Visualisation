#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import os.path
import sys
if sys.version_info >= (3, 9):
    from importlib.resources import files
else:
    from importlib.resources import open_binary, read_text
import xml.etree.ElementTree as et
from dataclasses import dataclass
from PIL import Image
from typing import Optional, Dict

from .ssv_logging import log


def _find_font(font_path: str) -> str:
    """
    Attempts to load a font file from the file system or from pySSV's built in fonts directory.

    :param font_path: the path to the font file.
    :return: the contents of the file as a string.
    """
    if os.path.isfile(font_path):
        with open(font_path, "r") as f:
            return f.read()

    try:
        if sys.version_info >= (3, 9):
            template_traversable = files("pySSV.fonts").joinpath(font_path)
            return template_traversable.read_text()
        else:
            return read_text("pySSV.fonts", font_path)
    except Exception as e:
        raise FileNotFoundError(f"Couldn't find/read the font: '{font_path}'. \n"
                                f"Inner exception: {e}")


def _load_bitmap(bitmap_path: str, font_path: str) -> Image.Image:
    """
    Attempts to load a font bitmap from the file system or from pySSV's built in fonts directory.

    :param bitmap_path: the path to the font bitmap.
    :param font_path: the path to the font file.
    :return: the contents of the font bitmap as an Image.
    """
    if os.path.isfile(bitmap_path):
        return Image.open(bitmap_path)

    font_dir = os.path.dirname(font_path)
    if os.path.isdir(font_dir):
        path = os.path.join(font_dir, font_path)
        if os.path.isfile(path):
            return Image.open(path)

    try:
        if sys.version_info >= (3, 9):
            template_traversable = files("pySSV.fonts").joinpath(bitmap_path)
            f = template_traversable.open("rb")
        else:
            f = open_binary("pySSV.fonts", bitmap_path)
        return Image.open(f)
    except Exception as e:
        raise FileNotFoundError(f"Couldn't find/read the font bitmap: '{bitmap_path}'. \n"
                                f"Inner exception: {e}")


@dataclass
class SSVCharacterDefinition:
    id: int
    """The id of the character. (Usually the ascii character code)"""
    char: str
    """The character being represented."""
    x: int
    """The x coordinate of the character in the bitmap from the left in pixels."""
    y: int
    """The y coordinate of the character in the bitmap from the top in pixels."""
    width: int
    """The width of the character in the bitmap in pixels."""
    height: int
    """The height of the character in the bitmap in pixels."""
    x_offset: int
    """How much to offset the character by in the x axis when rendering in pixels."""
    y_offset: int
    """How much to offset the character by in the y axis when rendering in pixels."""
    x_advance: int
    """How far to advance before drawing the next character."""


class SSVFont:
    def __init__(self, font_path: str):
        """
        Constructs a new SSVFont instance from an existing ``.fnt`` file.

        A ``.fnt`` file is a Bitmap Font file which is an xml file following the schema defined here:
        https://www.angelcode.com/products/bmfont/doc/file_format.html

        Font files can be generated using:
        https://github.com/soimy/msdf-bmfont-xml

        :param font_path: the path to the font file to load.
        """
        bm_font = et.fromstring(_find_font(font_path))
        try:
            info = bm_font.find("info")
            common = bm_font.find("common")
            self.font_name: str = info.get("face")  # type: ignore
            self.is_bold: bool = info.get("bold") == "1"  # type: ignore
            self.is_italic: bool = info.get("italic") == "1"  # type: ignore
            self.size: int = int(info.get("size"))  # type: ignore
            self.line_height: int = int(common.get("lineHeight"))  # type: ignore
            self.base_height: int = int(common.get("base"))  # type: ignore
            self.width: int = int(common.get("scaleW"))  # type: ignore
            self.height: int = int(common.get("scaleH"))  # type: ignore
            self.pages: int = int(common.get("pages"))  # type: ignore
            if self.pages != 1:
                raise ValueError(f"Font {self.font_name} has {self.pages} font pages, currently only 1 page is "
                                 f"supported.")

            distance_field = bm_font.find("distanceField")
            self.sdf_distance: Optional[int] = None
            if distance_field is not None:
                self.sdf_distance = int(distance_field.get("distanceRange"))  # type: ignore

            self.bitmap_path: str = bm_font.find("pages").find("page").get("file")  # type: ignore
            if self.bitmap_path is None:
                raise ValueError("Font bitmap path is not defined.")
        except Exception as e:
            raise ValueError(f"Error while parsing font file '{font_path}'. \n"
                             f"Inner exception: {e}")
        self.bitmap = _load_bitmap(self.bitmap_path, font_path)
        self.chars: Dict[str, SSVCharacterDefinition] = {}
        chars_el = bm_font.find("chars")
        if chars_el is not None:
            self._parse_chars(chars_el)

    def _parse_chars(self, chars: et.Element):
        for char in chars.iter("char"):
            char_id_str = char.get("id")
            if char_id_str is None:
                continue
            char_id = int(char_id_str)
            char_def = SSVCharacterDefinition(char_id,
                                              char.get("char", chr(char_id)),  # type: ignore
                                              int(char.get("x")),  # type: ignore
                                              int(char.get("y")),  # type: ignore
                                              int(char.get("width")),  # type: ignore
                                              int(char.get("height")),  # type: ignore
                                              int(char.get("xoffset")),  # type: ignore
                                              int(char.get("yoffset")),  # type: ignore
                                              int(char.get("xadvance")))  # type: ignore
            self.chars[char_def.char] = char_def


ssv_font_noto_sans_sb = SSVFont("NotoSans-SemiBold.fnt")
