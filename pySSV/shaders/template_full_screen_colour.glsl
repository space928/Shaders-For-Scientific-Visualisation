//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define full_screen_colour --author "Thomas Mathieson" \
        --description "A simple full screen pixel shader which fills the screen with a solid colour."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
#pragma SSVTemplate arg _colour -d "A glsl expression returning a vec4 representing the colour to output." --default "vec4(0., 1., 1., 1.)"

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"

#ifdef SHADER_STAGE_VERTEX
layout(location = 0) in vec2 in_vert;
layout(location = 1) in vec3 in_color;
layout(location = 0) out vec3 color;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    color = in_color;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
layout(location = 0) in vec3 color;

void main()
{
    fragColor = T_COLOUR;
    fragColor.rgb *= color;
}

#endif //SHADER_STAGE_FRAGMENT
