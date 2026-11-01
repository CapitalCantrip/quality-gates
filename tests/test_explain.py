import re
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import manifest  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
