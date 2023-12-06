//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define point_cloud --author "Thomas Mathieson" --description "Renders vertices as a point cloud."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage geometry
#pragma SSVTemplate stage fragment
#pragma SSVTemplate input_primitive POINTS
#pragma SSVTemplate arg entrypoint -d "The name of the entrypoint function to the shader." --default default_vert

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef SHADER_STAGE_VERTEX
in vec3 in_vert;
in vec3 in_color;
out vec4 color;

struct VertexOutput {
    vec4 position;
    float size;
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
    o.size = 10.0/uResolution.x;
    return o;
}

void main() {
    VertexOutput vOut = T_ENTRYPOINT();
    gl_Position = vOut.position;
    color = vOut.color;
    gl_PointSize = vOut.size;
}
#endif //SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_GEOMETRY
layout(points) in;
layout(triangle_strip, max_vertices=4) out;

in vec4 color[];
out vec4 out_color;

void main() {
    vec4 position = gl_in[0].gl_Position;
    float size = gl_in[0].gl_PointSize;
    out_color = color[0];
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
#endif //SHADER_STAGE_GEOMETRY


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
in vec4 out_color;

void main() {
    fragColor = out_color+vec4(0.5);
}
#endif //SHADER_STAGE_FRAGMENT
