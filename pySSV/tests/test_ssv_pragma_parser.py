#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

import pytest

from ..ssv_pragma_parser import SSVShaderPragmaParser, SSVTemplatePragmaParser

test_template = """
#pragma SSVTemplate define test_shadertoy
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
// Arguments get converted into compiler defines by the preprocessor
// an argument's name is transformed to match our naming convention:
//    entrypoint -> T_ENTRYPOINT
//    _varying_struct -> T_VARYING_STRUCT
#pragma SSVTemplate arg entrypoint --default mainImage -d "The name of the entrypoint function to the shader."
// Prefixing an argument name with an underscore is shorthand for --non_positional
// #pragma SSVTemplate arg _varying_struct --type str
// An example for an SDF shader
// #pragma SSVTemplate arg _render_mode --choices solid xray isolines 2d

#define SHADERTOY_COMPAT
// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef SHADER_STAGE_VERTEX
in vec2 in_vert;
in vec3 in_color;
out vec3 color;
out vec2 position;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    color = in_color;
    position = in_vert*0.5+0.5;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
in vec3 color;
in vec2 position;

#include "TEMPLATE_DATA"

void main() {
    // Not using the color attribute causes the compiler to strip it and confuses modernGL.
    fragColor = T_ENTRYPOINT(position * iResolution) + vec4(color, 1.0)*1e-6;
}
#endif //SHADER_STAGE_FRAGMENT
"""
test_shader = """
#pragma SSV test_shadertoy frag
// The entrypoint to the fragment shader
vec4 frag(vec2 fragPos)
{
    vec2 uv = fragPos.xy / iResolution.xy;

    return mix(uv.xyx, uv.yyx, sin(iTime)*0.5+0.5);
}
"""


def test_ssv_template_pragma_parser():
    template_parser = SSVTemplatePragmaParser()
    template_info = template_parser.parse(test_template, "test_template.glsl")

    # print(template_info)

    define = template_info["define"][0]
    stage1 = template_info["stage"][0]
    stage2 = template_info["stage"][1]
    arg = template_info["arg"][0]
    assert define.command == "define"
    assert define.name == "test_shadertoy"
    assert stage1.command == "stage"
    assert stage1.shader_stage == ["vertex"]
    assert stage2.command == "stage"
    assert stage2.shader_stage == ["fragment"]
    assert arg.command == "arg"
    assert arg.name == "entrypoint"
    assert arg.non_positional is False
    assert arg.action == "store"
    assert arg.default == "mainImage"
    assert arg.choices is None
    assert arg.const is None
    assert arg.description == "The name of the entrypoint function to the shader."


def test_ssv_shader_pragma_parser():
    shader_parser = SSVShaderPragmaParser()
    shader_info = shader_parser.parse(test_shader, "test_shader.glsl")
    assert shader_info.template == "test_shadertoy"
    assert shader_info.args == ["frag"]

