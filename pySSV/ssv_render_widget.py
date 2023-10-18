#!/usr/bin/env python
# coding: utf-8

#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

from ipywidgets import DOMWidget
from traitlets import Unicode, Enum, Int
from ._frontend import module_name, module_version


class SSVRenderWidget(DOMWidget):
    """TODO: Add docstring here
    """
    _model_name = Unicode('SSVRenderModel').tag(sync=True)
    _model_module = Unicode(module_name).tag(sync=True)
    _model_module_version = Unicode(module_version).tag(sync=True)
    _view_name = Unicode('SSVRenderView').tag(sync=True)
    _view_module = Unicode(module_name).tag(sync=True)
    _view_module_version = Unicode(module_version).tag(sync=True)

    streaming_mode = Enum(("png", "jpg", "h264"), "png").tag(sync=True)
    stream_data = Unicode("test").tag(sync=True)
    mouse_pos_x = Int(0).tag(sync=True)
    mouse_pos_y = Int(0).tag(sync=True)
