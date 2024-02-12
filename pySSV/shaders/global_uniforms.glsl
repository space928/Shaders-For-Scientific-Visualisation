//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
/******************************************************************************
* This file declares all the built in uniforms set by pySSV and any
* uniforms declared dynamically by the preprocessor.
******************************************************************************/
#ifdef SPHINX_DOCS
// Compatibility hack for the documentation compiler which doesn't know that 'uniform' is a keyword...
#define uniform
#endif // SPHINX_DOCS
/** The time in seconds since the canvas started running. */
uniform float uTime;
/** The current frame number, starting from 0. */
uniform int uFrame;
/** The resolution of the current render buffer in pixels. */
uniform vec4 uResolution;
/** The coordinates of the mouse relative to the canvas in pixels. */
uniform vec2 uMouse;
/** Whether the mouse button is pressed. */
uniform bool uMouseDown;
/** The main camera's view matrix. */
uniform mat4x4 uViewMat;
/** The main camera's projection matrix. */
uniform mat4x4 uProjMat;
/** The forward vector of the main camera. */
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
