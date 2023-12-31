//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define vert --author "Thomas Mathieson" \
        --description "A minimal shader template to render vertices with their vertex colours."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
#pragma SSVTemplate arg entrypoint -d "The name of the entrypoint function to the shader."

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef SHADER_STAGE_VERTEX
in vec2 in_vert;
in vec3 in_color;
out vec4 v_color;

struct VertexOutput {
    vec4 position;
    vec4 color;
};

#include "TEMPLATE_DATA"

void main() {
    VertexOutput vOut = T_ENTRYPOINT();
    gl_Position = vOut.position;
    v_color = vOut.color;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
in vec4 v_color;

void main() {
    // Not using the color attribute causes the compiler to strip it and confuses modernGL.
    fragColor = vec4(v_color);
}
#endif //SHADER_STAGE_FRAGMENT
