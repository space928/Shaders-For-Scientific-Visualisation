//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define pixel --author "Thomas Mathieson" --description "A simple full screen pixel shader."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
#pragma SSVTemplate arg entrypoint_vert -d "The name of the entrypoint function to the vertex shader."
#pragma SSVTemplate arg entrypoint_pixel -d "The name of the entrypoint function to the pixel shader."

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"

#ifdef SHADER_STAGE_VERTEX
layout(location = 0) in vec2 in_vert;
layout(location = 1) in vec3 in_color;
layout(location = 0) out vec3 color;
layout(location = 1) out vec3 position;

#include "TEMPLATE_DATA"

void main() {
    gl_Position = vec4(in_vert, 0.999, 1.0);
    color = in_color;

    T_ENTRYPOINT_VERT();
    position = gl_Position.xyz;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
layout(location = 0) in vec3 color;
layout(location = 1) in vec3 position;

#include "TEMPLATE_DATA"

void main() {
    fragColor = T_ENTRYPOINT_PIXEL(position);
    // Despite the explicit layout, sometimes in_color still gets stripped...
    fragColor.a += color.r*1e-20;
}
#endif //SHADER_STAGE_FRAGMENT
