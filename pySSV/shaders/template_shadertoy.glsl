//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define shadertoy --author "Thomas Mathieson" \
        --description "A simple full screen pixel shader with compatibility for Shadertoy shaders."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment

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
    gl_Position = vec4(in_vert, 0.999, 1.0);
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
    fragColor = vec4(0.);
    mainImage(fragColor, position * iResolution.xy);
    fragColor.a += color.r*1e-6;
}
#endif //SHADER_STAGE_FRAGMENT
