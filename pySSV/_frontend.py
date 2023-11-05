#!/usr/bin/env python
# coding: utf-8

#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.


"""
Information about the frontend package of the widgets.
"""

try:
    from ._version import __version__
except ImportError:
    __version__ = "dev"

module_name = "py-ssv"
module_version = f"^{__version__}"
