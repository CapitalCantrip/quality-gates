import sys

import lizard
import lizard_languages
from lizard_languages.swift import SwiftReader as LizardSwiftReader

FAILABLE_INITS = {"init?": "init", "init!": "init"}
SETTER_SCOPE = ["(", "set", ")"]
INITIALISER = "init"
COMMENT_STARTS = ("//", "/*")


def _is_significant(token: str) -> bool:
    return bool(token.strip()) and not token.startswith(COMMENT_STARTS)


def _is_setter_scope(out: list, significant: list) -> bool:
    words = [out[index] for index in significant[-4:]]
    return words[-3:] == SETTER_SCOPE and words[:-3] != [INITIALISER]


def rewritten(tokens) -> list:
    out = []
    significant = []
    for token in tokens:
        out.append(FAILABLE_INITS.get(token, token))
        if _is_significant(token):
            significant.append(len(out) - 1)
        if token == ")" and _is_setter_scope(out, significant):
            for index in reversed(significant[-3:]):
                del out[index]
            del significant[-3:]
    return out


class SwiftReader(LizardSwiftReader):
    def preprocess(self, tokens):
        return rewritten(super().preprocess(tokens))


def main(argv=None) -> int:
    lizard_languages.SwiftReader = SwiftReader
    return lizard.main(argv or sys.argv)


if __name__ == "__main__":
    sys.exit(main())
