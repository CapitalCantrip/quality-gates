import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "agents" / "escape-log.md"
COMMAND_LINE = re.compile(r"^gh issue list .*--jq '.*'$", re.MULTILINE)
FILTER = re.compile(r"--jq '(.*)'$")
PATTERN = re.compile(r'capture\("((?:[^"\\]|\\.)*)"\)')
GO_MATCHER = """package main

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"strings"
)

func main() {
	re := regexp.MustCompile(strings.ReplaceAll(os.Args[1], "(?<", "(?P<"))
	var bodies []string
	json.Unmarshal([]byte(os.Args[2]), &bodies)
	var kinds []string
	for _, body := range bodies {
		found := re.FindStringSubmatch(body)
		kind := ""
		if found != nil {
			kind = found[re.SubexpIndex("kind")]
		}
		kinds = append(kinds, kind)
	}
	out, _ := json.Marshal(kinds)
	fmt.Println(string(out))
}
"""
HEADING = "## Which gate should have caught it (comment-debt, cc-check, crap, or none could)"


def documented_command():
    return COMMAND_LINE.search(DOC.read_text()).group(0)


def documented_filter():
    return FILTER.search(documented_command()).group(1)


def body(kind, newline="\n"):
    lines = ["## What happened", "", "It broke.", "", "## How it was found (using the product, a review, a crash, other)",
             "", "a crash", "", HEADING, "", kind, ""]
    return newline.join(lines)


class DocumentedCommand(unittest.TestCase):
    def test_the_command_lists_every_escape_open_or_closed_and_the_doc_names_the_cap(self):
        command = documented_command()
        self.assertIn("gh issue list --label escaped --state all --limit 1000 --json body --jq", command)
        self.assertIn("`--limit 1000`", DOC.read_text())


@unittest.skipUnless(shutil.which("jq"), "jq is not installed")
class EscapeCount(unittest.TestCase):
    def count(self, bodies):
        filter_text = documented_filter()
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

    def test_a_body_that_starts_at_the_heading_counts_under_its_kind(self):
        self.assertEqual(self.count([HEADING + "\n\ncrap\n"]), ["escapes: 1", "crap: 1"])

    def test_an_empty_answer_followed_by_another_heading_counts_as_unanswered(self):
        bodies = ["## What happened\n\nx\n\n" + HEADING + "\n\n## Notes\n\nsee above\n"]
        self.assertEqual(self.count(bodies), ["escapes: 1", "unanswered: 1"])

    def test_an_issue_without_the_third_answer_counts_as_unanswered(self):
        bodies = ["Found it by hand.", "## What happened\n\nx\n\n" + HEADING + "\n"]
        self.assertEqual(self.count(bodies), ["escapes: 2", "unanswered: 2"])


@unittest.skipUnless(shutil.which("go"), "go is not installed")
class GoRegularExpressions(unittest.TestCase):
    def test_the_pattern_matches_the_same_answers_under_the_go_engine_gh_uses(self):
        pattern = json.loads('"' + PATTERN.search(documented_filter()).group(1) + '"')
        bodies = [body("crap"), body("crap", "\r\n"), HEADING + "\n\ncrap\n", "Found it by hand.",
                  "x\n\n" + HEADING + "\n\n## Notes\n"]
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "matcher.go").write_text(GO_MATCHER)
            ran = subprocess.run(["go", "run", "matcher.go", pattern, json.dumps(bodies)], cwd=folder,
                                 capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(ran.stdout), ["crap", "crap", "crap", "", "## Notes"])


if __name__ == "__main__":
    unittest.main()
