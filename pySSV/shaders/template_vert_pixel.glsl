//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define vert_pixel --author "Thomas Mathieson" --description "A simple vertex/pixel shader."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
#pragma SSVTemplate arg entrypoint_vert -d "The name of the entrypoint function to the vertex shader."
#pragma SSVTemplate arg entrypoint_pixel -d "The name of the entrypoint function to the pixel shader."

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"

#ifdef SHADER_STAGE_VERTEX
layout(location = 0) out vec3 position;

#include "TEMPLATE_DATA"

void main() {
    gl_Position = vec4(1.0);
    T_ENTRYPOINT_VERT();
    position = gl_Position.xyz;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
layout(location = 0) in vec3 position;

#include "TEMPLATE_DATA"

void main() {
    fragColor = T_ENTRYPOINT_PIXEL(position);
}
#endif //SHADER_STAGE_FRAGMENT
