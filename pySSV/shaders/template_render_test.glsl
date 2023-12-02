//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define render_test --author "Thomas Mathieson" \
        --description "A simple full screen pixel shader to test the render system."
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
    gl_Position = vec4(in_vert, 0.0, 1.0);
    color = in_color;
    position = in_vert*0.5+0.5;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
in vec3 color;
in vec2 position;

vec4 mainImage(in vec2 fragCoord)
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = fragCoord/iResolution.yy;
    // Colour changing over time
    vec3 col = sin(uv.xyx + iTime * vec3(3, 4, 5)) * 0.5 + 0.5;
    float alpha = smoothstep(0.1, 0.1+2./iResolution.y, 1.-length(uv*2.-1.));
    // Output to screen
    return vec4(vec3(col), alpha);
}

void main() {
    // Not using the color attribute causes the compiler to strip it and confuses modernGL.
    fragColor = mainImage(position * iResolution.xy) + vec4(color, 1.0)*1e-6;
}
#endif //SHADER_STAGE_FRAGMENT
