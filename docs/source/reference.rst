======================
PySSV Module Reference
======================

Public API
----------

The ``SSVCanvas`` is one of the core components of *pySSV*, it's what manages and provides and interface for the three
major internal components: *the renderer*, *the widget*, and *the shader preprocessor*.

.. automodule:: pySSV.ssv_canvas
    :members:

Canvas Objects
^^^^^^^^^^^^^^

These classes must be constructed by an ``SSVCanvas``.

.. automodule:: pySSV.ssv_render_buffer
    :members:


.. automodule:: pySSV.ssv_vertex_buffer
    :members:


.. automodule:: pySSV.ssv_camera
    :members:


.. automodule:: pySSV.ssv_texture
    :members:


Internal Modules
----------------

As a user you generally won't need to interact with these modules, the documentation provided here is for developers
wanting to extend pySSV and power users wanting to better understand how *pySSV* works internally.

Utilities
^^^^^^^^^

.. automodule:: pySSV.ssv_logging
    :members:


.. automodule:: pySSV.environment
    :members:

Renderer
^^^^^^^^

.. automodule:: pySSV.ssv_render
    :members:


.. automodule:: pySSV.ssv_render_opengl
    :members:


.. automodule:: pySSV.ssv_render_process_client
    :members:


.. automodule:: pySSV.ssv_render_process_server
    :members:


Jupyter Widget
^^^^^^^^^^^^^^

.. automodule:: pySSV.ssv_render_widget
    :members:

Shader Preprocessor
^^^^^^^^^^^^^^^^^^^

.. automodule:: pySSV.ssv_shader_preprocessor
    :members:


.. automodule:: pySSV.ssv_shader_source_preprocessor
    :members:


.. automodule:: pySSV.ssv_pragma_parser
    :members:


.. automodule:: pySSV.ssv_shader_args_tokenizer
    :members:

