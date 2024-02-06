//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
/******************************************************************************
* This file serves a compatibility layer allowing different GLSL compilers
* to be used; it relies on special preprocessor pragma to work.
* Including this, automatically defines the GLSL version, any needed
* compiler extensions, and the default precision.
******************************************************************************/
#ifdef _GL_VERSION
// This macro will expand to a version directive which is needed by the compiler, it must be the first non-whitespace/
// comment token in the shader file!
// This special pragma allows us to temporarily disable #line directives in the preprocessor to ensure that the version
// directive is the first in the file.
#pragma PreventLine true
_GL_VERSION
#ifdef _GL_ADDITIONAL_EXTENSIONS
_GL_ADDITIONAL_EXTENSIONS
#endif
#ifdef _GL_SUPPORTS_LINE_DIRECTIVES
#extension GL_ARB_shading_language_include : require
#pragma PreventLine false
#endif // _GL_SUPPORTS_LINE_DIRECTIVES
#endif // _GL_VERSION

#ifdef _GL_PRECISION
// In OpenGL ES you need to specify the precision of variables, you can do this per-variable or specify a default.
// https://stackoverflow.com/a/6336285
precision highp float;
#endif // _GL_PRECISION
