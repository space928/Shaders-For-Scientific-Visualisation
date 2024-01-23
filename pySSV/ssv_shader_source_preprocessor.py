#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import io
import logging
import os.path
from importlib.resources import as_file, files
import pcpp

from .ssv_logging import log


class SSVShaderSourcePreprocessor(pcpp.Preprocessor):
    """
    This class is responsible for the actual preprocessing of the shader template. It extends the ``pcpp.Preprocessor``
    to add functionality needed to support our custom #include and #pragma directives.
    """

    def __init__(self, shader_source):
        super().__init__()
        self.shader_source = shader_source
        self.will_enable_line_directive = False

    def on_file_open(self, is_system_include, includepath):
        """
        *Used internally by the parser.*

        :meta private:
        """
        if os.path.isfile(includepath):
            return super().on_file_open(is_system_include, includepath)

        filename = os.path.basename(includepath)
        if filename == "TEMPLATE_DATA":
            return io.StringIO(self.shader_source)

        try:
            with as_file(files("pySSV.shaders").joinpath(filename)) as f:
                ret = f.open('r', encoding=self.assume_encoding)
                bom = ret.read(1)
                if bom != '\ufeff':
                    ret.seek(0)
                return ret
        except Exception as e:
            self.on_error(self.lastdirective.source, self.lastdirective.lineno,
                          f"Encountered exception while trying to open #include file: {includepath}\n"
                          f"Inner exception: {e}")
            raise pcpp.OutputDirective(pcpp.Action.IgnoreAndPassThrough)

    def on_directive_unknown(self, directive, toks, ifpassthru, precedingtoks):
        """
        *Used internally by the parser.*

        :meta private:
        """
        if directive.value == "pragma":
            # This is a special pragma directive which allows #line directives to be suppressed. This is needed to
            # ensure that the #line directive can appear first in the shader.
            if len(toks) >= 2 and toks[0].value == "PreventLine":
                if toks[2].value == "true":
                    self.will_enable_line_directive = -1
                    self.line_directive = None
                else:
                    # Because of how the preprocessor is designed, it's not guaranteed to have condensed the last chunk
                    # of tokens yet, so it might still try and generate a #line directive when they should be disabled.
                    # Hence, we deffer re-enabling the line directive until we're sure it's safe to do so.
                    self.will_enable_line_directive = directive.lineno
                    # self.line_directive = "#line"

            # Remove this directive from the output
            raise pcpp.OutputDirective(pcpp.Action.IgnoreAndRemove)
        if directive.value == "version":
            raise pcpp.OutputDirective(pcpp.Action.IgnoreAndPassThrough)
        super().on_directive_unknown(directive, toks, ifpassthru, precedingtoks)

    def token(self):
        """
        *Used internally by the parser.*

        :meta private:
        """
        tok = super().token()

        # Macro expansion happens when the chunk is collapsed, so it should be a good time to re-enable #line
        # directives if needed.
        if -1 < self.will_enable_line_directive <= tok.lineno:
            self.line_directive = "#line"
            self.will_enable_line_directive = -1

        return tok

    def on_comment(self, tok):
        """
        *Used internally by the parser.*

        :meta private:
        """
        # Remove any comments from templates, but keep user comments
        if tok.source == "TEMPLATE_DATA":
            return True
        else:
            return False

    def on_error(self, file, line, msg):
        """
        *Used internally by the parser.*

        :meta private:
        """
        log(f"[ShaderPreprocessor] [{file}:{line}] {msg}", severity=logging.ERROR)
        self.return_code += 1
