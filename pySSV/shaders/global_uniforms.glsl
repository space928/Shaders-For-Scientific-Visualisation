//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
uniform float uTime;
uniform vec4 uResolution;
uniform vec2 uMouse;

#ifdef SHADERTOY_COMPAT
#define iTime uTime
#define iResolution uResolution
#define iMouse uMouse
#endif

#ifdef _DYNAMIC_UNIFORMS
_DYNAMIC_UNIFORMS;
#endif
