//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define sdf --author "Thomas Mathieson" \
        --description "A shader template which allows you to render custom signed distance functions."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
#pragma SSVTemplate arg entrypoint -d "The name of the sdf function in the shader."
#pragma SSVTemplate arg _camera_distance --default 10.0 -d "The distance of the camera from the centre of the distance field."
#pragma SSVTemplate arg _rotate_speed --default 0.1 -d "The orbit speed of the camera around the SDF, in radians/second."
#pragma SSVTemplate arg _raymarch_steps --default 128 \
        -d "The number of raymarching steps to use when rendering, turn this up if the edges of surfaces look soft."
#pragma SSVTemplate arg _raymarch_distance --default 32. -d "The maximum distance to raymarch."
#pragma SSVTemplate arg _light_dir --default "normalize(vec3(0.5, 0.5, -0.9))" -d "The maximum distance to raymarch."
#pragma SSVTemplate arg _render_mode --choices SOLID DEPTH XRAY ISOLINES --default SOLID \
        -d "How the distance field should be rendered. Check the documentation for more information about each mode."

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"

#define EPSILON 0.01
#define saturate(x) clamp(x, 0., 1.)


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

float map(vec3 p) {
    return T_ENTRYPOINT(p);
}

// Raymarching loop
float trace(vec3 o, vec3 r) {
    float t = 0.0;

    for( int i=0;i<T_RAYMARCH_STEPS;i++ ) {
        vec3 p = o + r * t;

        float d = map(p);

        if(t > T_RAYMARCH_DISTANCE) {
            t = -1.0;
            break;
        }

        t += d;
    }
    return t;
}

// Estimate the normal of the sdf by finite differences
vec3 estimateNormal(vec3 p) {
    vec2 eps = vec2(EPSILON, 0.);
    return normalize(vec3(
        map(p + eps.xyy) - map(p - eps.xyy),
        map(p + eps.yxy) - map(p - eps.yxy),
        map(p + eps.yyx) - map(p - eps.yyx)
    ));
}

mat3 rotY(float x)
{
    float sx = sin(x);
    float cx = cos(x);
    return mat3(cx, 0., sx,
                0., 1., 0.,
                -sx, 0., cx);
}

// From: https://www.shadertoy.com/view/lslGzl
vec3 filmicToneMapping(vec3 col)
{
	col = max(vec3(0.), col - vec3(0.002));
	col = (col * (6.2 * col + .5)) / (col * (6.2 * col + 1.7) + 0.06);
	return col;
}

// Fragpos, surface normal, ray direction, ray depth
vec3 shadeGBuff(vec3 p, vec3 n, vec3 d, float t, vec2 uv)
{
    vec3 col = mix(vec3(0.7, 0.8, 1.), vec3(0.3, 0.4, 1.), abs(saturate(d.y*2.)));
    if(t != -1. && t < T_RAYMARCH_DISTANCE)
    {
        float fog = 1.0 / (1.0 + t * t * 0.05);
        fog = smoothstep(0., 0.9, fog);

        vec3 ambient = vec3(0.1,0.1,0.15)*0.5;
        vec3 albedo = vec3(0.5);
        float ndotl = dot(T_LIGHT_DIR, n);
        float ndoth = saturate(dot(normalize(T_LIGHT_DIR + -d), n));
        vec3 light = saturate(ndotl) * albedo;
        vec3 soft_diffuse = (1.-pow(1.-saturate(ndotl * 0.4 + 0.6), 1.5)) * albedo;
        float spec = (pow(ndoth, 10.))*saturate(ndotl);
        light += saturate(spec);
        light += soft_diffuse*0.15;

        col = mix(col, ambient + light, fog);
    }

    return filmicToneMapping(col*0.5)*1.25;
}

void main() {
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = position;
    uv = uv * 2.0 - 1.0;
    // Fix any aspect ratio distortion
    uv.x *= uResolution.x / uResolution.y;

    vec3 r = normalize(vec3(uv, 2.0))*rotY(uTime*T_ROTATE_SPEED);
    vec3 o = vec3(0., 0., -T_CAMERA_DISTANCE)*rotY(uTime*T_ROTATE_SPEED);
    float t = trace(o, r);
    vec3 p = o + r * t;
    vec3 nrm = estimateNormal(p);

    vec3 col = shadeGBuff(p, nrm, r, t, uv);

    // Not using the color attribute causes the compiler to strip it and confuses modernGL.
    fragColor = vec4(col, 1.) + vec4(color, 1.0)*1e-10;
}
#endif //SHADER_STAGE_FRAGMENT
