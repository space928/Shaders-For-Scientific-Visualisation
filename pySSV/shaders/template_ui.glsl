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
#pragma SSVTemplate arg _support_outline -d "When this flag is passed, enable support for outlines. Requires rounding!" --action store_true
#pragma SSVTemplate arg _texture_name -d "The name of the uniform containing the texture." --default uTexture

// Include any default includes we think the user might want
#include "compat.glsl"
#include "global_uniforms.glsl"


#ifdef SHADER_STAGE_VERTEX
layout(location = 0) in vec2 in_vert;
layout(location = 1) in vec4 in_color;
layout(location = 0) out vec4 v_color;
#ifdef T_SUPPORT_TEXT
// The uv coordinates into the font texture are stored in xy, and z stores the font weight.
layout(location = 2) in vec3 in_char;
layout(location = 1) out vec3 v_char;
#endif // T_SUPPORT_TEXT
#if defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
layout(location = 3) in vec2 in_texcoord;
layout(location = 2) out vec2 v_texcoord;
#endif // defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
#ifdef T_SUPPORT_ROUNDING
// To get the correct aspect ratio, in_size.xy stores the size of the rect to be rounded in pixels
// in_size.z stores the rounding radius in pixels
layout(location = 4) in vec3 in_size;
layout(location = 3) out flat vec3 v_size;
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
layout(location = 1) in vec3 v_char;
#endif // T_SUPPORT_TEXT
#if defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
layout(location = 2) in vec2 v_texcoord;
#endif // defined(T_SUPPORT_TEXTURE) || defined(T_SUPPORT_ROUNDING)
#ifdef T_SUPPORT_ROUNDING
layout(location = 3) in flat vec3 v_size;
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
        float sdf = median(texture(uFontTex, v_char.xy).rgb);
        fragColor.a *= smoothstep(max(v_char.z - smoothing, 0.05), min(v_char.z + smoothing, 0.95), sdf);
        #ifdef T_SUPPORT_SHADOW
            float shadow_sdf = median(texture(uFontTex, v_char.xy-0.01).rgb);
            float shadow = smoothstep(max(v_char.z - smoothing, 0.05), min(v_char.z + smoothing, 0.95), shadow_sdf);
            float shadow_exp = smoothstep(max(v_char.z-.2 - smoothing, 0.05), min(v_char.z-.1 + smoothing, 0.95), shadow_sdf);
            float shadow_alpha = max(shadow_exp-fragColor.a, 0.);
            fragColor.rgb = (fragColor.rgb*0.2)*shadow_alpha + fragColor.rgb*(1.-shadow_alpha);
            fragColor.a = min(fragColor.a+shadow, 1.);
        #endif // T_SUPPORT_SHADOW
    #endif // T_SUPPORT_TEXT

    #ifdef T_SUPPORT_TEXTURE
        fragColor *= texture(T_TEXTURE_NAME, v_texcoord);
    #endif // T_SUPPORT_TEXTURE

    #ifdef T_SUPPORT_ROUNDING
        float radius = v_size.z;
        radius = min(radius, min(v_size.x, v_size.y)/4.);
        vec2 uv = v_texcoord * 2. - 1.;
        vec2 r = abs(uv*v_size.xy/4.) - v_size.xy/4. + radius;
        float mask = length(max(r, 0.)) + min(max(r.x, r.y), 0.0) - radius;
        fragColor.a *= smoothstep(0.5, -.25, mask);
        #ifdef T_SUPPORT_OUTLINE
        fragColor.rgb *= smoothstep(0.4, 1., abs(mask))*.5+.5;
        #endif // T_SUPPORT_OUTLINE
    #endif // T_SUPPORT_ROUNDING

    #ifndef T_SUPPORT_ALPHA
        fragColor.a = 1.0;
    #endif // T_SUPPORT_ALPHA
}
#endif // SHADER_STAGE_FRAGMENT
