
.. _built-in-shader-templates:

=========================
Built In Shader Templates
=========================

To reduce boilerplate code, *pySSV* includes a selection of shader templates which generate any platform/compiler
specific code needed for the shader. These templates should handle most needs for scientific visualisation, but if you
want to write your own shader templates to add new functionality or simplify your workflow refer to
:ref:`writing-shader-templates` for details on writing shader templates.

Built In Shader Uniforms
------------------------

.. c:namespace:: global_uniforms

All built in shader templates include the ``global_uniforms.glsl`` library which defines a variety of useful shader
uniforms which are set automatically by *pySSV*. It also includes any automatically defined uniforms (such as textures
and render buffer textures).

.. c:var:: float uTime

    The current time since the shader was started in seconds.

.. c:var:: int uFrame

    The current frame number of the shader.

.. c:var:: vec4 uResolution

    The resolution of the render buffer this shader is rendering to.

.. c:var:: vec2 uMouse

    The current mouse position in pixel coordinates.

.. c:var:: bool uMouseDown

    Whether a mouse button is pressed.

.. c:var:: mat4x4 uViewMat

    The view matrix for the ``SSVCanvas``'s main camera.

.. c:var:: mat4x4 uProjMat

    The projection matrix for the ``SSVCanvas``'s main camera.

.. c:var:: vec3 uViewDir

    The view direction for the ``SSVCanvas``'s main camera.


If ``SHADERTOY_COMPAT`` is ``#define`` before importing the ``global_uniforms.glsl`` file (which is the case in the
Shadertoy template) then the following uniforms are also defined as aliases of the above uniforms.

.. c:macro:: iTime

    ``= uTime``

.. c:macro:: iFrame

    ``= uFrame``

.. c:macro:: iResolution

    ``= uResolution``

.. c:macro:: iMouse

    ``= vec4(uMouse, uMouse*(uMouseDown?1.:-1.))``

    This doesn't quite match the implementation of shadertoy, but it's close enough for many shaders.

.. c:macro:: _DYNAMIC_UNIFORMS

    This macro is defined automatically by *pySSV* and expands to include the declarations of all automatically declared
    uniforms, such as user-defined textures and render buffer textures.


Pixel Shader Template
---------------------

``#pragma SSV pixel``

.. c:namespace:: pixel

This template exposes a single entrypoint to a pixel shader.

Entrypoint Signature
^^^^^^^^^^^^^^^^^^^^

.. c:function:: vec4 entrypoint(vec2 fragPos)

    :param fragPos: the position of the pixel being processed by this shader invocation in pixel coordinates.
    :returns: the pixel's colour.

Template Arguments
^^^^^^^^^^^^^^^^^^

*None*

Example
^^^^^^^

.. code-block:: glsl

    #pragma SSV pixel frag
    // The entrypoint to the fragment shader
    vec4 frag(vec2 fragPos)
    {
        vec2 uv = fragPos.xy / uResolution.xy;

        return mix(uv.xyx, uv.yyx, sin(uTime)*0.5+0.5);
    }


Vertex Shader Template
----------------------

``#pragma SSV vert``

.. c:namespace:: vert

This template exposes a single entrypoint to a vertex shader.

Entrypoint Signature
^^^^^^^^^^^^^^^^^^^^

.. c:function:: VertexOutput mainVert()

    :returns: a ``VertexOutput`` struct containing the transformed vertex data.

.. c:struct:: VertexOutput

    .. c:var:: vec4 position
    .. c:var:: vec4 color

The shader is expected to take input from the following vertex attributes:

.. c:var:: vec4 in_vert
.. c:var:: vec4 in_color


Template Arguments
^^^^^^^^^^^^^^^^^^

*None*

Example
^^^^^^^

.. code-block:: glsl

    #pragma SSV vert mainVert
    VertexOutput mainVert()
    {
        VertexOutput o;
        vec4 pos = vec4(in_vert, 1., 1.0);
        pos = uViewMat * pos;
        pos = uProjMat * pos;
        o.position = pos;
        o.color = vec4(in_color, 1.);
        return o;
    }


ShaderToy Template
------------------

``#pragma SSV shadertoy``

.. c:namespace:: shadertoy

This template exposes a single entrypoint to a pixel shader. It's designed to mimic the API of ShaderToy

Entrypoint Signature
^^^^^^^^^^^^^^^^^^^^

.. c:function:: void mainImage(vec4 fragColor, vec2 fragCoord)

    :param out fragColor: the pixel's final colour.
    :param fragPos: the position of the pixel being processed by this shader invocation in pixel coordinates.

Template Arguments
^^^^^^^^^^^^^^^^^^

*None*

Example
^^^^^^^

.. code-block:: glsl

    #pragma SSV shadertoy
    void mainImage(out vec4 fragColor, in vec2 fragCoord)
    {
        // Normalized pixel coordinates (from 0 to 1)
        vec2 uv = fragCoord/iResolution.yy;
        // Colour changing over time
        vec3 col = sin(uv.xyx + iTime * vec3(3, 4, 5)) * 0.5 + 0.5;
        // Output to screen
        fragColor = vec4(vec3(col), 1.);
    }


Vertex/Pixel Shader Template
----------------------------

*Not yet implemented*


Signed Distance Field Template
------------------------------

``#pragma SSV sdf``

.. c:namespace:: sdf

This template exposes a single entrypoint to a pixel shader. It's designed to mimic the API of ShaderToy

Entrypoint Signature
^^^^^^^^^^^^^^^^^^^^

.. c:function:: float map(vec3 pos)

    :param pos: the position to sample sample the signed distance field at.
    :returns: the signed distance to the surface.

Template Arguments
^^^^^^^^^^^^^^^^^^

.. option:: --camera_distance

    *default*: ``10.0``

    *type*: ``float``

    The distance of the camera from the centre of the distance field.

.. option:: --rotate_speed

    *default*: ``0.1``

    *type*: ``float``

    The orbit speed of the camera around the SDF, in radians/second.

.. option:: --raymarch_steps

    *default*: ``128``

    *type*: ``int``

    The number of raymarching steps to use when rendering, turn this up if the edges of surfaces look soft.

.. option:: --raymarch_distance

    *default*: ``32.0``

    *type*: ``float``

    The maximum distance to raymarch.

.. option:: --light_dir

    *default*: ``normalize(vec3(0.5, 0.5, -0.9))``

    *type*: ``vec3``

    The maximum distance to raymarch.

.. option:: --render_mode

    *choices*: ``SOLID, DEPTH, XRAY, ISOLINES``

    *default*: ``SOLID``

    How the distance field should be rendered. Check the documentation for more information about each mode.

Example
^^^^^^^

.. code-block:: glsl

    #pragma SSV sdf sdf_main --camera_distance 2. --rotate_speed 1.5 --render_mode SOLID

    // SDF taken from: https://iquilezles.org/articles/distfunctions/
    float sdCappedTorus(vec3 p, vec2 sc, float ra, float rb) {
      p.x = abs(p.x);
      float k = (sc.y*p.x>sc.x*p.y) ? dot(p.xy,sc) : length(p.xy);
      return sqrt( dot(p,p) + ra*ra - 2.0*ra*k ) - rb;
    }

    float sdf_main(vec3 p) {
        float t = 2.*(sin(uTime)*0.5+0.5)+0.2;
        return sdCappedTorus(p, vec2(sin(t), cos(t)), 0.5, 0.2);
    }


Point Cloud Template
--------------------

``#pragma SSV point_cloud``

.. c:namespace:: point_cloud

This template exposes a single entrypoint to a vertex shader. It treats input vertices as points and uses a geometry
shader to turn each vertex into a camera-facing sprite.

Entrypoint Signature
^^^^^^^^^^^^^^^^^^^^

.. c:function:: VertexOutput vert()

    :returns: a VertexOutput struct containing the transformed vertex.

.. c:struct:: VertexOutput

    .. c:var:: vec4 position
    .. c:var:: float size

        The size of the sprite representing the point.

    .. c:var:: vec4 color

The shader is expected to take input from the following vertex attributes:

.. c:var:: vec4 in_vert
.. c:var:: vec4 in_color

Template Arguments
^^^^^^^^^^^^^^^^^^

*None*

Example
^^^^^^^

.. code-block:: glsl

    #pragma SSV point_cloud mainPoint
    VertexOutput mainPoint()
    {
        VertexOutput o;
        vec4 pos = vec4(in_vert, 1.0);
        pos = uViewMat * pos;
        pos = uProjMat * pos;
        o.position = pos;
        o.color = vec4(in_color, 1.);
        o.size = 30.0/uResolution.x;
        return o;
    }


Render Test
-----------

``#pragma SSV render_test``

.. c:namespace:: render_test

This template generates a simple pixel shader which displays a colour changing gradient. Useful as a shorthand to make
a quick shader to test the rendering system.

Entrypoint Signature
^^^^^^^^^^^^^^^^^^^^

*None*

Template Arguments
^^^^^^^^^^^^^^^^^^

*None*

Example
^^^^^^^

.. code-block:: glsl

    #pragma SSV render_test



Geometry Shader Template
------------------------

``#pragma SSV geometry``

.. c:namespace:: geometry

This template exposes an entrypoint to a vertex shader and an entrypoint to a geometry shader. It treats input vertices
as points which are processed by the user defined vertex shader and can then be turned into triangle primitives by the
user defined geometry shader.

Entrypoint Signature
^^^^^^^^^^^^^^^^^^^^

Vertex Stage
____________

.. c:function:: VertexOutput vert()

    Where ``VertexOutput`` is substituted for the value of ``--vertex_output_struct``.

:returns: a <VertexOutput> struct containing the transformed vertex.


If the ``--vertex_output_struct`` argument isn't set then the ``<VertexOutput>`` struct is as follows:

.. c:struct:: DefaultVertexOutput

    .. c:var:: vec4 position
    .. c:var:: vec4 color
    .. c:var:: float size

        The size of the sprite representing the point.

If the ``--custom_vertex_input`` flag isn't specified then the vertex shader is expected to take input from the
following vertex attributes:

.. c:var:: vec4 in_vert
.. c:var:: vec4 in_color

Geometry Stage
______________

.. c:function:: void geo(VertexOutput i)

    :param i: the struct containing the processed vertex data


The geometry function is expected to write to these output variables before each call to ``EmitVertex()``:

.. c:var:: vec4 gl_Position

    The transformed (clip space) position of the vertex to emit.

.. c:var:: vec4 out_color

    The final colour of the vertex to be emitted.

The geometry function is responsible for calling ``EmitVertex()`` and ``EndPrimitive()`` as needed and must not emit
more vertices in a single invocation than what is specified in ``--geo_max_vertices`` (``default=4``).

Template Arguments
^^^^^^^^^^^^^^^^^^

.. option:: entrypoint_vert

    *positional*

    *type*: ``str``

    The name of the entrypoint function to vertex the shader.

.. option:: entrypoint_geo

    *positional*

    *type*: ``str``

    The name of the entrypoint function to geometry the shader.

.. option:: --vertex_output_struct

    *default*: ``DefaultVertexOutput``

    *type*: ``float``

    The name of the struct containing data to be transferred from the vertex stage to the geometry stage.

.. option:: --geo_max_vertices

    *default*: ``4``

    *type*: ``const int``

    The maximum number of vertices which can be output be the geometry stage per input vertex. Must be a constant.

.. option:: --custom_vertex_input

    *type*: ``flag``

    When this flag is passed, the default vertex input attributes are not created and must be declared by the user.

Example
^^^^^^^

.. code-block:: glsl

    #pragma SSV geometry mainPoint mainGeo
    #ifdef SHADER_STAGE_VERTEX
    DefaultVertexOutput mainPoint()
    {
        DefaultVertexOutput o;
        // Transform the points using the camera matrices
        vec4 pos = vec4(in_vert, 1.0);
        pos = uViewMat * pos;
        pos = uProjMat * pos;
        o.position = pos;
        o.color = vec4(in_color, 1.);
        o.size = 10.0/uResolution.x;
        return o;
    }
    #endif // SHADER_STAGE_VERTEX
    #ifdef SHADER_STAGE_GEOMETRY
    void mainGeo(DefaultVertexOutput i) {
        // Generate a quad for each point
        vec4 position = i.position;
        float size = i.size;
        out_color = i.color;
        vec4 aspect_ratio = vec4(1., uResolution.x/uResolution.y, 1., 1.);
        gl_Position = position + size * vec4(-1., -1., 0.0, 0.0) * aspect_ratio;
        EmitVertex();
        gl_Position = position + size * vec4(1., -1., 0.0, 0.0) * aspect_ratio;
        EmitVertex();
        gl_Position = position + size * vec4(-1., 1., 0.0, 0.0) * aspect_ratio;
        EmitVertex();
        gl_Position = position + size * vec4(1., 1., 0.0, 0.0) * aspect_ratio;
        EmitVertex();
        EndPrimitive();
    }
    #endif // SHADER_STAGE_GEOMETRY
