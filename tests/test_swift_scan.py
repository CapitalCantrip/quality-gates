import os
import tempfile
import unittest
from pathlib import Path

from quality_gates import complexity_scan

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

SUPER_INIT_WITH_SET_ARGUMENT = """\
class A {
    init(_ v: Int) {}
}
class B: A {
    init(set: Int, flag: Bool) {
        if flag { print(1) }
        super.init(set)
    }
    func g(_ a: Int) -> Int {
        if a > 1 { return 1 }
        return 0
    }
}
"""

PROPERTY_NAMED_SET_USED_AS_ARGUMENT = """\
struct S {
    static let set = 1
    let t = max(set, 2)
    init?(v: Int) {
        if v > 1 { return nil }
    }
    func g() {}
}
"""

CALL_WITH_SET_AT_TYPE_SCOPE = """\
struct S {
    let t = f(set)
    init?(v: Int) {
        if v > 1 { return nil }
    }
}
"""


def lizard_rows(text: str) -> list:
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "App.swift").write_text(text, encoding="utf-8")
        here = os.getcwd()
        os.chdir(folder)
        try:
            found = complexity_scan.scan(["App.swift"], "swift")
        finally:
            os.chdir(here)
    return [(fn.name, fn.cc, fn.start, fn.end) for fn in found.functions]


class SwiftScanTest(unittest.TestCase):
    def test_failable_init_question_and_bang_are_scored_as_init(self):
        self.assertEqual(lizard_rows(FAILABLE_INITS), [("init", 2, 2, 4), ("init#2", 3, 5, 8)])

    def test_set_inside_an_access_modifier_opens_no_setter_and_swallows_nothing(self):
        self.assertEqual(lizard_rows(SETTER_ACCESS), [("init", 1, 7, 7), ("g", 1, 8, 8)])

    def test_package_set_opens_no_setter_and_swallows_nothing(self):
        self.assertEqual(lizard_rows(PACKAGE_SETTER), [("init", 1, 3, 3), ("g", 1, 4, 4)])

    def test_a_comment_between_the_modifier_and_set_opens_no_setter_and_swallows_nothing(self):
        self.assertEqual(lizard_rows(COMMENT_BEFORE_SETTER), [("init", 1, 3, 3), ("g", 1, 4, 4)])

    def test_a_line_break_inside_the_parens_keeps_the_line_numbers_that_follow(self):
        self.assertEqual(lizard_rows(WRAPPED_SETTER), [("init", 1, 4, 4), ("g", 2, 5, 7)])

    def test_set_passed_to_dot_init_opens_no_function_and_the_next_function_is_scored(self):
        self.assertEqual(lizard_rows(DOT_INIT_WITH_SET_ARGUMENT), [("init", 1, 1, 1), ("g", 3, 4, 8)])

    def test_set_passed_to_self_init_leaves_the_convenience_init_and_the_next_function_scored(self):
        self.assertEqual(
            lizard_rows(SELF_INIT_WITH_SET_ARGUMENT),
            [("init", 1, 2, 2), ("init#2", 2, 3, 6), ("g", 2, 7, 10)],
        )

    def test_a_local_named_set_passed_to_a_call_scores_the_enclosing_function(self):
        self.assertEqual(lizard_rows(CALL_WITH_SET_ARGUMENT), [("g", 2, 2, 6), ("h", 1, 7, 7)])

    def test_set_passed_to_init_inside_a_function_body_opens_no_function(self):
        self.assertEqual(lizard_rows(INIT_CALL_IN_BODY), [("g", 2, 2, 6), ("h", 1, 7, 7)])

    def test_set_passed_to_super_init_leaves_the_init_and_the_next_function_scored(self):
        self.assertEqual(
            lizard_rows(SUPER_INIT_WITH_SET_ARGUMENT),
            [("init", 1, 2, 2), ("init#2", 2, 5, 8), ("g", 2, 9, 12)],
        )

    def test_a_property_named_set_used_as_an_argument_opens_no_set_function(self):
        self.assertEqual(lizard_rows(PROPERTY_NAMED_SET_USED_AS_ARGUMENT), [("init", 2, 4, 6), ("g", 1, 7, 7)])

    def test_set_passed_to_a_call_at_type_scope_leaves_the_next_failable_init_scored(self):
        self.assertEqual(lizard_rows(CALL_WITH_SET_AT_TYPE_SCOPE), [("init", 2, 3, 5)])


if __name__ == "__main__":
    unittest.main()
