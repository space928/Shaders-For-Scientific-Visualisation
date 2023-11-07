#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import sys
import pcpp
import argparse

from .ssv_logging import log


class ShaderPreprocessor(pcpp.Preprocessor):
    """

    """
    def __init__(self):
        super(ShaderPreprocessor, self).__init__()
        # Define any built in macros/includes

        # Pragma parser
        self.pragma_parse = argparse.ArgumentParser(prog="SSV Shader Preprocessor")
        sub_parsers = self.pragma_parse.add_subparsers(help="template generation command help", dest="command")
        pixel_parser = sub_parsers.add_parser("pixel", help="define the entrypoint for a pixel shader")
        pixel_parser.add_argument("function", type=str)
        vertex_parser = sub_parsers.add_parser("vertex", help="define the entrypoint for a vertex shader")
        vertex_parser.add_argument("function", type=str)
        sdf_parser = sub_parsers.add_parser("sdf", help="define the entrypoint for an sdf shader")
        sdf_parser.add_argument("function", type=str)
        sdf_parser.add_argument("--sdf_normal", type=str)
        sdf_parser.add_argument("--display_mode", choices=["solid", "xray", "isolines", "2d"])
        sdf_parser.add_argument("--surface_offset", type=str)
        self.pragma_args = []

    def on_directive_unknown(self, directive, toks, ifpassthru, precedingtoks):
        if directive.value != "pragma":
            return super(ShaderPreprocessor, self).on_directive_unknown(directive, toks, ifpassthru, precedingtoks)

        if not (len(toks) > 2 and toks[0].value == "SSV"):
            return super(ShaderPreprocessor, self).on_directive_unknown(directive, toks, ifpassthru, precedingtoks)

        tok_strs = [t.value for t in toks[2:]]
        # print(f"Found SSV pragma: {''.join(tok_strs)}")
        self.pragma_args.append(''.join(tok_strs))

    def write(self, oh=sys.stdout):
        # Prefixed template code

        # Output the preprocessed code
        super(ShaderPreprocessor, self).write(oh)
        # Suffixed template code

        print("\n############\n")
        print("Found following SSV pragmas: ")
        for pragma in self.pragma_args:
            args = self.pragma_parse.parse_args(pragma.split())
            print("\t", args)
