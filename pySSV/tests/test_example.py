#!/usr/bin/env python
# coding: utf-8

#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

import pytest

from ..ssv_render_widget import SSVRenderWidget


def test_example_creation_blank():
    w = SSVRenderWidget()
    assert w.streaming_mode in {"png", "jpg", "h264"}
