#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.

# mypy: ignore-errors

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

#
# pySSV documentation build configuration file
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.


# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.todo',
    'nbsphinx',
    'jupyter_sphinx',
    'nbsphinx_link',
    'sphinx_c_autodoc',
    'sphinx_c_autodoc.viewcode'
]

# Set the nbsphinx JS path to empty to avoid showing twice of the widgets
nbsphinx_requirejs_path = ""
nbsphinx_widgets_path = ""

# Ensure our extension is available:
import sys
from os.path import dirname, join as pjoin
import os

docs = dirname(dirname(__file__))
root = dirname(docs)
sys.path.insert(0, root)
sys.path.insert(0, pjoin(docs, 'sphinxext'))

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'pySSV'
copyright = '2023-2024, Thomas Mathieson'
author = 'Thomas Mathieson'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.


# get version from python package:
import os

here = os.path.dirname(__file__)
repo = os.path.join(here, '..', '..')
_version_py = os.path.join(repo, 'pySSV', '_version.py')
version_ns = {}
with open(_version_py) as f:
    exec(f.read(), version_ns)

# The short X.Y version.
version = '.'.join(version_ns['__version__'].split('.')[:2])
# The full version, including alpha/beta/rc tags.
release = version_ns['__version__']

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ['**.ipynb_checkpoints']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -- Options for autodoc --------------------------------------------------

autoclass_content = "both"
autodoc_member_order = "bysource"
autodoc_default_options = {
    "member-order": "bysource",
    # "special-members": "__init__",
    "undoc-members": False,
    # "exclude-members": "__weakref__"
}
autodoc_typehints = "both"

# -- Options for C autodoc ------------------------------------------------
if "win" in sys.platform:
    from clang.cindex import Config
    llvm_paths = [p for p in os.environ["path"].split(";") if "llvm" in p.lower()]
    if len(llvm_paths) > 0:
        Config.set_library_path(llvm_paths[0])
    # Config.set_library_file('libclang.dll')
if 'READTHEDOCS' in os.environ:
    from clang.cindex import Config
    Config.set_library_file("/usr/lib/llvm-14/lib/libclang.so.1")

c_autodoc_roots = ["../../pySSV/shaders", ""]
c_autodoc_compilation_args = ["-xc", "-DSPHINX_DOCS", "-include glsl_support.h"]

# -- Options for HTML output ----------------------------------------------


# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'pySSVdoc'

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'pySSV.tex', 'pySSV Documentation',
     'Thomas Mathieson', 'manual'),
]

# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc,
     'pySSV',
     'pySSV Documentation',
     [author], 1)
]

# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc,
     'pySSV',
     'pySSV Documentation',
     author,
     'pySSV',
     'Leverage the power of shaders for scientific visualisation in Jupyter',
     'Miscellaneous'),
]

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "rtd": ("https://docs.readthedocs.io/en/stable/", None),
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}

# Read The Docs
# on_rtd is whether we are on readthedocs.org, this line of code grabbed from
# docs.readthedocs.org
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

html_theme = 'sphinx_rtd_theme'
if not on_rtd:  # only import and set the theme if we're building docs locally
    import sphinx_rtd_theme

    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# otherwise, readthedocs.org uses their theme by default, so no need to specify it


# Uncomment this line if you have know exceptions in your included notebooks
# that nbsphinx complains about:
#
nbsphinx_allow_errors = True  # exception ipstruct.py ipython_genutils
# Prevent Jupyter notebooks from being automatically executed during the docs build
nbsphinx_execute = 'never'

from sphinx.util import logging

logger = logging.getLogger(__name__)


def setup(app):
    def add_scripts(app):
        for fname in ['helper.js', 'embed-bundle.js']:
            if not os.path.exists(os.path.join(here, '_static', fname)):
                logger.warning('missing javascript file: %s' % fname)
            app.add_js_file(fname)

    def pre_process(app, filename, contents, *args):
        file_body: str = contents[0]

        lines = file_body.splitlines()
        if len(lines) > 1:
            # If the first line is a copyright block, then skip the first two lines...
            if "copyright (c)" in lines[0].lower():
                lines = lines[2:]

        # replace the list to return back to the sphinx extension
        contents[:] = ["\n".join(lines)]

    app.connect("c-autodoc-pre-process", pre_process)
    app.connect('builder-inited', add_scripts)
