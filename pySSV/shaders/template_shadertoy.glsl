//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define shadertoy --author "Thomas Mathieson" \
        --description "A simple full screen pixel shader with compatibility for Shadertoy shaders."
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
    fragColor = T_ENTRYPOINT(position * iResolution.xy) + vec4(color, 1.0)*1e-6;
}
#endif //SHADER_STAGE_FRAGMENT
