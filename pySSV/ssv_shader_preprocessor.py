#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import io
import logging
import os.path
from typing import Any, Optional, Union, List, Dict, Tuple

import argparse
import sys
if sys.version_info >= (3, 9):
    from importlib.resources import files
else:
    from importlib.resources import contents, read_text

from .ssv_logging import log
from .ssv_pragma_parser import SSVShaderPragmaParser, SSVTemplatePragmaParser, SSVTemplatePragmaData
from .ssv_shader_source_preprocessor import SSVShaderSourcePreprocessor


class SSVShaderPreprocessor:
    """
    This class is responsible for preprocessing shader source code and shader templates into platform specific, ready
    to compile shaders for each pipeline stage.
    """

    def __init__(self, gl_version: str, supports_line_directives: bool):
        self._gl_version = gl_version
        self._supports_line_directives = supports_line_directives
        self._dynamic_uniforms: Dict[str, str] = {}
        self._global_defines: Dict[str, str] = {}
        self._template_parser = SSVTemplatePragmaParser()
        self._shader_parser = SSVShaderPragmaParser()

    @property
    def global_defines(self) -> Dict[str, str]:
        """
        Gets the (mutable) dictionary of compiler macros which are defined globally in all shaders. This does not
        include any macros defined by the ``SSVShaderPreprocessor`` itself. The dict contains key-value pairs where
        the key is the macro name and the value is the macro definition (as a C preprocessor macro).
        """
        return self._global_defines

    @staticmethod
    def _make_argparse(template_metadata: Dict[str, List[SSVTemplatePragmaData]]) -> argparse.ArgumentParser:
        template_name = "SSV"
        template_author = ""
        template_description = ""
        for arg in template_metadata.get("define", []):
            if arg.name is not None:
                template_name = arg.name
            if arg.author is not None:
                template_author = arg.author
            if arg.description is not None:
                template_description = arg.description
            break

        parser = argparse.ArgumentParser(f"#pragma SSV {template_name}",
                                         description=template_description,
                                         epilog=f"author: {template_author}",
                                         add_help=False,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        short_args = set()
        for arg in template_metadata.get("arg", []):
            if len(arg.name) == 0:
                continue

            # Convert the argument name to a positional/non-positional name
            prefixed = arg.name[0] == "_"
            non_positional = arg.non_positional or prefixed
            arg_name: Union[Tuple[str], Tuple[str, str]] = (arg.name,)
            if non_positional:
                name = f"--{arg.name[1 if prefixed else 0:]}"
                short_name = name[1:3]
                if short_name in short_args:
                    arg_name = (name,)
                else:
                    arg_name = (name, short_name)
                    short_args.add(short_name)

            params: Dict[str, Any] = {"action": arg.action}
            if arg.const is not None:
                params["const"] = arg.const
            if arg.choices is not None and len(arg.choices) > 0:
                params["choices"] = arg.choices
            if arg.default is not None:
                params["default"] = arg.default
            if arg.description is not None:
                params["help"] = arg.description
            # if non_positional:
            #     params["nargs"] = "+"

            parser.add_argument(*arg_name, **params)

        return parser

    def _make_defines(self, template_args: argparse.Namespace, template_argparse: List[SSVTemplatePragmaData],
                      extra_defines: Optional[Dict[str, str]],
                      compiler_extensions: Optional[List[str]]) -> List[Tuple[str, str]]:
        """
        Converts templates arguments from an argparse namespace to a list of tuples::

            (entrypoint='frag') -> (T_ENTRYPOINT, 'frag')
            (_mode='xray') -> (T_MODE, 'xray')
            (_shadertoy_compat='True') -> (T_SHADERTOY_COMPAT, '1')
            (_foo='False') -> <nothing>

        :param template_args: an argparse Namespace object.
        :param template_argparse: the list of SSVTemplateMetaData containing the argument definitions.
        :param extra_defines: extra preprocessor defines to be enabled globally.
        :param compiler_extensions: a list of GLSL extensions required by this shader
                                    (eg: ``GL_EXT_control_flow_attributes``)
        :return: a list of tuples of shader defines.
        """
        defines = []
        arg_templates: Dict[str, SSVTemplatePragmaData] = {
            arg.name[1:] if len(arg.name) > 1 and arg.name[0] == '_' else arg.name: arg for arg in template_argparse
        }
        global_choices: Dict[str, str] = {}
        for arg, val in template_args.__dict__.items():
            if issubclass(type(val), list):
                # Hack to support arguments containing spaces
                val = " ".join(val)
            if issubclass(type(val), bool):
                if val:
                    val = "1"
                else:
                    continue
            if val is None:
                val = "0"
                log(f"[ShaderPreprocessor] Value of shader argument {arg} is None!", severity=logging.WARN)
            if val.lower() == "false":
                # Don't define  defines which are set to false
                continue
            if val.lower() == "true":
                val = "1"
            # Support choices as an enum
            arg_choices = arg_templates[arg].choices
            if arg_choices is not None:
                # Add the choices to the defines
                for c in arg_choices:
                    if c not in global_choices:
                        global_choices[c] = str(len(global_choices))
                        defines.append((c, global_choices[c]))
                val = global_choices[val]

            name = f"T_{(arg[1:] if arg[0] == '_' else arg).upper()}"
            defines.append((name, val))
            if arg_templates[arg].default == val:
                defines.append((f"{name}_ISDEFAULT", "1"))

        defines.append(("SSV_SHADER", "1"))
        defines.append(("_GL_VERSION", f"#version {self._gl_version}"))
        if compiler_extensions is not None and len(compiler_extensions) > 0:
            defines.append(("_GL_ADDITIONAL_EXTENSIONS",
                            "\n".join(f"#extension {ext} : require" for ext in compiler_extensions)))
        if extra_defines is not None and len(extra_defines) > 0:
            for define, value in extra_defines.items():
                defines.append((define, value))
        for define, value in self._global_defines.items():
            defines.append((define, value))
        if self._supports_line_directives:
            defines.append(("_GL_SUPPORTS_LINE_DIRECTIVES", "1"))

        defines.append(("_DYNAMIC_UNIFORMS", "\n".join(self._dynamic_uniforms.values())))

        return defines

    def _find_shader_template(self, template_name, additional_template_directory, additional_templates):
        """
        Searches for a shader template given its name.

        :param template_name: the name of the template to look for.
        :param additional_template_directory: a path to a directory containing custom shader templates.
        :param additional_templates: a list of custom shader templates (source code, not paths).
        :return: (the template's filepath, the contents of the template)
        """
        # Find the relevant template
        template_source = None
        template_path = None
        template_expected_filename = f"template_{template_name.lower()}.glsl"

        # Check the additional_templates first
        if additional_templates is not None:
            for template in additional_templates:
                template_metadata = self._template_parser.parse(template, "additional_templates[]")
                for pragma in template_metadata["define"]:
                    if pragma.name.lower() == template_name.lower():
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
                if sys.version_info >= (3, 9):
                    template_traversable = files("pySSV.shaders").joinpath(template_expected_filename)
                    template_source = template_traversable.read_text()
                else:
                    template_source = read_text("pySSV.shaders", template_expected_filename)
                template_path = template_expected_filename
            except Exception as e:
                raise FileNotFoundError(f"Couldn't find/read a shader template called '{template_name}', "
                                        f"it should be in a file called '{template_expected_filename}'. \n"
                                        f"Inner exception: {e}")

        return template_path, template_source

    def preprocess(self, source: str, filepath: Optional[str] = None,
                   additional_template_directory: Optional[str] = None,
                   additional_templates: Optional[List[str]] = None,
                   shader_defines: Optional[Dict[str, str]] = None,
                   compiler_extensions: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Preprocesses an SSV shader into multiple processed shaders for each pipeline.

        :param source: the shader source code to preprocess. It should contain the necessary
                       ``#pragma SSV <template_name>`` directive see :ref:`built-in-shader-templates` for more
                       information.
        :param filepath: the filepath of the shader, used to help the preprocessor give more meaningful error messages.
        :param additional_template_directory: a path to a directory containing custom shader templates. See
                                              :ref:`writing-shader-templates` for information about using custom shader
                                              templates.
        :param additional_templates: a list of custom shader templates (source code, not paths). See
                                     :ref:`writing-shader-templates` for information about using custom shader
                                     templates.
        :param shader_defines: extra preprocessor defines to be enabled globally.
        :param compiler_extensions: a list of GLSL extensions required by this shader
                                    (eg: ``GL_EXT_control_flow_attributes``)
        :return: a dict of compiled shaders for each of the required pipeline stages.
        """
        template_info = self._shader_parser.parse(source, filepath)

        # Find the template file from its name
        template_path, template_source = self._find_shader_template(template_info.template,
                                                                    additional_template_directory, additional_templates)

        # Parse template args
        template_metadata = self._template_parser.parse(template_source, template_path)

        # Construct and argparse using the template metadata
        template_argparse = self._make_argparse(template_metadata)
        # Parse the template_info
        parsed_args = template_argparse.parse_args(template_info.args)
        defines = self._make_defines(parsed_args, template_metadata.get("arg", []), shader_defines, compiler_extensions)

        stages: List[str] = []
        for template_data in template_metadata.get("stage", []):
            if template_data.shader_stage is not None:
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
        primitive_type = None
        for p in template_metadata.get("input_primitive", []):
            primitive_type = p.primitive_type
        if primitive_type is not None:
            compiled_shaders["primitive_type"] = primitive_type
        return compiled_shaders

    def dbg_query_shader_templates(self,
                                   additional_template_directory: Optional[str] = None) -> List[SSVTemplatePragmaData]:
        """
        Gets a list of all the shader templates available to the preprocessor.

        :param additional_template_directory: a path to a directory containing custom shader templates.
        :return: A list of shader template metadata definitions.
        """
        templates = []
        # Check the additional_templates_directory
        if additional_template_directory is not None:
            if os.path.isdir(additional_template_directory):
                for file_name in os.listdir(additional_template_directory):
                    short_name = os.path.basename(file_name).lower()
                    if short_name.startswith("template_") and short_name.endswith(".glsl"):
                        try:
                            with open(file_name, "r") as f:
                                templates.append(f.read())
                        except Exception as e:
                            raise IOError(f"Couldn't read shader template '{file_name}' in additional template "
                                          f"directory! \n"
                                          f"Inner exception: {e}")
            else:
                raise NotADirectoryError(
                    f"Additional template directory is not a valid directory: {additional_template_directory}")

        # Then, check the built-in shaders
        try:
            if sys.version_info >= (3, 9):
                template_traversables = [f for f in files("pySSV.shaders").iterdir()
                                         if os.path.basename(f.name).startswith("template_")]
                for t in template_traversables:
                    templates.append(t.read_text())
            else:
                resources = [f for f in contents("pySSV.shaders") if os.path.basename(f).startswith("template_")]
                templates.extend([read_text("pySSV.shaders", res) for res in resources])
        except Exception as e:
            raise IOError(f"Couldn't read a built in shader template. \n"
                          f"Inner exception: {e}")

        # Now parse the template metadata
        metadata: List[Optional[SSVTemplatePragmaData]] = [
            self._template_parser.parse(template).get("define", [None])[0] for template in templates
        ]
        return [m for m in metadata if m is not None]

    def dbg_query_shader_template(self, template_name: str, additional_template_directory: Optional[str] = None,
                                  additional_templates: Optional[List[str]] = None) -> str:
        """
        Gets the list of arguments a given shader template expects and returns a string containing their usage info.

        :param template_name: the name of the template to look for.
        :param additional_template_directory: a path to a directory containing custom shader templates.
        :param additional_templates: a list of custom shader templates (source code, not paths).
        :return: the shader template's auto generated help string.
        """
        # Find the template file from its name
        template_path, template_source = self._find_shader_template(template_name, additional_template_directory,
                                                                    additional_templates)

        # Parse template args
        template_metadata = self._template_parser.parse(template_source, template_path)

        # Construct and argparse using the template metadata
        template_argparse = self._make_argparse(template_metadata)
        # Get help string
        return template_argparse.format_help()

    def add_dynamic_uniform(self, name: str, glsl_type: str):
        """
        Adds a uniform declaration to _DYNAMIC_UNIFORMS macro.

        :param name: the name of the uniform to add. Must be a valid GLSL identifier.
        :param glsl_type: the glsl type of the uniform.
        """
        self._dynamic_uniforms[name] = f"uniform {glsl_type} {name};"

    def remove_dynamic_uniform(self, name: str):
        """
        Removes a uniform declaration from the dynamic uniforms.

        :param name: the name of the uniform to remove.
        """
        del self._dynamic_uniforms[name]
