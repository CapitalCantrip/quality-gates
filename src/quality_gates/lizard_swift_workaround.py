import sys

import lizard
import lizard_languages
from lizard_languages.swift import SwiftReader as LizardSwiftReader

FAILABLE_INITS = {"init?": "init", "init!": "init"}
SETTER_SCOPE = ["(", "set", ")"]
COMMENT_STARTS = ("//", "/*")


def _is_significant(token: str) -> bool:
    return bool(token.strip()) and not token.startswith(COMMENT_STARTS)


def _last_significant(tokens: list, count: int) -> list:
    found = []
    for index in range(len(tokens) - 1, -1, -1):
        if _is_significant(tokens[index]):
            found.append(index)
            if len(found) == count:
                break
    return found[::-1]


def _setter_scope_indexes(tokens: list) -> list:
    indexes = _last_significant(tokens, len(SETTER_SCOPE))
    if [tokens[index] for index in indexes] == SETTER_SCOPE:
        return indexes
    return []


def rewritten(tokens) -> list:
    out = []
    for token in tokens:
        out.append(FAILABLE_INITS.get(token, token))
        if token == ")":
            for index in reversed(_setter_scope_indexes(out)):
                del out[index]
    return out


class SwiftReader(LizardSwiftReader):
    def preprocess(self, tokens):
        return rewritten(super().preprocess(tokens))


def main(argv=None) -> int:
    lizard_languages.SwiftReader = SwiftReader
    return lizard.main(argv or sys.argv)


if __name__ == "__main__":
    sys.exit(main())
