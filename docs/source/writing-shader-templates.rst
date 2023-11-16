
.. _writing-shader-templates:

========================
Writing Shader Templates
========================

*pySSV* has a powerful shader templating system which aims to reduce boilerplate code and improve compatibility of
shaders with different rendering backends.

When a user writes a shader they specify which shader template to compile with using the ``#pragma SSV <template_name>``
directive. The preprocessor searches for the template specified by the user in the following order:

1. Templates passed in to the ``shader()`` method along with the source code.
2. Templates in the folder passed in to the ``shader()`` method.
3. Templates in the built in templates folder (packaged with pySSV).

Shader templates must have a filename in the form ``template_<template_name>.glsl`` to be found. For instance, if the
following shader source code is passed in the ``shader()`` method:

.. code-block:: glsl

    #pragma SSV shadertoy frag
    // The entrypoint to the fragment shader
    vec4 frag(vec2 fragPos)
    {
        vec2 uv = fragPos.xy / uResolution.xy;

        return mix(uv.xyx, uv.yyx, sin(uTime)*0.5+0.5);
    }

The shader preprocessor will search for the template: ``template_shadertoy.glsl`` this template is parsed to determine
to parse further arguments in the ``#pragma SSV <template_name> ...`` directive. The template file is then preprocessed
with the user's source code and template parameters injected in to the template.

In this example the ``shadertoy`` shader template looks like this:

.. code-block:: glsl

    #pragma SSVTemplate define shadertoy --author "Thomas Mathieson" \
            --description "A simple full screen pixel shader with compatibility for Shadertoy shaders."
    #pragma SSVTemplate stage vertex
    #pragma SSVTemplate stage fragment
    // Arguments get converted into compiler defines by the preprocessor
    // an argument's name is transformed to match our naming convention:
    //    entrypoint -> T_ENTRYPOINT
    //    _varying_struct -> T_VARYING_STRUCT
    #pragma SSVTemplate arg entrypoint --default mainImage -d "The name of the entrypoint function to the shader."
    // Prefixing an argument name with an underscore is shorthand for --non_positional
    // #pragma SSVTemplate arg _varying_struct --type str
    // An example for an SDF shader
    // #pragma SSVTemplate arg _render_mode --choices solid xray isolines 2d

    #define SHADERTOY_COMPAT
    // Include any default includes we think the user might want
    // compat.glsl automatically declares the #version and precision directives when needed, it should always be the
    // first file to be included in the template.
    #include "compat.glsl"
    // global_uniforms.glsl contains the declarations for all uniforms which are automatically passed in by pySSV
    #include "global_uniforms.glsl"


    // Use these preprocessor blocks to specify what code to compile for each shader stage.
    // These macros (SHADER_STAGE_<stage_name>) are defined automatically by the preprocessor.
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

    // Including the magic string "TEMPLATE_DATA" causes the user's shader code to be injected here.
    #include "TEMPLATE_DATA"

    void main() {
        // Not using the color attribute causes the compiler to strip it and confuses modernGL.
        // T_ENTRYPOINT is a macro that was defined automatically when the argument defined
        // by '#pragma SSVTemplate arg entrypoint' was passed in.
        fragColor = T_ENTRYPOINT(position * iResolution) + vec4(color, 1.0)*1e-6;
    }
    #endif //SHADER_STAGE_FRAGMENT

When preprocessing the template the arguments passed in to the ``#pragma SSV <template_name>`` directive are converted
to preprocessor defines. Argument names are converted to uppercase and prefixed with ``T_``, so the argument
``entrypoint`` is passed in to the shader template as ``#define T_ENTRYPOINT <value>``. The glsl source passed in by
the user to the template is injected in the shader template using the special ``#include "TEMPLATE_DATA"`` directive
which simply expands to the user's glsl code when preprocessed. Arguments are passed in to the shader as defines
exactly as they are specified by the user::

    // If the user specifies these arguments
    #pragma SSV sdf sdf_main --camera_speed -1.5 --light_dir "normalize(vec3(0.1, 0.2, 0.3))"

    // They will be defined by the preprocessor as
    #define T_ENTRYPOINT sdf_main
    #define T_CAMERA_SPEED -1.5
    // Notice in this case that to specify a value which contains whitespace, it must be wrapped in quotation marks.
    // A few basic c++ style escape sequences are supported in this case as well (\", \n, \t).
    #define T_LIGHT_DIR normalize(vec3(0.1, 0.2, 0.3))

``SSVTemplate`` Directives
--------------------------

The template is parametrised using ``#pragma SSVTemplate`` directives.

Define Directive
^^^^^^^^^^^^^^^^

``#pragma SSVTemplate define``

This directive is used to define a shader template and any metadata associated with it.

**Parameters:**

.. option:: name

    The name of the shader template. This should only consist of characters valid in filenames and should not contain
    spaces.


.. option:: --author

    The shader template's author.


.. option:: --description

    A brief description of the shader template and what it does.


Stage Directive
^^^^^^^^^^^^^^^

``#pragma SSVTemplate stage``

This directive specifies a shader stage to compile this template for.

**Parameters:**

.. option:: stage

    The stage(s) to compile for. Accepts one or more of: ``vertex``, ``fragment``, ``tess_control``,
    ``tess_evaluation``, ``geometry``, or ``compute``.


Arg Directive
^^^^^^^^^^^^^

``#pragma SSVTemplate arg``

This directive defines an argument to be passed in to the shader template in the ``#pragma SSV <template_name> [args]``
directive.

**Parameters:**

.. option:: name

    The name of the argument to be passed in to the shader; prefixing the name with an underscore implies the
    ``--non_positional`` flag.

.. option:: --non_positional

    *[Flag]* Treat this as a non-positional argument; it's name is automatically prefixed with ``--``.

.. option:: --action

    What to do when this argument is encountered. Accepts the following options:

    1. ``store`` (default) Stores the value the user passes in to the argument in the argument.
    2. ``store_const`` Stores a constant value (defined in ``--const``) in the argument when this flag is specified.
    3. ``store_true`` A special case of ``store_const`` which stores ``true`` when the flag is specified and ``false``
       if it isn't.
    4. ``store_false`` The inverse of ``store_true``.

.. option:: --default

    The default value for this argument if it isn't specified.

.. option:: --choices

    Limits the valid values of this argument to those specified here. This parameter accepts multiple values.

.. option:: --const

    When using the 'store_const' action, specifies what value to store.

