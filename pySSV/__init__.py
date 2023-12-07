#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from typing import Optional

from .ssv_render_widget import SSVRenderWidget
from .ssv_canvas import SSVCanvas
from .ssv_logging import log

try:
    from ._version import __version__
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

def canvas(size: Optional[tuple[int, int]] = (640, 480), backend: str = "opengl", standalone: bool = False,
           target_framerate: int = 60, use_renderdoc: bool = False):
    """
    Creates a new ``SSVCanvas`` which contains the render widget and manages the render context.

    :param size: the default resolution of the renderer as a tuple: ``(width: int, height: int)``.
    :param backend: the rendering backend to use; currently supports: ``"opengl"``.
    :param standalone: whether the canvas should run standalone, or attempt to create a Jupyter Widget for
                       rendering.
    :param target_framerate: the default framerate to target when running.
    :param use_renderdoc: optionally, an instance of the Renderdoc in-app api to provide support for frame
                           capturing and analysis in renderdoc.
    """

    return SSVCanvas(size, backend, standalone, target_framerate, use_renderdoc)
