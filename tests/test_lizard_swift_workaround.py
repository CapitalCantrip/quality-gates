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

PACKAGE_SETTER = """\
class C {
    package(set) var x = 0
    init() {}
    func g() {}
}
"""

COMMENT_BEFORE_SETTER = """\
class C {
    private /* why */ (set) var z = 0
    init() {}
    func g() {}
}
"""

WRAPPED_SETTER = """\
class C {
    private(
        set) var q = 0
    init() {}
    func g(_ a: Int) {
        if a > 1 { return }
    }
}
"""

DOT_INIT_WITH_SET_ARGUMENT = """\
struct Foo { init(_ v: Int) {} }
struct S {
    let x: Foo = .init(set)
    func g(_ a: Int) -> Int {
        if a > 1 { return 1 }
        if a > 2 { return 2 }
        return 0
    }
}
"""

SELF_INIT_WITH_SET_ARGUMENT = """\
class B {
    init(_ v: Int) {}
    convenience init(set: Int, flag: Bool) {
        if flag { print(1) }
        self.init(set)
    }
    func g(_ a: Int) -> Int {
        if a > 1 { return 1 }
        return 0
    }
}
"""

CALL_WITH_SET_ARGUMENT = """\
class C {
    func g(_ set: Int) -> Int {
        let t = foo(set)
        if t > 5 { return 1 }
        return t
    }
    func h() {}
}
"""

INIT_CALL_IN_BODY = """\
struct S {
    func g(_ set: Int) -> Int {
        let x = Foo.init(set)
        if x.ok { return 1 }
        return 0
    }
    func h() {}
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

    def test_package_set_opens_no_setter_and_swallows_nothing(self):
        self.assertEqual(lizard_rows(PACKAGE_SETTER), [("init", 1, 3, 3), ("g", 1, 4, 4)])

    def test_a_comment_between_the_modifier_and_set_opens_no_setter_and_swallows_nothing(self):
        self.assertEqual(lizard_rows(COMMENT_BEFORE_SETTER), [("init", 1, 3, 3), ("g", 1, 4, 4)])

    def test_a_line_break_inside_the_parens_opens_no_setter_and_swallows_nothing(self):
        rows = lizard_rows(WRAPPED_SETTER)
        self.assertEqual([name for name, _, _, _ in rows], ["init", "g"])

    def test_line_numbers_after_a_wrapped_setter_access_match_lizard_master(self):
        self.assertEqual(lizard_rows(WRAPPED_SETTER), [("init", 1, 4, 4), ("g", 2, 5, 7)])

    def test_set_passed_to_dot_init_keeps_the_init_call_as_lizard_master_reads_it(self):
        self.assertEqual(lizard_rows(DOT_INIT_WITH_SET_ARGUMENT), [("init", 1, 1, 1), ("init", 3, 3, 8)])

    def test_set_passed_to_self_init_matches_lizard_master_including_its_known_gap(self):
        self.assertEqual(
            lizard_rows(SELF_INIT_WITH_SET_ARGUMENT),
            [("init", 1, 2, 2), ("init", 2, 5, 10), ("init", 2, 3, 11)],
        )

    def test_a_local_named_set_passed_to_a_call_scores_the_enclosing_function_as_lizard_master_does(self):
        self.assertEqual(lizard_rows(CALL_WITH_SET_ARGUMENT), [("g", 2, 2, 6), ("h", 1, 7, 7)])

    def test_set_passed_to_init_inside_a_function_body_matches_lizard_master_including_its_known_gap(self):
        self.assertEqual(
            lizard_rows(INIT_CALL_IN_BODY),
            [("init", 2, 3, 4), ("g", 1, 2, 6), ("h", 1, 7, 7)],
        )


if __name__ == "__main__":
    unittest.main()
