//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#ifdef SPHINX_DOCS
// Compatibility hack for the documentation compiler which doesn't know that 'uniform' is a keyword...
#define uniform
#endif // SPHINX_DOCS
uniform float uTime;
uniform int uFrame;
uniform vec4 uResolution;
uniform vec2 uMouse;
uniform bool uMouseDown;
uniform mat4x4 uViewMat;
uniform mat4x4 uProjMat;
uniform vec3 uViewDir;

#ifdef SHADERTOY_COMPAT
#define iTime uTime
#define iFrame uFrame
#define iResolution uResolution
// This doesn't quite match the implementation of shadertoy, but it's close enough for many shaders
#define iMouse vec4(uMouse, uMouse*(uMouseDown?1.:-1.))
#endif

#ifdef _DYNAMIC_UNIFORMS
_DYNAMIC_UNIFORMS;
#endif
