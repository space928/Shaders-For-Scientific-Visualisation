#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import sys
from typing import Union

import pcpp
import argparse

from .ssv_logging import log
from .ssv_shader_args_tokenizer import SSVShaderArgsTokenizer


class SSVTemplatePragmaData(argparse.Namespace):
    command: str = None
    # Define/Arg
    name: str = None
    author: str = None
    description: str = None
    # Stage
    shader_stage: list[str] = None
    # Arg
    # name: str = None
    non_positional: bool = False
    action: str = None
    default: str = None
    choices: list[str] = None
    const: str = None
    # description: list[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class SSVShaderPragmaData(argparse.Namespace):
    template: str = None
    args: list[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class SSVTemplatePragmaParser(pcpp.Preprocessor):
    """
    This class is responsible for parsing #pragma definitions in SSV shader templates.

    Refer to :ref:`writing-shader-templates` for details on writing shader templates.
    """

    def __init__(self):
        super(SSVTemplatePragmaParser, self).__init__()
        # Template pragma parser
        self._pragma_parse = argparse.ArgumentParser(prog="SSV Shader Preprocessor")
        sub_parsers = self._pragma_parse.add_subparsers(dest="command")
        define_parser = sub_parsers.add_parser("define", help="Defines a new SSV shader template")
        define_parser.add_argument("name", type=str,
                                   help="The name the shader template. The template's filename should be in the form: "
                                        "'template_<name>.glsl'.")
        define_parser.add_argument("--author", "-a", type=str,
                                   help="The shader template's author.")
        define_parser.add_argument("--description", "-d", type=str,
                                   help="A brief description of the shader template and what it does.")
        stage_parser = sub_parsers.add_parser("stage",
                                              help="Specifies a shader stage to compile this template for")
        stage_parser.add_argument("shader_stage",
                                  choices=["vertex", "fragment", "tess_control", "tess_evaluation", "geometry",
                                           "compute"],
                                  nargs="+")
        arg_parser = sub_parsers.add_parser("arg",
                                            help="Defines an argument to be passed into this shader template when "
                                                 "evaluating it. Arguments are passed into the shader as compiler "
                                                 "defines; the names of the arguments are transformed to uppercase and "
                                                 "prefixed with 'T_'")
        arg_parser.add_argument("name", type=str,
                                help="The name of the argument to be passed in to the shader; prefixing the name with "
                                     "an underscore implies the '--non_positional' flag")
        arg_parser.add_argument("--non_positional", "-n", action="store_true",
                                help="Treat this as a non-positional argument; it's name is automatically prefixed "
                                     "with '--'")
        # arg_parser.add_argument("--type", "-t", type=str, help="")
        arg_parser.add_argument("--action", "-a", default="store",
                                choices=["store", "store_const", "store_true", "store_false"],
                                help="What to do when this argument is encountered. See the argparse docs for details "
                                     "on the different actions: "
                                     "https://docs.python.org/3.11/library/argparse.html#action")
        arg_parser.add_argument("--default", type=str,
                                help="The default value for this argument if it isn't specified")
        arg_parser.add_argument("--choices", "-c", type=str, nargs="+", action="extend",
                                help="Limits the valid values of this argument to those specified here")
        arg_parser.add_argument("--const", type=str,
                                help="When using the 'store_const' action, specifies what value to store")
        arg_parser.add_argument("--description", "-d",
                                help="A brief description of the argument and the value it expects. Note that for "
                                     "implementation reasons the description can't contain dashes.")

        self._pragma_args = []

    def on_include_not_found(self, is_malformed, is_system_include, curdir, includepath):
        """
        *Used internally by the parser.*
        """
        raise pcpp.OutputDirective(pcpp.Action.IgnoreAndPassThrough)

    def on_error(self, file, line, msg):
        """
        *Used internally by the parser.*
        """
        log(f"[{file}:{line}] {msg}")
        raise ValueError(f"[{file}:{line}] {msg}")

    def on_directive_unknown(self, directive, toks, ifpassthru, precedingtoks):
        """
        *Used internally by the parser.*
        """
        if directive.value != "pragma" or len(toks) <= 2:
            return super(SSVTemplatePragmaParser, self).on_directive_unknown(directive, toks, ifpassthru, precedingtoks)

        if toks[0].value == "SSVTemplate":
            # print(f"Found SSV pragma: {SSVShaderArgsTokenizer.correct_tokens(toks[2:], self)}")
            self._pragma_args.append(SSVShaderArgsTokenizer.correct_tokens(toks[2:], self))
        # else:
        #     log(f"[{directive.source}:{directive.lineno}] Unrecognised #pragma directive: {''.join(toks)}",
        #         severity=logging.DEBUG)

        return True

    def parse(self, input, source=None, ignore=None) -> dict[str, list[SSVTemplatePragmaData]]:
        """
        Parses the #pragma directives of a shader template.

        :param input: the source of the shader template.
        :param source: the path to the source file.
        :param ignore:
        :return: a dictionary of parsed shader template commands.
        """
        if ignore is None:
            ignore = {}

        self._pragma_args = []

        # Set up the parser
        super(SSVTemplatePragmaParser, self).parse(input, source, ignore)

        # Parse all tokens
        while self.token():
            pass

        args = [self._pragma_parse.parse_args(args, namespace=SSVTemplatePragmaData())
                for args in self._pragma_args]

        # Group arguments into a dictionary
        args_dict = {}
        for arg in args:
            if arg.command in args_dict:
                args_dict[arg.command].append(arg)
            else:
                args_dict[arg.command] = [arg]

        return args_dict

    def write(self, oh=sys.stdout):
        """
        The pragma parser only parses #pragma arguments, it should not be used to preprocess shader files.

        :param oh: unused
        """
        raise NotImplementedError("The SSV pragma parser is strictly read only.")


class SSVShaderPragmaParser(pcpp.Preprocessor):
    """
    This class is responsible for parsing #pragma definitions in SSV shaders.
    """

    def __init__(self):
        super(SSVShaderPragmaParser, self).__init__()
        # Template pragma parser
        self._pragma_parse = argparse.ArgumentParser(prog="SSV Shader Preprocessor", prefix_chars="`")
        self._pragma_parse.add_argument("template", type=str)
        self._pragma_parse.add_argument("args", type=str, nargs="*")

        self._pragma_args = None

    def on_directive_unknown(self, directive, toks, ifpassthru, precedingtoks):
        """
        *Used internally by the parser.*
        """
        if directive.value != "pragma" or len(toks) <= 2:
            return super(SSVShaderPragmaParser, self).on_directive_unknown(directive, toks, ifpassthru, precedingtoks)

        if toks[0].value == "SSV":
            # log(f"Found SSV pragma: {''.join(tok_strs)}")
            if self._pragma_args is not None:
                raise ValueError("Shader contains multiple shader template pragma directives! Only one is allowed.")
            self._pragma_args = SSVShaderArgsTokenizer.correct_tokens(toks[2:], self)
        # else:
        #     log(f"[{directive.source}:{directive.lineno}] Unrecognised #pragma directive: {''.join([t.value for t in toks])}",
        #         severity=logging.DEBUG)

        return True

    def parse(self, input, source=None, ignore=None) -> SSVShaderPragmaData:
        """
        Parses the #pragma directives of a shader.

        :param input: the source of the shader.
        :param source: the path to the source file.
        :param ignore:
        :return: an object of parsed shader template info.
        """
        if ignore is None:
            ignore = {}

        self._pragma_args = None

        # Set up the parser
        super(SSVShaderPragmaParser, self).parse(input, source, ignore)

        # Parse all tokens
        while self.token():
            pass

        if self._pragma_args is None:
            raise ValueError(
                "Shader does not use a shader template! Did you remember to add #pragma SSV [...] to your shader?")

        return self._pragma_parse.parse_args(self._pragma_args, namespace=SSVShaderPragmaData())

    def write(self, oh=sys.stdout):
        """
        The pragma parser only parses #pragma arguments, it should not be used to preprocess shader files.

        :param oh: unused
        """
        raise NotImplementedError("The SSV pragma parser is strictly read only.")
