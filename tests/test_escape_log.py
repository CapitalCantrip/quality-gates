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
PATTERN = re.compile(r'counts\("((?:[^"\\]|\\.)*)"\)')
GO_MATCHER = """package main

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
)

func main() {
	re := regexp.MustCompile(os.Args[1])
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
STAGE_HEADING = "## Earliest point it could have been stopped (idea, spec, module map, ticket brief, build, review, gate)"


def documented_command():
    return COMMAND_LINE.search(DOC.read_text()).group(0)


def documented_filter():
    return FILTER.search(documented_command()).group(1)


def body(gate, newline="\n", stage="build"):
    lines = ["## What happened", "", "It broke.", "", "## How it was found (using the product, a review, a crash, other)",
             "", "a crash", "", STAGE_HEADING, "", stage, "", HEADING, "", gate, ""]
    return newline.join(lines)


def report(total, stages, gates):
    return [f"escapes: {total}", "by stage:", *[f"  {line}" for line in stages], "by gate:", *[f"  {line}" for line in gates]]


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

    def test_the_routine_prints_the_total_and_a_count_for_each_stage_and_each_gate(self):
        bodies = [body("comment-debt", stage="spec"), body("none could", stage="build"), body("comment-debt", stage="build"),
                  body("crap", stage="review")]
        self.assertEqual(self.count(bodies), report(4, ["build: 2", "review: 1", "spec: 1"],
                                                    ["comment-debt: 2", "crap: 1", "none could: 1"]))

    def test_a_body_with_windows_line_endings_counts_under_its_stage_and_gate(self):
        self.assertEqual(self.count([body("crap", "\r\n", "spec"), body("crap", stage="spec")]),
                         report(2, ["spec: 2"], ["crap: 2"]))

    def test_the_stage_and_the_gate_ignore_case_and_trailing_spaces(self):
        self.assertEqual(self.count([body("None could  ", stage="Ticket Brief "), body("none could", stage="ticket brief")]),
                         report(2, ["ticket brief: 2"], ["none could: 2"]))

    def test_a_body_that_starts_at_the_stage_heading_counts_under_its_stage(self):
        self.assertEqual(self.count([STAGE_HEADING + "\n\nspec\n\n" + HEADING + "\n\ncrap\n"]),
                         report(1, ["spec: 1"], ["crap: 1"]))

    def test_a_body_that_starts_at_the_gate_heading_counts_under_its_gate(self):
        self.assertEqual(self.count([HEADING + "\n\ncrap\n"]), report(1, ["unanswered: 1"], ["crap: 1"]))

    def test_an_empty_stage_answer_followed_by_the_gate_heading_counts_as_unanswered_and_keeps_the_gate(self):
        bodies = ["## What happened\n\nx\n\n" + STAGE_HEADING + "\n\n" + HEADING + "\n\ncrap\n"]
        self.assertEqual(self.count(bodies), report(1, ["unanswered: 1"], ["crap: 1"]))

    def test_an_empty_gate_answer_followed_by_another_heading_counts_as_unanswered(self):
        bodies = ["## What happened\n\nx\n\n" + HEADING + "\n\n## Notes\n\nsee above\n"]
        self.assertEqual(self.count(bodies), report(1, ["unanswered: 1"], ["unanswered: 1"]))

    def test_an_issue_filed_under_the_three_question_template_counts_its_gate_and_no_stage(self):
        bodies = ["## What happened\n\nx\n\n## Which gate should have caught it (crap)\n\ncrap\n"]
        self.assertEqual(self.count(bodies), report(1, ["unanswered: 1"], ["crap: 1"]))

    def test_an_issue_with_neither_answer_counts_as_unanswered_for_both(self):
        bodies = ["Found it by hand.", "## What happened\n\nx\n\n" + STAGE_HEADING + "\n" + HEADING + "\n"]
        self.assertEqual(self.count(bodies), report(2, ["unanswered: 2"], ["unanswered: 2"]))


@unittest.skipUnless(shutil.which("go"), "go is not installed")
class GoRegularExpressions(unittest.TestCase):
    def matched(self, pattern, bodies):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "matcher.go").write_text(GO_MATCHER)
            ran = subprocess.run(["go", "run", "matcher.go", pattern, json.dumps(bodies)], cwd=folder,
                                 capture_output=True, text=True, check=True)
        return json.loads(ran.stdout)

    def patterns(self):
        return [json.loads('"' + found + '"') for found in PATTERN.findall(documented_filter())]

    def test_the_filter_has_one_pattern_for_the_stage_and_one_for_the_gate(self):
        stage, gate = self.patterns()
        self.assertIn("## Earliest point it could have been stopped", stage)
        self.assertIn("## Which gate should have caught it", gate)

    def test_the_stage_pattern_matches_the_same_answers_under_the_go_engine_gh_uses(self):
        stage, _ = self.patterns()
        bodies = [body("crap", stage="spec"), body("crap", "\r\n", "spec"), STAGE_HEADING + "\n\nspec\n", "Found it by hand.",
                  "x\n\n" + STAGE_HEADING + "\n\n" + HEADING + "\n"]
        self.assertEqual(self.matched(stage, bodies), ["spec", "spec", "spec", "", HEADING])

    def test_the_gate_pattern_matches_the_same_answers_under_the_go_engine_gh_uses(self):
        _, gate = self.patterns()
        bodies = [body("crap"), body("crap", "\r\n"), HEADING + "\n\ncrap\n", "Found it by hand.",
                  "x\n\n" + HEADING + "\n\n## Notes\n"]
        self.assertEqual(self.matched(gate, bodies), ["crap", "crap", "crap", "", "## Notes"])


if __name__ == "__main__":
    unittest.main()
