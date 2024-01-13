//  Copyright (c) 2024 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#pragma SSVTemplate define ui --author "Thomas Mathieson" --description "pySSV's built in GUI shader."
#pragma SSVTemplate stage vertex
#pragma SSVTemplate stage fragment
#pragma SSVTemplate arg _support_alpha -d "When this flag is passed, enable support alpha blending." --action store_true
#pragma SSVTemplate arg _support_text -d "When this flag is passed, enable support text rendering." --action store_true
#pragma SSVTemplate arg _support_texture -d "When this flag is passed, enable support texture rendering." --action store_true
#pragma SSVTemplate arg _support_rounding -d "When this flag is passed, enable support rounded edges. Requires texture coordinates!" --action store_true
#pragma SSVTemplate arg _support_shadow -d "When this flag is passed, enable support for shadows [NOT IMPLEMENTED YET]. Requires texture coordinates!" --action store_true
#pragma SSVTemplate arg _texture_name -d "The name of the uniform containing the texture." --default uTexture
#pragma SSVTemplate arg _rounding_radius -d "The radius of rounding to apply to rectangle." --default 3.

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef SHADER_STAGE_VERTEX
layout(location = 0) in vec2 in_vert;
layout(location = 1) in vec4 in_color;
layout(location = 0) out vec4 v_color;
#ifdef T_SUPPORT_TEXT
layout(location = 2) in vec2 in_char;
layout(location = 1) out vec2 v_char;
#endif // T_SUPPORT_TEXT
#if defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
layout(location = 3) in vec2 in_texcoord;
layout(location = 2) out vec2 v_texcoord;
#endif // defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
#ifdef T_SUPPORT_ROUNDING
layout(location = 4) in vec2 in_size;
layout(location = 3) out flat vec2 v_size;
#endif // T_SUPPORT_ROUNDING

void main() {
    gl_Position = vec4((in_vert/uResolution.xy)*2.-1., 0.0, 1.0);
    gl_Position.y = -gl_Position.y;
    v_color = in_color;
    #ifdef T_SUPPORT_TEXT
    v_char = in_char;
    #endif // T_SUPPORT_TEXT
    #if defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
    v_texcoord = in_texcoord;
    #endif // defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
    #ifdef T_SUPPORT_ROUNDING
    v_size = in_size;
    #endif // T_SUPPORT_ROUNDING
}
#endif // SHADER_STAGE_VERTEX


#ifdef SHADER_STAGE_FRAGMENT
out vec4 fragColor;
layout(location = 0) in vec4 v_color;
#ifdef T_SUPPORT_TEXT
layout(location = 1) in vec2 v_char;
#endif // T_SUPPORT_TEXT
#if defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
layout(location = 2) in vec2 v_texcoord;
#endif // defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
#ifdef T_SUPPORT_ROUNDING
layout(location = 3) in flat vec2 v_size;
#endif // T_SUPPORT_ROUNDING

#include "TEMPLATE_DATA"

#ifdef T_SUPPORT_TEXT
float median(vec3 x) {
    return max(min(x.r, x.g), min(max(x.r, x.g), x.b));
}
#endif // T_SUPPORT_TEXT

void main() {
    fragColor = v_color;

    #ifdef T_SUPPORT_TEXT
        // Multi-channel distance field text rendering derived from:
        // https://github.com/Chlumsky/msdfgen
        // See also: https://cdn.cloudflare.steamstatic.com/apps/valve/2007/SIGGRAPH2007_AlphaTestedMagnification.pdf
        float smoothing = abs(dFdy(v_char.y))*40.;
        float sdf = median(texture(uFontTex, v_char).rgb);
        fragColor.a *= smoothstep(0.5 - smoothing, 0.5 + smoothing, sdf);
    #endif // T_SUPPORT_TEXT

    #ifdef T_SUPPORT_TEXTURE
        fragColor *= texture(T_TEXTURE_NAME, v_texcoord);
    #endif // T_SUPPORT_TEXTURE

    #ifdef T_SUPPORT_ROUNDING
        float radius = T_ROUNDING_RADIUS;
        vec2 uv = v_texcoord * 2. - 1.;
        vec2 r = abs(uv*v_size.xy/4.) - v_size.xy/4. + radius;
        float mask = length(max(r, 0.)) + min(max(r.x, r.y), 0.0) - radius;
        fragColor.a *= smoothstep(0.5, -.25, mask);
    #endif // T_SUPPORT_ROUNDING

    #ifndef T_SUPPORT_ALPHA
        fragColor.a = 1.0;
    #endif // T_SUPPORT_ALPHA
}
#endif // SHADER_STAGE_FRAGMENT
