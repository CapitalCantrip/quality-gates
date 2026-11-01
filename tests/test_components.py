import re
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import manifest  # noqa: E402
from quality_gates import quality_check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/quality_gates"
SKILLS = PACKAGE / "skills"
MANIFEST = manifest.load_components()
SOURCES = manifest.load_sources()
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

COMMENT_DEBT_LANGUAGES = {"python"}
HOOK_SECTION = "\n## 4. Hooks\n"
UPSTREAM_LABELS = {"mattpocock/skills": "Pocock"}
SKILLS_PREFIX = "src/quality_gates/skills/"


def admissions_of(kind):
    return {a.name: a for a in MANIFEST.admissions if a.kind == kind}


def version_tuple(version):
    return tuple(int(number) for number in version.split("."))


def pyproject_requirements():
    listed = re.search(r"(?m)^dependencies = \[(.*)\]$", PYPROJECT).group(1)
    return dict(re.findall(r'"([\w-]+)>=([\d.]+)"', listed))


def parts(kind=None):
    for component in MANIFEST.components:
        for part in component.parts:
            if kind is None or part.kind == kind:
                yield component, part


def languages_of(component, part):
    return component.languages if part.languages is None else part.languages


def shipped_skills():
    return sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))


def upstream_repos_by_skill():
    found = {}
    for source in SOURCES:
        for local in source.files.values():
            if local.startswith(SKILLS_PREFIX):
                found.setdefault(local[len(SKILLS_PREFIX):].split("/")[0], set()).add(source.repo)
    return found


def skill_md_is_adapted(skill):
    local = f"{SKILLS_PREFIX}{skill}/SKILL.md"
    return any(local in source.files.values() and source.copied.startswith("adapted") for source in SOURCES)


def readme_from_column():
    skills_section = README.split("\n## Skills\n", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `/?([\w-]+)` \| ([^|]+?) \|", skills_section, re.MULTILINE)
    return dict(rows), [name for name, _ in rows]


def origin_of(component, part):
    return part.origin or component.origin


def expected_from_label(component, part):
    origin = origin_of(component, part)
    if origin.type == "ours":
        return "ours"
    label = UPSTREAM_LABELS[origin.name]
    return f"{label}, changed" if origin.changed else label


class ComponentManifest(unittest.TestCase):
    def test_every_shipped_skill_is_in_exactly_one_component(self):
        listed = Counter(part.id for _, part in parts("skill"))
        self.assertEqual({skill: listed.get(skill, 0) for skill in shipped_skills()}, {skill: 1 for skill in shipped_skills()})

    def test_every_skill_a_component_names_ships(self):
        self.assertEqual(sorted(part.id for _, part in parts("skill")), shipped_skills())

    def test_every_hook_a_component_names_ships(self):
        for _, part in parts("hook"):
            self.assertTrue((PACKAGE / "hooks" / part.id).is_file(), part.id)

    def test_every_command_a_component_names_is_installed_by_the_package(self):
        for _, part in parts("command"):
            self.assertRegex(PYPROJECT, rf'(?m)^{re.escape(part.id)} = "quality_gates\.', part.id)

    def test_every_dependency_a_component_names_is_a_requirement_at_the_stated_version(self):
        for _, part in parts("dependency"):
            self.assertIn(f'"{part.id}{part.origin.version}"', PYPROJECT, part.id)
            self.assertEqual(part.origin.name, part.id)

    def test_every_ci_step_marker_appears_in_the_ci_example_it_points_to(self):
        for _, part in parts("ci_step"):
            self.assertIn(part.marker, (SKILLS / part.file.split("skills/", 1)[1]).read_text(encoding="utf-8"), part.id)

    def test_a_ci_step_marker_is_a_line_the_example_puts_in_a_workflow_or_in_the_file_it_names(self):
        for _, part in parts("ci_step"):
            example = (SKILLS / part.file.split("skills/", 1)[1]).read_text(encoding="utf-8")
            if part.found_in is not None:
                self.assertIn(f"Save as `{part.found_in}`", example, part.id)
            else:
                runs = [line for line in example.splitlines() if part.marker in line]
                self.assertTrue(any(re.match(r"^\s*(- run: )?" + re.escape(part.marker), line) for line in runs), part.id)

    def test_a_part_names_only_languages_its_component_has(self):
        for component, part in parts():
            self.assertLessEqual(set(part.languages or ()), set(component.languages), part.id)

    def test_every_language_a_component_has_gets_a_ci_step(self):
        for component in MANIFEST.components:
            steps = [part for part in component.parts if part.kind == "ci_step"]
            covered = {language for part in steps for language in languages_of(component, part)}
            self.assertEqual(covered, set(component.languages), component.id)

    def test_every_baseline_and_config_file_a_component_names_is_named_by_a_shipped_skill(self):
        skill_text = " ".join(path.read_text(encoding="utf-8") for path in SKILLS.glob("*/SKILL.md"))
        for kind in ("baseline", "config"):
            for _, part in parts(kind):
                self.assertIn(part.id, skill_text, part.id)

    def test_every_precommit_step_marker_is_in_the_hook_step_of_the_setup_guide(self):
        guide = (SKILLS / "setup-standards" / "SKILL.md").read_text(encoding="utf-8")
        hook_step = guide.split(HOOK_SECTION, 1)[1].split("\n## ", 1)[0]
        for _, part in parts("precommit_step"):
            self.assertIn(f"`{part.marker}", hook_step, part.id)

    def test_every_language_a_fast_gate_component_has_gets_a_precommit_step(self):
        for component in MANIFEST.components:
            steps = [part for part in component.parts if part.kind == "precommit_step"]
            covered = {language for part in steps for language in languages_of(component, part)}
            self.assertTrue(not steps or covered == set(component.languages), component.id)

    def test_a_component_names_cc_check_only_for_languages_cc_check_counts(self):
        for component, _ in (pair for pair in parts("command") if pair[1].id == "cc-check"):
            self.assertLessEqual(set(component.languages), set(quality_check.LANGUAGES), component.id)

    def test_the_comment_gate_names_only_the_languages_comment_debt_reads(self):
        for component, _ in (pair for pair in parts("command") if pair[1].id == "comment-debt"):
            self.assertEqual(set(component.languages), COMMENT_DEBT_LANGUAGES, component.id)

    def test_the_swift_and_rust_complexity_gates_list_their_lint_config_and_ci_step(self):
        for component_id, config in (("complexity-swift", ".swiftlint.yml"), ("complexity-rust", "clippy.toml")):
            component = next(c for c in MANIFEST.components if c.id == component_id)
            kinds = {(part.kind, part.id) for part in component.parts}
            self.assertIn(("config", config), kinds, component_id)
            self.assertTrue(any(kind == "ci_step" for kind, _ in kinds), component_id)

    def test_only_the_core_component_is_core(self):
        self.assertEqual([c.id for c in MANIFEST.components if c.core], ["core"])

    def test_a_component_has_the_origin_most_of_its_parts_have(self):
        for component in MANIFEST.components:
            counts = Counter((o.type, o.name) for o in (origin_of(component, p) for p in component.parts))
            (top, top_count), *rest = counts.most_common()
            self.assertTrue(not rest or rest[0][1] < top_count, component.id)
            self.assertEqual((component.origin.type, component.origin.name), top, component.id)


class ComponentManifestAgreesWithTheUpstreamRecord(unittest.TestCase):
    def test_a_skill_has_upstream_files_exactly_when_the_manifest_says_it_comes_from_or_adapts_that_upstream(self):
        recorded = upstream_repos_by_skill()
        for component, part in parts("skill"):
            origin = origin_of(component, part)
            named = set(origin.adapts or ())
            if origin.type == "upstream":
                named.add(origin.name)
            self.assertEqual(recorded.get(part.id, set()), named, part.id)

    def test_an_upstream_skill_is_marked_changed_exactly_when_its_skill_file_is_adapted(self):
        for component, part in parts("skill"):
            origin = origin_of(component, part)
            if origin.type == "upstream":
                self.assertEqual(bool(origin.changed), skill_md_is_adapted(part.id), part.id)


class AdmissionsAgreeWithWhatShips(unittest.TestCase):
    def test_every_source_in_the_upstream_record_has_an_upstream_admission(self):
        upstreams = admissions_of("upstream")
        for source in SOURCES:
            self.assertIn(source.repo, upstreams)

    def test_every_upstream_admission_is_a_source_in_the_upstream_record(self):
        self.assertEqual(set(admissions_of("upstream")), {source.repo for source in SOURCES})

    def test_every_python_requirement_of_the_package_has_a_dependency_admission_at_the_same_minimum(self):
        dependencies = admissions_of("dependency")
        requirements = pyproject_requirements()
        self.assertEqual(sorted(requirements), sorted(dependencies))
        for name, minimum in requirements.items():
            self.assertEqual(dependencies[name].minimum_version, minimum, name)

    def test_the_version_ci_tested_is_at_or_above_the_minimum_for_every_dependency(self):
        for name, admission in admissions_of("dependency").items():
            self.assertGreaterEqual(version_tuple(admission.tested_version), version_tuple(admission.minimum_version), name)

    def test_a_dependency_part_states_the_minimum_its_admission_records(self):
        dependencies = admissions_of("dependency")
        for _, part in parts("dependency"):
            self.assertEqual(part.origin.version, f">={dependencies[part.origin.name].minimum_version}", part.id)

    def test_every_test_only_tool_has_a_licence_and_no_part_installs_it(self):
        named = {origin_of(c, p).name for c, p in parts()}
        for name, admission in admissions_of("test-only").items():
            self.assertTrue(admission.licence, name)
            self.assertNotIn(name, named)


class ComponentManifestAgreesWithTheReadme(unittest.TestCase):
    def test_the_readme_from_column_agrees_with_the_manifest_for_every_skill(self):
        from_column, _ = readme_from_column()
        expected = {part.id: expected_from_label(component, part) for component, part in parts("skill")}
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
