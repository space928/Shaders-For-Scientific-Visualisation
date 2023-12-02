#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

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

def canvas(size=None):
    """

    :param size:
    :return:
    """

    return SSVCanvas(size)
