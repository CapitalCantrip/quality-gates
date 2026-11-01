import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import explain, manifest  # noqa: E402

PACKAGE = Path(__file__).resolve().parents[1] / "src/quality_gates"
COMPONENTS = manifest.load_components()
SECTIONS = ["What it catches", "Why it matters", "What it asks of you", "Want to go deeper?"]
LINK = re.compile(r"^- \[[^\]]+\]\(https://[^)\s]+\): .+ Checked (\d{4}-\d{2}-\d{2})\.$")


def explainers():
    for component in COMPONENTS.components:
        if component.explainer is not None:
            yield component, (PACKAGE / component.explainer).read_text(encoding="utf-8")


def sections(text):
    return re.findall(r"^## (.+)$", text, re.MULTILINE)


def links(text):
    return [line for line in text.split("\n## Want to go deeper?\n", 1)[1].splitlines() if line.startswith("- ")]


class ExplainerFormat(unittest.TestCase):
    def test_the_crap_component_has_an_explainer_as_the_worked_example(self):
        crap = next(c for c in COMPONENTS.components if c.id == "crap")
        self.assertIsNotNone(crap.explainer)

    def test_an_explainer_opens_with_the_name_of_its_component(self):
        for component, text in explainers():
            self.assertEqual(text.splitlines()[0], f"# {component.name}", component.id)

    def test_an_explainer_has_its_four_sections_in_order(self):
        for component, text in explainers():
            self.assertEqual(sections(text), SECTIONS, component.id)

    def test_an_explainer_gives_one_to_three_outside_links_under_want_to_go_deeper(self):
        for component, text in explainers():
            self.assertGreaterEqual(len(links(text)), 1, component.id)
            self.assertLessEqual(len(links(text)), 3, component.id)

    def test_every_link_says_why_it_is_worth_the_time_and_the_date_it_was_checked(self):
        for component, text in explainers():
            for line in links(text):
                match = LINK.match(line)
                self.assertIsNotNone(match, line)
                date.fromisoformat(match.group(1))


def run(entry, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = entry(argv)
        except SystemExit as stop:
            code = stop.code
    return code, out.getvalue(), err.getvalue()


def manifest_of(**changes):
    component = {"id": "demo", "name": "Demo", "description": "A demo component.", "core": False, "languages": [],
                 "origin": {"type": "ours"}, "parts": []}
    return {"format_version": 2, "admissions": [], "components": [dict(component, **changes)]}


def manifest_in(folder, data):
    path = Path(folder) / "fixture.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class ExplainCommand(unittest.TestCase):
    def test_explain_prints_the_explainer_the_manifest_names_for_the_component(self):
        code, out, err = run(explain.main, ["crap"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, (PACKAGE / "explainers/crap.md").read_text(encoding="utf-8"))

    def test_an_unknown_component_name_stops_with_exit_1_naming_it(self):
        code, out, err = run(explain.main, ["bogus"])
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err, "qg explain: no component named 'bogus'\n")

    def test_a_component_with_no_explainer_yet_stops_with_exit_1_naming_it(self):
        with tempfile.TemporaryDirectory() as folder:
            entry = partial(explain.main, components_path=manifest_in(folder, manifest_of()))
            code, out, err = run(entry, ["demo"])
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err, "qg explain: 'demo' has no explainer yet\n")

    def test_an_explainer_file_that_is_missing_stops_with_exit_3_naming_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            entry = partial(explain.main, components_path=manifest_in(folder, manifest_of(explainer="explainers/demo.md")))
            code, out, err = run(entry, ["demo"])
        self.assertEqual((code, out), (3, ""))
        self.assertIn("demo.md", err)

    def test_a_manifest_that_does_not_load_stops_with_exit_3_naming_the_problem(self):
        with tempfile.TemporaryDirectory() as folder:
            entry = partial(explain.main, components_path=manifest_in(folder, {"format_version": 2, "admissions": []}))
            code, out, err = run(entry, ["demo"])
        self.assertEqual((code, out), (3, ""))
        self.assertEqual(err, "qg explain: fixture.json: missing field 'components'\n")

    def test_a_missing_name_stops_with_usage_and_exit_2(self):
        code, out, err = run(explain.main, [])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("the following arguments are required: name", err)

    def test_explain_help_shows_its_usage(self):
        code, out, _ = run(explain.main, ["--help"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("usage: qg explain [-h] name\n"))


if __name__ == "__main__":
    unittest.main()
