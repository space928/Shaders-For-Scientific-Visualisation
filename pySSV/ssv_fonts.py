#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import os.path
from importlib.resources import as_file, files
import xml.etree.ElementTree as et
from dataclasses import dataclass
from PIL import Image

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
        template_traversable = files("pySSV.fonts").joinpath(font_path)
        return template_traversable.read_text()
    except Exception as e:
        raise FileNotFoundError(f"Couldn't find/read the font: '{font_path}'. \n"
                                f"Inner exception: {e}")


def _load_bitmap(bitmap_path: str, font_path: str) -> Image:
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
        template_traversable = files("pySSV.fonts").joinpath(bitmap_path)
        f = template_traversable.open("rb")
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
            self.font_name = info.get("face")
            self.is_bold = info.get("bold") == "1"
            self.is_italic = info.get("italic") == "1"
            self.size = int(info.get("size"))
            self.line_height = int(common.get("lineHeight"))
            self.base_height = int(common.get("base"))
            self.width = int(common.get("scaleW"))
            self.height = int(common.get("scaleH"))
            self.pages = int(common.get("pages"))
            if self.pages != 1:
                raise ValueError(f"Font {self.font_name} has {self.pages} font pages, currently only 1 page is "
                                 f"supported.")

            distance_field = bm_font.find("distanceField")
            if distance_field is not None:
                self.sdf_distance = int(distance_field.get("distanceRange"))
            else:
                self.sdf_distance = None

            self.bitmap_path = bm_font.find("pages").find("page").get("file")
        except Exception as e:
            raise ValueError(f"Error while parsing font file '{font_path}'. \n"
                             f"Inner exception: {e}")
        self.bitmap = _load_bitmap(self.bitmap_path, font_path)
        self._parse_chars(bm_font.find("chars"))

    def _parse_chars(self, chars: et.Element):
        self.chars = {}
        for char in chars.iter("char"):
            char_id = int(char.get("id"))
            char = SSVCharacterDefinition(char_id,
                                          char.get("char", chr(char_id)),
                                          int(char.get("x")),
                                          int(char.get("y")),
                                          int(char.get("width")),
                                          int(char.get("height")),
                                          int(char.get("xoffset")),
                                          int(char.get("yoffset")),
                                          int(char.get("xadvance")))
            self.chars[char.char] = char


ssv_font_noto_sans_sb = SSVFont("NotoSans-SemiBold.fnt")
