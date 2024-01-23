
.. _installation:

Installation
============


The simplest way to install pySSV is via pip::

    pip install pySSV

or via conda::

    conda install pySSV


If you don't already have Jupyter Lab installed, install via pip::

    pip install jupyterlab==4.*

If you installed via pip, and are using Jupyter Notebook version < 5.3, you will also have to
install / configure the front-end extension as well. If you are using classic
notebook (as opposed to Jupyterlab), run::

    jupyter nbextension install [--sys-prefix / --user / --system] --py pySSV

    jupyter nbextension enable [--sys-prefix / --user / --system] --py pySSV

with the `appropriate flag`_.


.. links

.. _`appropriate flag`: https://jupyter-notebook.readthedocs.io/en/stable/extending/frontend_extensions.html#installing-and-enabling-extensions
