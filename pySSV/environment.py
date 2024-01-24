#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

# This snippet for detecting the python environment is taken from:
# https://github.com/InsightSoftwareConsortium/itkwidgets/blob/main/itkwidgets/integrations/environment.py Licensed
# under the Apache License 2.0: https://github.com/InsightSoftwareConsortium/itkwidgets/blob/main/LICENSE
from enum import Enum
import sys


class Env(Enum):
    JUPYTER_NOTEBOOK = 'notebook'
    JUPYTERLAB = 'lab'
    JUPYTERLITE = 'lite'
    SAGEMAKER = 'sagemaker'
    HYPHA = 'hypha'
    COLAB = 'colab'


def find_env():
    try:
        from google.colab import files  # type: ignore
        return Env.COLAB
    except ImportError:
        try:
            from IPython import get_ipython  # type: ignore
            if get_ipython() is None:
                # Hack
                return Env.JUPYTERLAB
            parent_header = get_ipython().parent_header
            username = parent_header['header']['username']
            if username == '':
                return Env.JUPYTERLAB
            elif username == 'username':
                return Env.JUPYTER_NOTEBOOK
            else:
                return Env.SAGEMAKER
        except ImportError:
            import sys
            if sys.platform == 'emscripten':
                return Env.JUPYTERLITE
            return Env.HYPHA


ENVIRONMENT = find_env()
