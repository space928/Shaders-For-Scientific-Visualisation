//  Copyright (c) 2023 Thomas Mathieson.
//  Distributed under the terms of the MIT license.
#ifdef _GL_VERSION
// This macro will expand to a version directive which is needed by the compiler, it must be the first non-whitespace/
// comment token in the shader file!
// This special pragma allows us to temporarily disable #line directives in the preprocessor to ensure that the version
// directive is the first in the file.
#pragma PreventLine true
_GL_VERSION
#extension GL_ARB_shading_language_include : require
#ifdef _GL_ADDITIONAL_EXTENSIONS
_GL_ADDITIONAL_EXTENSIONS
#endif
#pragma PreventLine false
#endif // _GL_VERSION

#ifdef _GL_PRECISION
// In OpenGL ES you need to specify the precision of variables, you can do this per-variable or specify a default.
// https://stackoverflow.com/a/6336285
precision highp float;
#endif // _GL_PRECISION
