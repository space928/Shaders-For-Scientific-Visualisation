#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from typing import Tuple


class Colour:
    """
    Represents an RGBA colour.
    """
    r: float
    g: float
    b: float
    a: float

    def __init__(self, r: float = 0, g: float = 0, b: float = 0, a: float = 1):
        """
        Creates a new colour object

        :param r: red (0-1)
        :param g: green (0-1)
        :param b: blue (0-1)
        :param a: alpha (0-1)
        """
        self.r = r
        self.g = g
        self.b = b
        self.a = a

    def __mul__(self, other):
        if isinstance(other, Colour):
            return Colour(self.r*other.r, self.g*other.g, self.b*other.b, self.a*other.a)
        elif isinstance(other, float) or isinstance(other, int):
            return Colour(self.r * other, self.g * other, self.b * other, self.a * other)
        elif isinstance(other, tuple) and len(other) >= 4:
            return Colour(self.r * other[0], self.g * other[1], self.b * other[2], self.a * other[3])
        else:
            raise TypeError(f"Can't multiply Colour by {type(other)}!")

    def __add__(self, other):
        if isinstance(other, Colour):
            return Colour(self.r+other.r, self.g+other.g, self.b+other.b, self.a+other.a)
        elif isinstance(other, float) or isinstance(other, int):
            return Colour(self.r + other, self.g + other, self.b + other, self.a + other)
        elif isinstance(other, tuple) and len(other) >= 4:
            return Colour(self.r + other[0], self.g + other[1], self.b + other[2], self.a + other[3])
        else:
            raise TypeError(f"Can't add Colour to {type(other)}!")

    @property
    def astuple(self) -> Tuple[float, float, float, float]:
        """Gets the (r, g, b, a) tuple of this colour."""
        return self.r, self.g, self.b, self.a

    @staticmethod
    def from_hex(hex_colour: str) -> "Colour":
        if len(hex_colour) >= 4 and hex_colour[0] == "#":
            hex_colour = hex_colour[1:]
        if len(hex_colour) == 3:
            return Colour(int(hex_colour[0], 16) / 15, int(hex_colour[1], 16) / 15, int(hex_colour[2], 16) / 15)
        elif len(hex_colour) == 4:
            return Colour(int(hex_colour[0], 16) / 15, int(hex_colour[1], 16) / 15, int(hex_colour[2], 16) / 15,
                          int(hex_colour[3], 16) / 15)
        elif len(hex_colour) == 6:
            return Colour(int(hex_colour[0:1], 16) / 255, int(hex_colour[2:3], 16) / 255,
                          int(hex_colour[3:4], 16) / 255)
        elif len(hex_colour) == 8:
            return Colour(int(hex_colour[0:1], 16) / 255, int(hex_colour[2:3], 16) / 255,
                          int(hex_colour[3:4], 16) / 255, int(hex_colour[5:6], 16) / 255)
        else:
            raise ValueError(f"'{hex_colour}' is not a valid hex colour!")

    @staticmethod
    def from_int(r: int, g: int, b: int, a: int = 255) -> "Colour":
        return Colour(r / 255, g / 255, b / 255, a / 255)


####################
# Built in colours #
####################

white = Colour(1, 1, 1)
black = Colour(0, 0, 0)
red = Colour(1, 0, 0)
green = Colour(0, 1, 0)
blue = Colour(0, 0, 1)
cyan = Colour(0, 1, 1)
magenta = Colour(1, 0, 1)
yellow = Colour(1, 1, 0)

lightgrey = Colour(.75, .75, .75)
lightgray = Colour(.75, .75, .75)
grey = Colour(.5, .5, .5)
gray = Colour(.5, .5, .5)
darkgrey = Colour(.25, .25, .25)
darkgray = Colour(.25, .25, .25)
maroon = Colour(.5, 0, 0)
olive = Colour(.5, .5, 0)
darkgreen = Colour(0, .5, 0)
teal = Colour(0, .5, .5)
navy = Colour(0, 0, .5)
darkmagenta = Colour(.5, 0, .5)

orange = Colour(1, .5, 0)
emeraldgreen = Colour(0, 1, .5)
skyblue = Colour(0, .5, 1)
violet = Colour(.5, 0, 1)
deeppink = Colour(1, 0, .5)
limegreen = Colour(0.5, 1, 0)

ui_base_bg = Colour(0.2, 0.2, 0.2, 0.5)
ui_element_bg = Colour(0.35, 0.35, 0.35)
ui_element_bg_hover = Colour(0.45, 0.45, 0.45)
ui_element_bg_click = Colour(0.25, 0.25, 0.25)
ui_element_border = Colour(0.15, 0.15, 0.15)
ui_text = Colour(0.95, 0.95, 0.95)
