import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lizard_languages

from quality_gates import complexity_scan, lizard_swift_workaround

FAILABLE_INITS = """\
struct S {
    init?(text: String) {
        if text.isEmpty { return nil }
    }
    init!(code: Int) {
        if code < 0 { return nil }
        if code > 9 { return nil }
    }
}
"""

SETTER_ACCESS = """\
class C {
    private(set) var a = 0
    fileprivate(set) var b = 0
    internal(set) var c = 0
    public(set) var d = 0
    public private(set) var e = 0
    init() {}
    func g() {}
}
"""


def lizard_rows(text: str) -> list:
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder, "App.swift")
        source.write_text(text, encoding="utf-8")
        out = io.StringIO()
        with patch.object(lizard_languages, "SwiftReader", lizard_languages.SwiftReader):
            with contextlib.redirect_stdout(out):
                lizard_swift_workaround.main(["lizard", "-l", "swift", "--csv", str(source)])
    rows = csv.reader(io.StringIO(out.getvalue().strip()))
    return [(fn.name, fn.cc, fn.start, fn.end) for fn in map(complexity_scan.parse_row, rows) if fn]


class LizardSwiftWorkaroundTest(unittest.TestCase):
    def test_lizard_bug_516_failable_init_question_and_bang_tokens_are_scored_as_init(self):
        self.assertEqual(lizard_rows(FAILABLE_INITS), [("init", 2, 2, 4), ("init", 3, 5, 8)])

    def test_lizard_bug_516_set_inside_an_access_modifier_opens_no_setter_and_swallows_nothing(self):
        self.assertEqual(lizard_rows(SETTER_ACCESS), [("init", 1, 7, 7), ("g", 1, 8, 8)])


if __name__ == "__main__":
    unittest.main()
