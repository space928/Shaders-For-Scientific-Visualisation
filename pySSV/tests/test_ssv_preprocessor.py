#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

import pytest

from ..ssv_shader_preprocessor import SSVShaderPreprocessor
from ..ssv_pragma_parser import SSVShaderPragmaParser, SSVTemplatePragmaParser
from .test_ssv_pragma_parser import test_shader, test_template


def test_ssv_argparse():
    template_info = SSVShaderPragmaParser().parse(test_shader, "test_shader.glsl")
    template_metadata = SSVTemplatePragmaParser().parse(test_template, "test_template.glsl")
    arg_parser = SSVShaderPreprocessor._make_argparse(template_metadata)
    parsed_args = arg_parser.parse_args(template_info.args)
    # print(parsed_args)
    assert "entrypoint" in parsed_args
    assert parsed_args.entrypoint == "frag"


def test_ssv_preprocessor():
    preproc = SSVShaderPreprocessor(gl_version="420")
    proc_shaders = preproc.preprocess(test_shader, "test_shader.glsl", additional_templates=[test_template])
    assert len(proc_shaders) == 2
    assert "vertex_shader" in proc_shaders
    assert "fragment_shader" in proc_shaders
    # print(proc_shaders["vertex_shader"])
    # print("################################")
    # print(proc_shaders["fragment_shader"])
    # This is not a great unit test, it's sensitive to stylistic changes in the output which don't impact functionality.
    assert proc_shaders["vertex_shader"] == """#version 420
#extension GL_ARB_shading_language_include : require
#line 3 "global_uniforms.glsl"
uniform float uTime;
uniform vec4 uResolution;
uniform vec2 uMouse;
#line 22 "test_shadertoy"
in vec2 in_vert;
in vec3 in_color;
out vec3 color;
out vec2 position;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    color = in_color;
    position = in_vert*0.5+0.5;
}
"""
    assert proc_shaders["fragment_shader"] == """#version 420
#extension GL_ARB_shading_language_include : require
#line 3 "global_uniforms.glsl"
uniform float uTime;
uniform vec4 uResolution;
uniform vec2 uMouse;
#line 35 "test_shadertoy"
out vec4 fragColor;
in vec3 color;
in vec2 position;
#line 3 "TEMPLATE_DATA"
// The entrypoint to the fragment shader
vec4 frag(vec2 fragPos)
{
    vec2 uv = fragPos.xy / uResolution.xy;

    return mix(uv.xyx, uv.yyx, sin(uTime)*0.5+0.5);
}
#line 41 "test_shadertoy"
void main() {

    fragColor = frag(position * uResolution) + vec4(color, 1.0)*1e-6;
}
"""

