import sys

import lizard
import lizard_languages
from lizard_languages.swift import SwiftReader as LizardSwiftReader

FAILABLE_INITS = {"init?": "init", "init!": "init"}
SETTER_ACCESS_MODIFIERS = ("private", "fileprivate", "internal", "public")
SETTER_SCOPE = ["(", "set", ")"]


def _ends_in_setter_access(tokens: list) -> bool:
    return tokens[-3:] == SETTER_SCOPE and len(tokens) > 3 and tokens[-4] in SETTER_ACCESS_MODIFIERS


def rewritten(tokens) -> list:
    out = []
    for token in tokens:
        out.append(FAILABLE_INITS.get(token, token))
        if _ends_in_setter_access(out):
            del out[-3:]
    return out


class SwiftReader(LizardSwiftReader):
    def preprocess(self, tokens):
        return rewritten(super().preprocess(tokens))


def main(argv=None) -> int:
    lizard_languages.SwiftReader = SwiftReader
    return lizard.main(argv or sys.argv)


if __name__ == "__main__":
    sys.exit(main())
