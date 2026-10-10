import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quality_gates.errors import ToolError
from quality_gates.json_report import load_json


class LoadJsonTest(unittest.TestCase):
    def load(self, content=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            if content is not None:
                path.write_bytes(content)
            return load_json(str(path), "widget file", "widget JSON")

    def test_a_valid_file_is_returned_as_parsed_json(self):
        self.assertEqual(self.load(b'{"files": [1, 2]}'), {"files": [1, 2]})

    def test_a_missing_file_is_a_tool_error_naming_the_reader(self):
        with self.assertRaises(ToolError) as raised:
            self.load()
        self.assertTrue(str(raised.exception).startswith("cannot open widget file: [Errno 2]"))

    def test_a_file_that_is_not_utf8_is_a_tool_error_naming_the_reader(self):
        with self.assertRaises(ToolError) as raised:
            self.load(b"\xff\xfe\x00binary")
        self.assertTrue(str(raised.exception).startswith("bad widget JSON: "))

    def test_malformed_json_is_a_tool_error_naming_the_reader(self):
        with self.assertRaises(ToolError) as raised:
            self.load(b"{not json")
        self.assertTrue(str(raised.exception).startswith("bad widget JSON: Expecting property name"))

    def test_json_nested_too_deeply_to_parse_is_a_tool_error_naming_the_reader(self):
        with self.assertRaises(ToolError) as raised:
            self.load(b"[" * 200000)
        self.assertTrue(str(raised.exception).startswith("bad widget JSON: "))

    def test_a_number_the_parser_refuses_is_a_tool_error_naming_the_reader(self):
        with patch("quality_gates.json_report.json.load", side_effect=ValueError("Exceeds the limit")):
            with self.assertRaises(ToolError) as raised:
                self.load(b"1")
        self.assertEqual(str(raised.exception), "bad widget JSON: Exceeds the limit")


if __name__ == "__main__":
    unittest.main()
