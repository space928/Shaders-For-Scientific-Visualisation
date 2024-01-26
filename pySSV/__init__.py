#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from typing import Optional, Tuple

from .ssv_render_widget import SSVRenderWidget
from .ssv_canvas import SSVCanvas
from .ssv_logging import log

try:
    from ._version import __version__  # type: ignore
except ImportError:
    # Fallback when using the package in dev mode without installing in editable mode with pip. It is highly
    # recommended to install the package from a stable release or in editable mode:
    # https://pip.pypa.io/en/stable/topics/local-project-installs/#editable-installs
    import warnings

    warnings.warn("Importing 'pySSV' outside a proper installation.")
    __version__ = "dev"


def _jupyter_labextension_paths():
    return [{
        "src": "labextension",
        "dest": "py-ssv"
    }]


def _jupyter_nbextension_paths():
    return [dict(
        section="notebook",
        src="nbextension",
        dest="py-ssv",
        require="py-ssv/index")]


# Various factory methods

def canvas(size: Optional[Tuple[int, int]] = (640, 480), backend: str = "opengl",
           gl_version: Optional[Tuple[int, int]] = None, standalone: bool = False, target_framerate: int = 60,
           use_renderdoc: bool = False, supports_line_directives: Optional[bool] = None):
    """
    Creates a new ``SSVCanvas`` which contains the render widget and manages the render context.

    :param size: the default resolution of the renderer as a tuple: ``(width: int, height: int)``.
    :param backend: the rendering backend to use; currently supports: ``"opengl"``.
    :param gl_version: optionally, the minimum version of OpenGL to support. Accepts a tuple of (major, minor), eg:
                       gl_version=(4, 2) for OpenGL 4.2 Core.
    :param standalone: whether the canvas should run standalone, or attempt to create a Jupyter Widget for
                       rendering.
    :param target_framerate: the default framerate to target when running.
    :param use_renderdoc: optionally, an instance of the Renderdoc in-app api to provide support for frame
                           capturing and analysis in renderdoc.
    :param supports_line_directives: whether the shader compiler supports ``#line`` directives (Nvidia GPUs only). Set
                                     to ``None`` for automatic detection. If you get
                                     'extension not supported: GL_ARB_shading_language_include' errors, set this to
                                     ``False``.
    """

    return SSVCanvas(size, backend, gl_version, standalone, target_framerate, use_renderdoc, supports_line_directives)
