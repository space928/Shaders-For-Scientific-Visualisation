==============
Shader Library
==============

*pySSV* provides a small library of commonly used GLSL functions to reduce boilerplate. These can be imported into any
shader using the ``#include "xxxx.glsl"`` directive.

^^^^^^^^^^^^^^^^^
Library Reference
^^^^^^^^^^^^^^^^^

----------------
Colour Utilities
----------------
``#include "color_utils.glsl"``

.. autocmodule:: color_utils.glsl
    :members:

----------------------------------
Random Number Generation / Hashing
----------------------------------
``#include "random.glsl"``

.. autocmodule:: random.glsl
    :members:

-------------------------------
Signed Distance Field Operators
-------------------------------
``#include "sdf_ops.glsl"``

.. autocmodule:: sdf_ops.glsl
    :members:

------------------------
Text Rendering Utilities
------------------------
``#include "text.glsl"``

.. autocmodule:: text.glsl
    :members:

^^^^^^^^^^^^^^^^^^
Internal Utilities
^^^^^^^^^^^^^^^^^^

These glsl files are usually included automatically by the shader template.

----------------------
Compiler Compatibility
----------------------
``#include "compat.glsl"``

.. autocmodule:: compat.glsl
    :members:

---------------------------
Global Uniform Declarations
---------------------------
``#include "global_uniforms.glsl"``

.. autocmodule:: global_uniforms.glsl
    :members:
