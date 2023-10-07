#!/usr/bin/env python
# coding: utf-8

#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

import pytest

from ..example import ExampleWidget


def test_example_creation_blank():
    w = ExampleWidget()
    assert w.value == 'Hello World'
