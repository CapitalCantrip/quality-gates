import unittest

from quality_gates import code_reader
from quality_gates.code_reader import Comment, Syntax

SLASHES = Syntax(line=("//",))


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


if __name__ == "__main__":
    unittest.main()
