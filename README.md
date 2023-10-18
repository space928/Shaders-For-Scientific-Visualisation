# Shaders For Scientific Visualisation
**Author:** _Thomas Mathieson_  
**Student ID:** _2576219m_  
**Supervisor:** _Dr. John Williamson_  

[![Build Status](https://travis-ci.org/space928/Shaders-For-Scientific-Visualisation.svg?branch=master)](https://travis-ci.org/space928/pySSV)

A python library for advanced interactive data visualisation on the GPU. This project is being developed for my Level 4 
Individual Project at the University of Glasgow for my Computing Science degree.

The dissertation and accompanying notes and planning documents can be found 
[here](https://github.com/space928/Shaders-For-Scientific-Visualisation-Notes).

## Installation

You can install using `pip`:

```bash
pip install pySSV
```

If you are using Jupyter Notebook 5.2 or earlier, you may also need to enable
the nbextension:
```bash
jupyter nbextension enable --py [--sys-prefix|--user|--system] pySSV
```

## Getting Started

### Try the example notebook
Create a suitable python environment (optional if you already have a python environment with jupyterlab setup) and install the package using `pip`:
```bash
conda create -n pySSV -c conda-forge python jupyterlab
conda activate pySSV

pip install pySSV
```
Download the example notebook from github:
```bash
curl -o introduction.ipynb https://github.com/space928/Shaders-For-Scientific-Visualisation/raw/main/examples/introduction.ipynb
```
Start JupyterLab and play around with the notebook:
```bash
jupyter lab .\introduction.ipynb
```

## Building

Create a dev environment:
```bash
conda create -n pySSV-dev -c conda-forge nodejs yarn python jupyterlab
conda activate pySSV-dev
```

Install the python. This will also build the TS package.
```bash
pip install -e ".[test, examples]"
```

When developing your extensions, you need to manually enable your extensions with the
notebook / lab frontend. For lab, this is done by the command:

```bash
jupyter labextension develop --overwrite .
yarn run build
```

For classic notebook, you need to run:

```bash
jupyter nbextension install --sys-prefix --symlink --overwrite --py pySSV
jupyter nbextension enable --sys-prefix --py pySSV
```

Note that the `--symlink` flag **doesn't work on Windows**, so you will here have to run
the `install` command every time that you rebuild your extension. For certain installations
you might also need another flag instead of `--sys-prefix`, but we won't cover the meaning
of those flags here.

### How to see your changes
#### Typescript:
If you use JupyterLab to develop then you can watch the source directory and run JupyterLab at the same time in different
terminals to watch for changes in the extension's source and automatically rebuild the widget.

```bash
# Watch the source directory in one terminal, automatically rebuilding when needed
yarn run watch
# Run JupyterLab in another terminal
jupyter lab
```

After a change wait for the build to finish and then refresh your browser and the changes should take effect.

#### Python:
If you make a change to the python code then you will need to restart the notebook kernel to have it take effect.

## Updating the version

To update the version, install tbump and use it to bump the version.
By default it will also create a tag.

```bash
pip install tbump
tbump <new-version>
```

## Acknowledgements

Thanks to Dr. John H. Williamson for his support throughout the project.

This project was made using the fabulous Jupyter Widget template: 
https://github.com/jupyter-widgets/widget-ts-cookiecutter
