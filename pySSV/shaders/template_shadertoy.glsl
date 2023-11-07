#pragma SSVTemplate define shadertoy
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
// Arguments get converted into compiler defines by the preprocessor
// an argument's name is transformed to match our naming convention:
//    entrypoint -> T_ENTRYPOINT
//    _varying_struct -> T_VARYING_STRUCT
#pragma SSVTemplate arg entrypoint
// Prefixing an argument name with an underscore is shorthand for --non_positional
// #pragma SSVTemplate arg _varying_struct --type str
// An example for an SDF shader
// #pragma SSVTemplate arg _render_mode --choices solid xray isolines 2d

#ifdef _GL_VERSION
#version _GL_VERSION
// For some compilers you need to specify the OpenGL version to target as the first line of the shader.
#endif // _GL_VERSION
#ifdef _GL_PRECISION
// In OpenGL ES you need to specify the precision of variables, you can do this per-variable or specify a default.
// https://stackoverflow.com/a/6336285
precision highp float;
#endif // _GL_PRECISION

#define SHADERTOY_COMPAT
// Include any default includes we think the user might want
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
    fragColor = mainImage(position * iResolution) + vec4(color, 1.0)*1e-6;
}
#endif //SHADER_STAGE_FRAGMENT