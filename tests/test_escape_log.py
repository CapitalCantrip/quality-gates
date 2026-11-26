import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "agents" / "escape-log.md"
COMMAND = re.compile(r"^gh issue list .*--jq '(.*)'$", re.MULTILINE)
HEADING = "## Which gate should have caught it (comment-debt, cc-check, crap, or none could)"


def body(kind, newline="\n"):
    lines = ["## What happened", "", "It broke.", "", "## How it was found (using the product, a review, a crash, other)",
             "", "a crash", "", HEADING, "", kind, ""]
    return newline.join(lines)


@unittest.skipUnless(shutil.which("jq"), "jq is not installed")
class EscapeCount(unittest.TestCase):
    def count(self, bodies):
        filter_text = COMMAND.search(DOC.read_text()).group(1)
        issues = json.dumps([{"body": text} for text in bodies])
        result = subprocess.run(["jq", "-r", filter_text], input=issues, capture_output=True, text=True, check=True)
        return result.stdout.splitlines()

    def test_the_routine_prints_zero_when_nothing_has_escaped(self):
        self.assertEqual(self.count([]), ["escapes: 0"])

    def test_the_routine_prints_the_total_and_a_count_for_each_kind(self):
        bodies = [body("comment-debt"), body("none could"), body("comment-debt"), body("crap")]
        self.assertEqual(self.count(bodies), ["escapes: 4", "comment-debt: 2", "crap: 1", "none could: 1"])

    def test_a_body_with_windows_line_endings_counts_under_its_kind(self):
        self.assertEqual(self.count([body("crap", "\r\n"), body("crap")]), ["escapes: 2", "crap: 2"])

    def test_the_kind_ignores_case_and_trailing_spaces(self):
        self.assertEqual(self.count([body("None could  "), body("none could")]), ["escapes: 2", "none could: 2"])

    def test_an_issue_without_the_third_answer_counts_as_unanswered(self):
        bodies = ["Found it by hand.", "## What happened\n\nx\n\n" + HEADING + "\n"]
        self.assertEqual(self.count(bodies), ["escapes: 2", "unanswered: 2"])


if __name__ == "__main__":
    unittest.main()
