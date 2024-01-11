//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define point_cloud --author "Thomas Mathieson" --description "Renders vertices as a point cloud."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage geometry
#pragma SSVTemplate stage fragment
#pragma SSVTemplate input_primitive POINTS
#pragma SSVTemplate arg entrypoint -d "The name of the entrypoint function to the shader." --default default_vert
#pragma SSVTemplate arg _non_square_points -d "When specified 'size' parameter of VertexOutput struct takes a vec2." --action store_true

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef SHADER_STAGE_VERTEX
// These are specified with an explicit layout specifier to prevent compiler stripping
layout(location = 0) in vec3 in_vert;
layout(location = 1) in vec3 in_color;
layout(location = 0) out vec4 _color;
#ifdef T_NON_SQUARE_POINTS
layout(location = 1) out vec2 _size;
#endif

struct VertexOutput {
    vec4 position;
    #ifdef T_NON_SQUARE_POINTS
    vec2 size;
    #else
    float size;
    #endif
    vec4 color;
};

#include "TEMPLATE_DATA"

VertexOutput default_vert() {
    VertexOutput o;
    vec4 pos = vec4(in_vert, 1.0);
    pos = uViewMat * pos;
    pos = uProjMat * pos;
    o.position = pos;
    o.color = vec4(in_color, 1.);
    #ifdef T_NON_SQUARE_POINTS
    o.size = vec2(10.0/uResolution.x);
    #else
    o.size = 10.0/uResolution.x;
    #endif
    return o;
}

void main() {
    VertexOutput vOut = T_ENTRYPOINT();
    gl_Position = vOut.position;
    _color = vOut.color;
    #ifdef T_NON_SQUARE_POINTS
    _size = vOut.size;
    #else
    gl_PointSize = vOut.size;
    #endif
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_GEOMETRY
layout(points) in;
layout(triangle_strip, max_vertices=4) out;

layout(location = 0) in vec4 _color[];
#ifdef T_NON_SQUARE_POINTS
layout(location = 1) in vec2 _size[];
#endif
layout(location = 0) out vec4 out_color;

void main() {
    vec4 position = gl_in[0].gl_Position;
    #ifdef T_NON_SQUARE_POINTS
    if(_size[0] == vec2(0.)) {
        EndPrimitive();
        return;
    }
    vec4 size = vec4(_size[0], 1., 1.);
    vec4 aspect_ratio = vec4(1.);
    #else
    if(gl_in[0].gl_PointSize == 0.) {
        EndPrimitive();
        return;
    }
    float size = gl_in[0].gl_PointSize;
    vec4 aspect_ratio = vec4(1., uResolution.x/uResolution.y, 1., 1.);
    #endif
    out_color = _color[0];
    gl_Position = position + size * vec4(-1., -1., 0.0, 0.0) * aspect_ratio;
    EmitVertex();
    gl_Position = position + size * vec4(1., -1., 0.0, 0.0) * aspect_ratio;
    EmitVertex();
    gl_Position = position + size * vec4(-1., 1., 0.0, 0.0) * aspect_ratio;
    EmitVertex();
    gl_Position = position + size * vec4(1., 1., 0.0, 0.0) * aspect_ratio;
    EmitVertex();
    EndPrimitive();
}
#endif //SHADER_STAGE_GEOMETRY


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
layout(location = 0) in vec4 out_color;

void main() {
    fragColor = out_color;
}
#endif //SHADER_STAGE_FRAGMENT
