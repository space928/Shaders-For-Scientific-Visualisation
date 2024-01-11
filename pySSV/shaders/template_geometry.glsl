//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define point_cloud --author "Thomas Mathieson" --description "Allows the use of a geometry shader to generate triangles from vertices (treated as points)."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage geometry
#pragma SSVTemplate stage fragment
#pragma SSVTemplate input_primitive POINTS
#pragma SSVTemplate arg entrypoint_vert -d "The name of the entrypoint function to vertex the shader." --default default_vert
#pragma SSVTemplate arg entrypoint_geo -d "The name of the entrypoint function to geometry the shader." --default default_geo
//#pragma SSVTemplate arg _vertex_input_struct -d "The name of the struct containing data to be input to the vertex stage of the shader." --default DefaultVertexInput
#pragma SSVTemplate arg _vertex_output_struct -d "The name of the struct containing data to be transferred from the vertex stage to the geometry stage." --default DefaultVertexOutput
#pragma SSVTemplate arg _geo_max_vertices -d "The maximum number of vertices which can be output be the geometry stage per input vertex. Must be a constant." --default 4
#pragma SSVTemplate arg _custom_vertex_input -d "When this flag is passed, the default vertex input attributes are not created and must be declared by the user." --action store_true

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef T_VERTEX_OUTPUT_STRUCT_ISDEFAULT
struct DefaultVertexOutput {
    vec4 position;
    vec4 color;
    float size;
};
#endif // T_VERTEX_OUTPUT_STRUCT_ISDEFAULT

#ifdef SHADER_STAGE_VERTEX
#ifndef T_CUSTOM_VERTEX_INPUT
// By using an explicit layout binding, we prevent the compiler from stripping the input attributes.
layout(location = 0) in vec4 in_vert;
layout(location = 1) in vec4 in_color;
#endif // T_CUSTOM_VERTEX_INPUT
#endif // SHADER_STAGE_VERTEX

#ifdef SHADER_STAGE_GEOMETRY
layout(location = 0) out vec4 out_color;
#endif // SHADER_STAGE_GEOMETRY

#include "TEMPLATE_DATA"

#ifdef SHADER_STAGE_VERTEX
layout(location = 0) out T_VERTEX_OUTPUT_STRUCT v_out;

#ifndef T_CUSTOM_VERTEX_INPUT
T_VERTEX_OUTPUT_STRUCT default_vert() {
    T_VERTEX_OUTPUT_STRUCT o;
    vec4 pos = vec4(in_vert, 1.0);
    pos = uViewMat * pos;
    pos = uProjMat * pos;
    o.position = pos;
    o.color = vec4(in_color, 1.);
    o.size = 10.0/uResolution.x;
    return o;
}
#else
#ifdef T_ENTRYPOINT_VERT_ISDEFAULT
#error Using custom vertex input attributes with the default vertex shader is not supported. Make sure to define 'entrypoint_vert' in your shader!
#endif // T_ENTRYPOINT_VERT_ISDEFAULT
T_VERTEX_OUTPUT_STRUCT default_vert() {
    T_VERTEX_OUTPUT_STRUCT o;
    return o;
}
#endif // T_CUSTOM_VERTEX_INPUT

void main() {
    v_out = T_ENTRYPOINT_VERT();
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_GEOMETRY
layout(points) in;
layout(triangle_strip, max_vertices=T_GEO_MAX_VERTICES) out;

layout(location = 0) in T_VERTEX_OUTPUT_STRUCT v_out[];

#ifdef T_ENTRYPOINT_VERT_ISDEFAULT
void default_geo(T_VERTEX_OUTPUT_STRUCT i) {
    vec4 position = i.position;
    float size = i.size;
    out_color = i.color;
    vec4 aspect_ratio = vec4(1., uResolution.x/uResolution.y, 1., 1.);
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
#endif //T_ENTRYPOINT_VERT_ISDEFAULT

void main() {
    out_color = vec4(1., 0.5, 1., 1.);
    T_ENTRYPOINT_GEO(v_out[0]);
}
#endif //SHADER_STAGE_GEOMETRY


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
layout(location = 0) in vec4 out_color;

void main() {
    fragColor = out_color;
}
#endif //SHADER_STAGE_FRAGMENT
