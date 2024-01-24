#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from typing import Any, List

import pcpp  # type: ignore


class SSVShaderArgsTokenizer:
    @staticmethod
    def correct_tokens(tokens: List[Any], preprocessor: pcpp.Preprocessor):
        """
        This method takes a list of PCPP LexTokens and converts them to a list of arguments for argparse.

        This method handles string un-escaping and whitespace stripping.

        :param tokens: the list of PCPP tokens to parse.
        :param preprocessor: the preprocessor used to generate the tokens.
        :return: a list of arguments.
        """
        ret = []
        combined_tok = []
        tokens_iter = iter(tokens)
        for tok in tokens_iter:
            if tok.type == preprocessor.t_STRING:
                unescaped = []
                str_iter = iter(tok.value[1:-1])
                for c in str_iter:
                    if c == "\\":
                        # Check the next character
                        escaped = next(str_iter, None)
                        if escaped == '"':
                            unescaped.append('"')
                        elif escaped == "n":
                            unescaped.append("\n")
                        elif escaped == "t":
                            unescaped.append("\t")
                        elif escaped is None:
                            unescaped.append(c)
                        else:
                            # Ignore invalid escape sequences
                            unescaped.append(c)
                            unescaped.append(escaped)
                    else:
                        # Normal character
                        unescaped.append(c)

                combined_tok.append(''.join(unescaped))
            elif tok.type in preprocessor.t_WS:
                if len(combined_tok) > 0:
                    ret.append("".join(combined_tok))
                    combined_tok.clear()
            else:
                combined_tok.append(tok.value)
        if len(combined_tok) > 0:
            ret.append("".join(combined_tok))
        return ret
