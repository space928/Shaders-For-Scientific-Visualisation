//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define pixel --author "Thomas Mathieson" --description "A simple full screen pixel shader."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
#pragma SSVTemplate arg entrypoint -d "The name of the entrypoint function to the shader."

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef SHADER_STAGE_VERTEX
layout(location = 0) in vec2 in_vert;
layout(location = 1) in vec3 in_color;
layout(location = 0) out vec3 color;
layout(location = 1) out vec2 position;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    color = in_color;
    position = in_vert*0.5+0.5;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
layout(location = 0) in vec3 color;
layout(location = 1) in vec2 position;

#include "TEMPLATE_DATA"

void main() {
    fragColor = T_ENTRYPOINT(position * uResolution.xy);
}
#endif //SHADER_STAGE_FRAGMENT
