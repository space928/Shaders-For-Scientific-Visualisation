#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import io
import logging
import os.path
import sys
from typing import Optional

import pcpp
import argparse
from importlib.resources import as_file, files

from .ssv_logging import log
from .ssv_pragma_parser import SSVShaderPragmaParser, SSVTemplatePragmaParser, SSVTemplatePragmaData
from .ssv_shader_source_preprocessor import SSVShaderSourcePreprocessor


class SSVShaderPreprocessor:
    """

    """

    def __init__(self):
        self._template_parser = SSVTemplatePragmaParser()
        self._shader_parser = SSVShaderPragmaParser()

    @staticmethod
    def _make_argparse(template_metadata: list[SSVTemplatePragmaData]) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser("SSV Shader Preprocessor")

        short_args = set()
        for arg in template_metadata:
            if arg.command != "arg" or len(arg.name) == 0:
                continue

            # Convert the argument name to a positional/non-positional name
            prefixed = arg.name[0] == "_"
            non_positional = arg.non_positional or prefixed
            arg_name = (arg.name,)
            if non_positional:
                name = f"--{arg.name[1 if prefixed else 0:]}"
                short_name = name[1:3]
                if short_name in short_args:
                    arg_name = (name,)
                else:
                    arg_name = (name, short_name)
                    short_args.add(short_name)

            params = {"action": arg.action}
            if arg.const is not None:
                params["const"] = arg.const
            if arg.choices is not None and len(arg.choices) > 0:
                params["choices"] = arg.choices
            if arg.default is not None:
                params["default"] = arg.default
            if arg.description is not None and len(arg.description) > 0:
                params["help"] = " ".join(arg.description)

            parser.add_argument(*arg_name, **params)

        return parser

    @staticmethod
    def _make_defines(template_args: argparse.Namespace) -> list[tuple[str, str]]:
        """
        Converts templates arguments from an argparse namespace to a list of tuples::

            (entrypoint='frag') -> (T_ENTRYPOINT, 'frag')
            (_mode='xray') -> (T_MODE, 'xray')
            (_shadertoy_compat='True') -> (T_SHADERTOY_COMPAT, '1')
            (_foo='False') -> <nothing>

        :param template_args: an argparse Namespace object.
        :return: a list of tuples of shader defines.
        """
        defines = []
        for arg, val in template_args.__dict__.items():
            if val == "False":
                # Don't define  defines which are set to false
                continue
            if val == "True":
                val = "1"

            name = f"T_{(arg[1:] if arg[0] == '_' else arg).upper()}"
            defines.append((name, val))

        defines.append(("SSV_SHADER", "1"))
        defines.append(("_GL_VERSION", "#version 420"))

        return defines

    def preprocess(self, source: str, filepath: Optional[str] = None,
                   additional_template_directory: Optional[str] = None,
                   additional_templates: Optional[list[str]] = None):
        """
        Preprocesses an SSV shader into multiple processed shaders for each pipeline.

        :param source: the shader source code to preprocess. It should contain the necessary
                       ``#pragma SSV <template_name>`` directive see :ref:`built-in-shader-templates` for more
                       information.
        :param filepath: the filepath of the shader, used to help the preprocessor give more meaningful error messages.
        :param additional_template_directory: a path to a directory containing custom shader templates. See
                                              :ref:`writing-shader-templates` for information about using custom shader
                                              templates.
        :param additional_templates: a list of custom shader templates (source code, not paths).See
                                     :ref:`writing-shader-templates` for information about using custom shader
                                     templates.
        :return: a dict of compiled shaders for each of the required pipeline stages.
        """
        template_info = self._shader_parser.parse(source, filepath)

        # Find the relevant template
        template_source = None
        template_path = None
        template_expected_filename = f"template_{template_info.template.lower()}.glsl"

        # Check the additional_templates first
        if additional_templates is not None:
            for template in additional_templates:
                template_metadata = self._template_parser.parse(template, "additional_templates[]")
                for pragma in template_metadata:
                    if pragma.command == "define" and pragma.name.lower() == template_info.template.lower():
                        template_source = template
                        template_path = pragma.name
                        break
                if template_source is not None:
                    break

        # Then check the additional_templates_directory
        if template_source is None and additional_template_directory is not None:
            if os.path.isdir(additional_template_directory):
                for file_name in os.listdir(additional_template_directory):
                    if os.path.basename(file_name).lower() == template_expected_filename:
                        try:
                            with open(file_name, "r") as f:
                                template_source = f.read()
                            template_path = file_name
                        except Exception as e:
                            raise FileNotFoundError(f"Couldn't read shader template '{file_name}' in additional "
                                                    f"template directory! \n"
                                                    f"Inner exception: {e}")
                        break
            else:
                raise NotADirectoryError(
                    f"Additional template directory is not a valid directory: {additional_template_directory}")

        # Finally, check the built-in shaders
        if template_source is None:
            try:
                template_traversable = files("pySSV.shaders").joinpath(template_expected_filename)
                template_source = template_traversable.read_text()
                template_path = template_expected_filename
            except Exception as e:
                raise FileNotFoundError(f"Couldn't find/read a shader template called '{template_info.template}', "
                                        f"it should be in a file called '{template_expected_filename}'. \n"
                                        f"Inner exception: {e}")

        # Parse template args
        template_metadata = self._template_parser.parse(template_source, template_path)

        # Construct and argparse using the template metadata
        template_argparse = self._make_argparse(template_metadata)
        # Parse the template_info
        parsed_args = template_argparse.parse_args(template_info.args)
        defines = self._make_defines(parsed_args)

        stages = []
        for template_data in template_metadata:
            if template_data.command == "stage":
                stages.extend(template_data.shader_stage)

        # Preprocess the template
        compiled_shaders = {}
        for stage in stages:
            preprocessor = SSVShaderSourcePreprocessor(source)
            defines_stage = defines + [(f"SHADER_STAGE_{stage.upper()}", "1")]
            for d in defines_stage:
                # macro = pcpp.parser.Macro(d[0], d[1])
                # macro.source = "GLOBAL"
                # macro.lineno = -1
                # preprocessor.macros[d[0]] = macro
                preprocessor.define(f"{d[0]} {d[1]}")

            preprocessor.parse(template_source, template_path)
            shader = io.StringIO()
            preprocessor.write(shader)
            compiled_shaders[f"{stage}_shader"] = shader.getvalue()
        return compiled_shaders
