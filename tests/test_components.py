import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/quality_gates"
SKILLS = PACKAGE / "skills"
MANIFEST = json.loads((PACKAGE / "components.json").read_text(encoding="utf-8"))
UPSTREAM = json.loads((PACKAGE / "upstream.json").read_text(encoding="utf-8"))
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

PART_KINDS = {"skill", "hook", "baseline", "ci_step", "claude_md_line", "command", "dependency"}
ORIGIN_TYPES = {"ours", "upstream", "dependency"}
UPSTREAM_LABELS = {"mattpocock/skills": "Pocock"}
SKILLS_PREFIX = "src/quality_gates/skills/"


def parts(kind=None):
    for component in MANIFEST["components"]:
        for part in component["parts"]:
            if kind is None or part["kind"] == kind:
                yield component, part


def origin_of(component, part):
    return part.get("origin", component["origin"])


def shipped_skills():
    return sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))


def upstream_repos_by_skill():
    found = {}
    for source in UPSTREAM["sources"]:
        for local in source["files"].values():
            if local.startswith(SKILLS_PREFIX):
                found.setdefault(local[len(SKILLS_PREFIX):].split("/")[0], set()).add(source["repo"])
    return found


def skill_md_is_adapted(skill):
    local = f"{SKILLS_PREFIX}{skill}/SKILL.md"
    return any(local in source["files"].values() and source["copied"].startswith("adapted") for source in UPSTREAM["sources"])


def readme_from_column():
    skills_section = README.split("\n## Skills\n", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `/?([\w-]+)` \| ([^|]+?) \|", skills_section, re.MULTILINE)
    return dict(rows), [name for name, _ in rows]


def expected_from_label(component, part):
    origin = origin_of(component, part)
    if origin["type"] == "ours":
        return "ours"
    label = UPSTREAM_LABELS[origin["name"]]
    return f"{label}, changed" if origin.get("changed") else label


class ComponentManifest(unittest.TestCase):
    def test_the_manifest_carries_a_format_version(self):
        self.assertIsInstance(MANIFEST.get("format_version"), int)

    def test_every_shipped_skill_is_in_exactly_one_component(self):
        listed = Counter(part["id"] for _, part in parts("skill"))
        self.assertEqual({skill: listed.get(skill, 0) for skill in shipped_skills()}, {skill: 1 for skill in shipped_skills()})

    def test_every_skill_a_component_names_ships(self):
        self.assertEqual(sorted(part["id"] for _, part in parts("skill")), shipped_skills())

    def test_every_hook_a_component_names_ships(self):
        for _, part in parts("hook"):
            self.assertTrue((PACKAGE / "hooks" / part["id"]).is_file(), part["id"])

    def test_every_command_a_component_names_is_installed_by_the_package(self):
        for _, part in parts("command"):
            self.assertRegex(PYPROJECT, rf'(?m)^{re.escape(part["id"])} = "quality_gates\.', part["id"])

    def test_every_dependency_a_component_names_is_a_requirement_at_the_stated_version(self):
        for _, part in parts("dependency"):
            self.assertIn(f'"{part["id"]}{part["origin"]["version"]}"', PYPROJECT, part["id"])
            self.assertEqual(part["origin"]["name"], part["id"])

    def test_every_ci_step_a_component_names_is_in_the_ci_file_it_points_to(self):
        for _, part in parts("ci_step"):
            self.assertIn(part["id"], (SKILLS / part["file"].split("skills/", 1)[1]).read_text(encoding="utf-8"), part["id"])

    def test_every_baseline_a_component_names_is_named_by_a_shipped_skill(self):
        skill_text = " ".join(path.read_text(encoding="utf-8") for path in SKILLS.glob("*/SKILL.md"))
        for _, part in parts("baseline"):
            self.assertIn(part["id"], skill_text, part["id"])

    def test_every_part_has_a_known_kind_and_every_origin_a_known_type(self):
        for component, part in parts():
            self.assertIn(part["kind"], PART_KINDS, part)
            self.assertIn(origin_of(component, part)["type"], ORIGIN_TYPES, part)

    def test_a_component_has_a_unique_id_a_plain_description_and_a_core_flag(self):
        ids = [component["id"] for component in MANIFEST["components"]]
        self.assertEqual(len(ids), len(set(ids)))
        for component in MANIFEST["components"]:
            self.assertIsInstance(component["core"], bool, component["id"])
            self.assertIsInstance(component["languages"], list, component["id"])
            self.assertRegex(component["description"], r"^[^\n]+\.$", component["id"])

    def test_only_the_core_component_is_core(self):
        self.assertEqual([c["id"] for c in MANIFEST["components"] if c["core"]], ["core"])

    def test_a_component_has_the_origin_most_of_its_parts_have(self):
        for component in MANIFEST["components"]:
            counts = Counter((o["type"], o.get("name")) for o in (origin_of(component, p) for p in component["parts"]))
            (top, top_count), *rest = counts.most_common()
            self.assertTrue(not rest or rest[0][1] < top_count, component["id"])
            self.assertEqual((component["origin"]["type"], component["origin"].get("name")), top, component["id"])


class ComponentManifestAgreesWithTheUpstreamRecord(unittest.TestCase):
    def test_a_skill_has_upstream_files_exactly_when_the_manifest_says_it_comes_from_or_adapts_that_upstream(self):
        recorded = upstream_repos_by_skill()
        for component, part in parts("skill"):
            origin = origin_of(component, part)
            named = set(origin.get("adapts", []))
            if origin["type"] == "upstream":
                named.add(origin["name"])
            self.assertEqual(recorded.get(part["id"], set()), named, part["id"])

    def test_an_upstream_skill_is_marked_changed_exactly_when_its_skill_file_is_adapted(self):
        for component, part in parts("skill"):
            origin = origin_of(component, part)
            if origin["type"] == "upstream":
                self.assertEqual(bool(origin.get("changed")), skill_md_is_adapted(part["id"]), part["id"])


class ComponentManifestAgreesWithTheReadme(unittest.TestCase):
    def test_the_readme_from_column_agrees_with_the_manifest_for_every_skill(self):
        from_column, _ = readme_from_column()
        expected = {part["id"]: expected_from_label(component, part) for component, part in parts("skill")}
        self.assertEqual(from_column, expected)

    def test_the_readme_lists_every_shipped_skill_once(self):
        _, names = readme_from_column()
        self.assertEqual(sorted(names), shipped_skills())


class ComponentManifestShips(unittest.TestCase):
    def test_the_manifest_is_listed_in_the_package_data(self):
        package_data = re.search(r"(?m)^quality_gates = \[(.*)\]$", PYPROJECT).group(1)
        self.assertIn('"components.json"', package_data)


if __name__ == "__main__":
    unittest.main()
