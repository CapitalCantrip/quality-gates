import unittest

from quality_gates import code_reader
from quality_gates.code_reader import Balanced, Comment, Interpolation, Literal, Syntax
from quality_gates.comment_debt import RUST

SLASHES = Syntax(line=("//",))
C_LIKE = Syntax(line=("//",), block=(("/*", "*/"),))
NESTING = Syntax(line=("//",), block=(("/*", "*/"),), nested=True)
QUOTED = Syntax(line=("//",), block=(("/*", "*/"),),
                literals=(Literal('"', r'"(?:\\[\s\S]|[^"\\])*"'), Literal("'", r"'[^'\n]'")))
TEMPLATE_PIECE = r"(?:\\[\s\S]|\$(?!\{)|[^`\\$])*(?:`|\$\{)"
TEMPLATED = Syntax(line=("//",), block=(("/*", "*/"),),
                   literals=(Literal("'", r"'[^'\n]*'"),
                             Literal("`", "`" + TEMPLATE_PIECE, Interpolation(("{", "}"), TEMPLATE_PIECE))))
DOUBLE_PARENS = Syntax(line=("#",), literals=(Literal(r"\(\(", r"\(\(", balanced=Balanced(("(", ")"), "))")),))
BODIED = Syntax(line=("#",), literals=(Literal("<<", r"<<(\w+)", body=r"(?:[^\n]*\n)*?\g<1>(?=\n|\Z)"),))


class ReadingLineComments(unittest.TestCase):

    def test_a_line_comment_is_found_with_its_kind_text_and_lines(self):
        reading = code_reader.read("fn main() {\n    // a comment\n}\n", SLASHES)
        self.assertEqual(reading.comments, (Comment("line", "// a comment", 2, 2),))

    def test_a_trailing_comment_starts_at_its_marker(self):
        reading = code_reader.read("let x = 1; // why\n", SLASHES)
        self.assertEqual(reading.comments, (Comment("line", "// why", 1, 1),))

    def test_code_with_no_marker_has_no_comments_and_reads_back_unchanged(self):
        source = "fn main() {\n    let x = 1;\n}\n"
        reading = code_reader.read(source, SLASHES)
        self.assertEqual((reading.comments, reading.blanked), ((), source))

    def test_the_blanked_copy_keeps_every_line_and_blanks_each_comment(self):
        reading = code_reader.read("let x = 1; // why\r\n// all\nx\n", SLASHES)
        self.assertEqual(reading.blanked, "let x = 1;       \r\n      \nx\n")

    def test_only_a_newline_ends_a_line_so_other_line_breaks_keep_the_line_numbers(self):
        for separator in ("\x0c", "\x0b", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)):
                source = f"let a = 1;{separator}\n// why\n"
                reading = code_reader.read(source, SLASHES)
                self.assertEqual(reading.comments, (Comment("line", "// why", 2, 2),))
                self.assertEqual(reading.blanked, f"let a = 1;{separator}\n      \n")


class ReadingBlockComments(unittest.TestCase):

    def test_a_block_comment_is_found_with_its_whole_text_and_its_first_and_last_lines(self):
        reading = code_reader.read("x\n/* one\n   two */ y\n", C_LIKE)
        self.assertEqual(reading.comments, (Comment("block", "/* one\n   two */", 2, 3),))
        self.assertEqual(reading.blanked, "x\n      \n          y\n")

    def test_a_block_comment_that_never_closes_runs_to_the_end_of_the_file(self):
        reading = code_reader.read("x\n/* open\n", C_LIKE)
        self.assertEqual(reading.comments, (Comment("block", "/* open\n", 2, 3),))

    def test_a_nested_block_comment_ends_only_where_its_outer_comment_closes(self):
        reading = code_reader.read("/* a /* b */ c */ x // y\n", NESTING)
        self.assertEqual([c.text for c in reading.comments], ["/* a /* b */ c */", "// y"])

    def test_without_nesting_a_block_comment_ends_at_the_first_close(self):
        reading = code_reader.read("/* a /* b */ c\n", C_LIKE)
        self.assertEqual(reading.comments, (Comment("block", "/* a /* b */", 1, 1),))


class ReadingDocComments(unittest.TestCase):

    def test_a_comment_starting_with_a_doc_pattern_is_a_doc_comment_and_any_other_keeps_its_kind(self):
        syntax = Syntax(line=("//",), block=(("/*", "*/"),), doc=(r"///(?!/)", r"/\*\*(?![*/])"))
        reading = code_reader.read("/// a\n//// b\n/** c */\n/**/\n", syntax)
        self.assertEqual([(c.kind, c.text) for c in reading.comments],
                         [("doc", "/// a"), ("line", "//// b"), ("doc", "/** c */"), ("block", "/**/")])


class ReadingLiterals(unittest.TestCase):

    def test_a_marker_inside_a_literal_is_not_a_comment_and_the_literal_is_blanked(self):
        reading = code_reader.read('let s = "a // b /* c"; // why\n', QUOTED)
        self.assertEqual(reading.comments, (Comment("line", "// why", 1, 1),))
        self.assertEqual(reading.blanked, "let s =              ;       \n")

    def test_a_literal_over_several_lines_keeps_the_line_numbers_of_what_follows(self):
        reading = code_reader.read('let s = "one\r\ntwo";\n// why\n', QUOTED)
        self.assertEqual(reading.comments, (Comment("line", "// why", 3, 3),))
        self.assertEqual(reading.blanked, "let s =     \r\n    ;\n      \n")

    def test_an_opening_that_does_not_complete_its_literal_is_read_as_code(self):
        reading = code_reader.read("fn f<'a>(x: &'a str) {} // why\n", QUOTED)
        self.assertEqual(reading.comments, (Comment("line", "// why", 1, 1),))
        self.assertEqual(reading.blanked, "fn f<'a>(x: &'a str) {}       \n")


class ReadingInterpolatedLiterals(unittest.TestCase):

    def test_the_code_inside_an_interpolation_is_read_as_code_and_the_literal_around_it_is_blanked(self):
        reading = code_reader.read("x = `a // ${ f({k: '}'}) /* why */ } b // ${`c`}` // end\n", TEMPLATED)
        self.assertEqual([c.text for c in reading.comments], ["/* why */", "// end"])
        self.assertEqual(reading.blanked, "x =          f({k:    })                                \n")

    def test_a_bracket_outside_any_interpolation_is_code(self):
        reading = code_reader.read("f({}) } // why\n", TEMPLATED)
        self.assertEqual(reading.comments, (Comment("line", "// why", 1, 1),))

    def test_an_interpolation_that_never_closes_leaves_the_rest_of_the_file_as_code(self):
        reading = code_reader.read("x = `a ${ b\n// why\n", TEMPLATED)
        self.assertEqual(reading.comments, (Comment("line", "// why", 2, 2),))
        self.assertEqual(reading.blanked, "x =       b\n      \n")


class ReadingBalancedLiterals(unittest.TestCase):

    def test_a_balanced_literal_ends_where_its_brackets_balance_however_deep_they_nest(self):
        reading = code_reader.read("x=$(( (1 + (2 * (3 # y))) )) # why\n", DOUBLE_PARENS)
        self.assertEqual(reading.comments, (Comment("line", "# why", 1, 1),))
        self.assertEqual(reading.blanked, "x=$" + " " * 25 + "      \n")

    def test_brackets_that_balance_without_the_closing_mark_are_read_as_code(self):
        reading = code_reader.read("((cd a) # x\n) # why\n", DOUBLE_PARENS)
        self.assertEqual([c.text for c in reading.comments], ["# x", "# why"])

    def test_brackets_that_never_balance_are_read_as_code(self):
        reading = code_reader.read("(( a # why\n", DOUBLE_PARENS)
        self.assertEqual(reading.comments, (Comment("line", "# why", 1, 1),))


class ReadingLiteralsWithABodyOnTheLinesBelow(unittest.TestCase):

    def test_the_rest_of_the_opening_line_is_read_as_code_and_the_body_below_is_blanked(self):
        reading = code_reader.read("cat <<END # why\n# body\nEND\n# after\n", BODIED)
        self.assertEqual([(c.text, c.start) for c in reading.comments], [("# why", 1), ("# after", 4)])
        self.assertEqual(reading.blanked, "cat" + " " * 12 + "\n      \n   \n       \n")

    def test_bodies_opened_on_one_line_follow_one_another_in_the_order_they_were_opened(self):
        reading = code_reader.read("cmd <<A <<B\n# a\nA\n# b\nB\n# after\n", BODIED)
        self.assertEqual([(c.text, c.start) for c in reading.comments], [("# after", 6)])

    def test_a_body_starts_after_the_lines_its_opening_line_joins_with_a_backslash(self):
        reading = code_reader.read("cat <<END \\\n  # why\n# body\nEND\n", BODIED)
        self.assertEqual([(c.text, c.start) for c in reading.comments], [("# why", 2)])

    def test_a_line_comment_ends_the_opening_line_even_when_it_ends_in_a_backslash(self):
        reading = code_reader.read("cat <<END # C:\\\n# body\nEND\n# after\n", BODIED)
        self.assertEqual([(c.text, c.start) for c in reading.comments], [("# C:\\", 1), ("# after", 4)])

    def test_a_body_that_never_ends_leaves_its_opening_as_code(self):
        reading = code_reader.read("cat <<END\n# why\n", BODIED)
        self.assertEqual(reading.comments, (Comment("line", "# why", 2, 2),))
        self.assertEqual(reading.blanked, "cat <<END\n     \n")


RUST_SOURCE = (
    "//! Crate.\n"
    "fn f<'a>(s: &'a str) -> char { // why\n"
    "    let url = \"https://x/y\"; let raw = r#\"a \"//\" b\"#;\n"
    "    /* one\n"
    "       two */ let c = ['\\x7f', '\\u{1F600}', '\"'];\n"
    "    let multi = \"first\n"
    "second\";\n"
    "}\n"
)
RUST_BLANKED = (
    "          \n"
    "fn f<'a>(s: &'a str) -> char {       \n"
    "    let url =              ; let raw =              ;\n"
    "          \n"
    "              let c = [      ,            ,    ];\n"
    "    let multi =       \n"
    "       ;\n"
    "}\n"
)


class ReadingOneRustFile(unittest.TestCase):

    def test_the_blanked_copy_keeps_every_line_and_blanks_each_string_and_comment(self):
        reading = code_reader.read(RUST_SOURCE, RUST.syntax)
        self.assertEqual(reading.blanked, RUST_BLANKED)
        self.assertEqual(reading.blanked.count("\n"), RUST_SOURCE.count("\n"))
        self.assertEqual([(c.kind, c.start, c.end) for c in reading.comments],
                         [("doc", 1, 1), ("line", 2, 2), ("block", 4, 5)])


if __name__ == "__main__":
    unittest.main()
