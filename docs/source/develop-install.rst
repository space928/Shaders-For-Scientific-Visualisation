
Developer install
=================


To install a developer version of pySSV, you will first need to clone the repository::

    git clone https://github.com/space928/Shaders-For-Scientific-Visualisation
    cd Shaders-For-Scientific-Visualisation

You can optionally create a new Python dev environment::

    conda create -n pySSV-dev -c conda-forge nodejs yarn python jupyterlab=4
    conda activate pySSV-dev

Install the python package. This will also build the TS package::

    pip install -e ".[test, examples]"

The ``jlpm`` command is JupyterLab's pinned version of [yarn](https://yarnpkg.com/) that is installed with JupyterLab.
You may use ``yarn`` or ``npm`` in lieu of ``jlpm`` below. Using ``jlpm`` and ``yarn`` sometimes breaks the package
cache if this happens, just delete the ``yarn.lock`` file and the ``.yarn`` folder and rerun ``jlpm install``.

When developing your extensions, you need to manually enable your extensions with the notebook / lab frontend. For
Jupyter Notebook, this is done with the command:

    jupyter nbextension install [--sys-prefix / --user / --system] --symlink --py pySSV
    jupyter nbextension enable [--sys-prefix / --user / --system] --py pySSV

with the `appropriate flag`_.

Or, if you are using Jupyterlab::

    jupyter labextension develop --overwrite .

Build the frontend of the plugin::

    jlpm run build

If you plan on making changes to the plugin frontend (any of the typescript), then run the watch task to automatically
rebuild the plugin when there are changes. Changes to the python are automatically reloaded when the Jupyter Kernel is
restarted::

    jlpm run watch

If you're building the documentation, you'll also need to have the libclang binaries installed. On Windows these can be
installed with chocolatey::

    choco install llvm

.. links

.. _`appropriate flag`: https://jupyter-notebook.readthedocs.io/en/stable/extending/frontend_extensions.html#installing-and-enabling-extensions
