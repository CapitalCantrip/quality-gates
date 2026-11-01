import ast
import copy
import datetime
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import manifest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_FILES = ("components.json", "upstream.json")
RADON = {"name": "radon", "kind": "dependency", "licence": "MIT", "practice": "One maintainer who ships rarely.",
         "last_release": "2023-03-26", "minimum_version": "6", "tested_version": "6.0.1"}
SKILLS = {"name": "someone/skills", "kind": "upstream", "licence": "MIT", "practice": "Publishes skills he uses daily.",
          "last_release": "2026-10-29"}
RUFF = {"name": "ruff", "kind": "test-only", "licence": "GPL-3.0-only", "practice": "A funded team ships weekly.",
        "last_release": "2026-10-27"}
COMPONENTS = {
    "format_version": 2,
    "admissions": [RADON, SKILLS, RUFF],
    "components": [{
        "id": "risk",
        "name": "Risk gate",
        "description": "Flags tangled, untested code.",
        "core": False,
        "languages": ["python"],
        "origin": {"type": "ours"},
        "parts": [
            {"kind": "skill", "id": "crap"},
            {"kind": "ci_step", "id": "crap-python", "marker": "crap --lang python", "languages": ["python"]},
            {"kind": "dependency", "id": "radon", "origin": {"type": "dependency", "name": "radon"}},
        ],
    }],
}
SOURCES = {"sources": [{"repo": "someone/skills", "commit": "a" * 40, "copied": "verbatim",
                        "files": {"skills/domain.md": "src/domain.md"}}]}


def changed(data, edit):
    edited = copy.deepcopy(data)
    edit(edited)
    return edited


class ShippedManifest(unittest.TestCase):
    def test_the_shipped_components_load_as_records_with_parts_and_origins(self):
        loaded = manifest.load_components()
        core = next(c for c in loaded.components if c.id == "core")
        self.assertEqual(loaded.format_version, 2)
        self.assertTrue(core.core)
        self.assertEqual(core.origin.type, "upstream")
        self.assertIn(("skill", "tdd"), [(p.kind, p.id) for p in core.parts])

    def test_the_shipped_admissions_cover_every_source_in_use_and_every_test_only_tool(self):
        kinds = {a.name: a.kind for a in manifest.load_components().admissions}
        self.assertEqual(kinds, {"radon": "dependency", "lizard": "dependency", "mattpocock/skills": "upstream",
                                 "cursor/plugins": "upstream", "ruff": "test-only", "eslint": "test-only",
                                 "swiftlint": "test-only"})

    def test_the_shipped_upstream_record_loads_as_sources(self):
        sources = manifest.load_sources()
        self.assertIn("mattpocock/skills", [s.repo for s in sources])
        self.assertTrue(all(s.files for s in sources))


def names_a_manifest_file(node):
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and any(node.value == name or node.value.endswith(f"/{name}") for name in MANIFEST_FILES))


def manifest_paths_built(tree):
    for node in ast.walk(tree):
        operands = []
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            operands = [node.left, node.right]
        elif isinstance(node, ast.Call):
            operands = list(node.args)
        yield from (node.lineno for operand in operands if names_a_manifest_file(operand))


class OnlyTheManifestModuleReadsTheManifests(unittest.TestCase):
    def test_no_code_outside_the_manifest_module_opens_or_parses_components_or_upstream_json(self):
        found = []
        for path in sorted(list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").glob("*.py"))):
            if path == ROOT / "src/quality_gates/manifest.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            found += [f"{path.relative_to(ROOT)}:{line}" for line in manifest_paths_built(tree)]
        self.assertEqual(found, [])


class AdmissionRecords(unittest.TestCase):
    def test_a_manifest_hands_out_its_admission_records_by_name(self):
        loaded = manifest.components_from(COMPONENTS)
        radon = next(a for a in loaded.admissions if a.name == "radon")
        self.assertEqual((radon.kind, radon.licence, radon.last_release, radon.minimum_version, radon.tested_version),
                         ("dependency", "MIT", datetime.date(2023, 3, 26), "6", "6.0.1"))


class ExplainerRecords(unittest.TestCase):
    def test_a_component_that_names_its_explainer_hands_out_the_path_it_names(self):
        named = changed(COMPONENTS, lambda d: d["components"][0].update(explainer="explainers/crap.md"))
        self.assertEqual(manifest.components_from(named).components[0].explainer, "explainers/crap.md")

    def test_a_component_that_names_no_explainer_hands_out_none(self):
        self.assertIsNone(manifest.components_from(COMPONENTS).components[0].explainer)


class DependencyVersions(unittest.TestCase):
    def test_a_dependency_origin_takes_its_version_from_the_minimum_its_admission_records(self):
        origin = manifest.components_from(COMPONENTS).components[0].parts[2].origin
        self.assertEqual(origin.as_dict(), {"type": "dependency", "name": "radon", "version": ">=6"})

    def test_an_origin_whose_admission_records_no_minimum_has_no_version(self):
        origin = manifest.components_from(COMPONENTS).components[0].origin
        self.assertIsNone(origin.version)


def admission(edit):
    return changed(COMPONENTS, lambda d: edit(d["admissions"]))


class MalformedAdmission(unittest.TestCase):
    def rejected(self, data):
        with self.assertRaises(manifest.ManifestError) as failure:
            manifest.components_from(data)
        return str(failure.exception)

    def test_a_source_missing_its_licence_fails_naming_the_source_and_the_field(self):
        message = self.rejected(admission(lambda a: a[0].pop("licence")))
        self.assertEqual(message, "components.json: admission 'radon': missing field 'licence'")

    def test_a_source_missing_its_practice_fails_naming_the_field(self):
        message = self.rejected(admission(lambda a: a[1].pop("practice")))
        self.assertEqual(message, "components.json: admission 'someone/skills': missing field 'practice'")

    def test_a_manifest_without_admissions_fails(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d.pop("admissions")))
        self.assertEqual(message, "components.json: missing field 'admissions'")

    def test_a_source_of_an_unknown_kind_fails_naming_the_kind(self):
        message = self.rejected(admission(lambda a: a[0].update(kind="plugin")))
        self.assertEqual(message, "components.json: admission 'radon': unknown source kind 'plugin'")

    def test_an_upstream_with_a_copyleft_licence_fails_naming_the_licence(self):
        message = self.rejected(admission(lambda a: a[1].update(licence="GPL-3.0-only")))
        self.assertEqual(message, "components.json: admission 'someone/skills': an upstream needs one of "
                                  "Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MIT, not 'GPL-3.0-only'")

    def test_an_upstream_with_a_permissive_licence_is_accepted(self):
        for licence in ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"):
            manifest.components_from(admission(lambda a: a[1].update(licence=licence)))

    def test_a_dependency_with_a_copyleft_osi_licence_is_accepted(self):
        loaded = manifest.components_from(admission(lambda a: a[0].update(licence="GPL-3.0-only")))
        self.assertEqual(loaded.admissions[0].licence, "GPL-3.0-only")

    def test_a_dependency_with_a_licence_that_is_not_osi_approved_fails(self):
        message = self.rejected(admission(lambda a: a[0].update(licence="Proprietary")))
        self.assertEqual(message, "components.json: admission 'radon': a dependency needs an OSI-approved licence, not 'Proprietary'")

    def test_a_test_only_tool_may_have_any_licence_but_not_an_empty_one(self):
        manifest.components_from(admission(lambda a: a[2].update(licence="Proprietary")))
        message = self.rejected(admission(lambda a: a[2].update(licence="")))
        self.assertEqual(message, "components.json: admission 'ruff': field 'licence' must be a licence id")

    def test_a_source_with_neither_a_last_release_nor_a_stable_reason_fails(self):
        message = self.rejected(admission(lambda a: a[1].pop("last_release")))
        self.assertEqual(message, "components.json: admission 'someone/skills': give either 'last_release' or 'stable'")

    def test_a_source_with_both_a_last_release_and_a_stable_reason_fails(self):
        message = self.rejected(admission(lambda a: a[1].update(stable="Prompts only.")))
        self.assertEqual(message, "components.json: admission 'someone/skills': give either 'last_release' or 'stable', not both")

    def test_a_source_marked_stable_with_no_reason_fails(self):
        message = self.rejected(admission(lambda a: (a[1].pop("last_release"), a[1].update(stable=" "))))
        self.assertEqual(message, "components.json: admission 'someone/skills': field 'stable' must give the reason")

    def test_a_source_marked_stable_with_a_reason_is_accepted(self):
        loaded = manifest.components_from(admission(lambda a: (a[1].pop("last_release"), a[1].update(stable="Prompts only."))))
        self.assertEqual(loaded.admissions[1].stable, "Prompts only.")

    def test_a_last_release_that_is_not_a_date_fails(self):
        message = self.rejected(admission(lambda a: a[1].update(last_release="October")))
        self.assertEqual(message, "components.json: admission 'someone/skills': field 'last_release' must be a date like 2026-10-29")

    def test_a_practice_that_is_not_one_sentence_fails(self):
        message = self.rejected(admission(lambda a: a[1].update(practice="Daily commits")))
        self.assertEqual(message, "components.json: admission 'someone/skills': the practice must be one line ending in a full stop")

    def test_a_minimum_version_without_a_tested_version_fails(self):
        message = self.rejected(admission(lambda a: a[0].pop("tested_version")))
        self.assertEqual(message, "components.json: admission 'radon': give 'minimum_version' and 'tested_version' together")

    def test_two_sources_with_one_name_fail(self):
        message = self.rejected(admission(lambda a: a.append(copy.deepcopy(a[0]))))
        self.assertEqual(message, "components.json: admission name 'radon' is listed twice")

    def test_a_component_origin_naming_a_source_with_no_admission_fails(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["origin"].update(type="upstream", name="other/skills")))
        self.assertEqual(message, "components.json: component 'risk': origin names 'other/skills', which has no admission")

    def test_a_part_origin_naming_a_source_with_no_admission_fails_naming_the_part(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][2]["origin"].update(name="radan")))
        self.assertEqual(message, "components.json: component 'risk', part 'radon': origin names 'radan', which has no admission")

    def test_an_adapted_source_with_no_admission_fails_naming_the_part(self):
        part = {"kind": "skill", "id": "adapted", "origin": {"type": "ours", "adapts": ["other/skills"]}}
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"].append(part)))
        self.assertEqual(message, "components.json: component 'risk', part 'adapted': origin names 'other/skills', which has no admission")

    def test_an_origin_whose_type_differs_from_the_kind_of_the_source_it_names_fails(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][2]["origin"].update(type="upstream")))
        self.assertEqual(message, "components.json: component 'risk', part 'radon': origin type 'upstream' names 'radon', a dependency")


class MalformedManifest(unittest.TestCase):
    def rejected(self, data, read=manifest.components_from):
        with self.assertRaises(manifest.ManifestError) as failure:
            read(data)
        return str(failure.exception)

    def test_a_well_formed_manifest_loads(self):
        self.assertEqual(manifest.components_from(COMPONENTS).components[0].parts[2].origin.version, ">=6")

    def test_a_component_missing_a_field_fails_naming_the_component_and_the_field(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0].pop("description")))
        self.assertEqual(message, "components.json: component 'risk': missing field 'description'")

    def test_a_part_missing_a_field_fails_naming_the_part_and_the_field(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][0].pop("id")))
        self.assertEqual(message, "components.json: component 'risk', part 1: missing field 'id'")

    def test_a_part_of_an_unknown_kind_fails_naming_the_kind(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][0].update(kind="plugin")))
        self.assertEqual(message, "components.json: component 'risk', part 'crap': unknown part kind 'plugin'")

    def test_an_origin_of_an_unknown_type_fails_naming_the_type(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["origin"].update(type="vendored")))
        self.assertEqual(message, "components.json: component 'risk': unknown origin type 'vendored'")

    def test_a_part_origin_of_an_unknown_type_fails_naming_the_part(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][2]["origin"].update(type="x")))
        self.assertEqual(message, "components.json: component 'risk', part 'radon': unknown origin type 'x'")

    def test_a_format_version_that_is_not_a_whole_number_fails(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d.update(format_version="1")))
        self.assertEqual(message, "components.json: field 'format_version' must be a whole number")

    def test_a_core_flag_that_is_not_true_or_false_fails(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0].update(core="no")))
        self.assertEqual(message, "components.json: component 'risk': field 'core' must be true or false")

    def test_component_languages_that_are_not_a_list_fail(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0].update(languages="python")))
        self.assertEqual(message, "components.json: component 'risk': field 'languages' must be a list")

    def test_part_languages_that_are_not_a_list_fail_naming_the_part(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][1].update(languages="python")))
        self.assertEqual(message, "components.json: component 'risk', part 'crap-python': field 'languages' must be a list")

    def test_origin_adapts_that_is_not_a_list_fails_naming_the_part(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][2]["origin"].update(adapts="radon")))
        self.assertEqual(message, "components.json: component 'risk', part 'radon': field 'adapts' must be a list")

    def test_a_ci_step_without_a_marker_fails_naming_the_part(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][1].pop("marker")))
        self.assertEqual(message, "components.json: component 'risk', part 'crap-python': missing field 'marker'")

    def test_a_precommit_step_without_a_marker_fails_naming_the_part(self):
        step = {"kind": "precommit_step", "id": "comment-debt"}
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"].append(step)))
        self.assertEqual(message, "components.json: component 'risk', part 'comment-debt': missing field 'marker'")

    def test_a_component_language_the_registry_does_not_know_fails_naming_the_language(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0].update(languages=["python", "cobol"])))
        self.assertEqual(message, "components.json: component 'risk': unknown language 'cobol'")

    def test_a_part_language_the_registry_does_not_know_fails_naming_the_part(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"][1].update(languages=["cobol"])))
        self.assertEqual(message, "components.json: component 'risk', part 'crap-python': unknown language 'cobol'")

    def test_every_registered_language_is_accepted_including_rust_and_shell(self):
        loaded = manifest.components_from(changed(COMPONENTS, lambda d: d["components"][0].update(
            languages=["python", "swift", "typescript", "rust", "shell"])))
        self.assertEqual(loaded.components[0].languages, ("python", "swift", "typescript", "rust", "shell"))

    def test_a_description_that_is_not_one_line_ending_in_a_full_stop_fails(self):
        for description in ("Flags tangled code", "Flags tangled.\nUntested code."):
            message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0].update(description=description)))
            self.assertEqual(message, "components.json: component 'risk': the description must be one line ending in a full stop")

    def test_an_explainer_that_is_not_the_path_of_a_markdown_file_fails_naming_the_component(self):
        for explainer in ("explainers/crap.txt", 3):
            with self.subTest(explainer=explainer):
                message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0].update(explainer=explainer)))
                self.assertEqual(message, "components.json: component 'risk': field 'explainer' must name a Markdown file")

    def test_two_components_with_one_id_fail(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"].append(copy.deepcopy(d["components"][0]))))
        self.assertEqual(message, "components.json: component id 'risk' is listed twice")

    def test_a_part_listed_twice_in_one_component_fails(self):
        message = self.rejected(changed(COMPONENTS, lambda d: d["components"][0]["parts"].append({"kind": "skill", "id": "crap"})))
        self.assertEqual(message, "components.json: component 'risk': part skill 'crap' is listed twice")

    def test_a_source_missing_a_field_fails_naming_the_source_and_the_field(self):
        message = self.rejected(changed(SOURCES, lambda d: d["sources"][0].pop("copied")), manifest.sources_from)
        self.assertEqual(message, "upstream.json: source 1: missing field 'copied'")

    def test_a_record_without_sources_fails(self):
        self.assertEqual(self.rejected({}, manifest.sources_from), "upstream.json: missing field 'sources'")

    def test_a_file_that_is_not_json_fails_naming_the_file(self):
        broken = Path(tempfile.mkdtemp()) / "broken.json"
        broken.write_text("{", encoding="utf-8")
        message = self.rejected(broken, manifest.load_components)
        self.assertTrue(message.startswith(f"{broken}: not valid JSON: "), message)

    def test_a_missing_file_fails_with_a_plain_message_naming_the_file(self):
        missing = Path(tempfile.mkdtemp()) / "missing.json"
        self.assertEqual(self.rejected(missing, manifest.load_components), f"{missing}: not found")

    def test_a_file_that_cannot_be_read_fails_with_a_plain_message_naming_the_file(self):
        folder = Path(tempfile.mkdtemp())
        message = self.rejected(folder, manifest.load_sources)
        self.assertTrue(message.startswith(f"{folder}: cannot be read: "), message)


if __name__ == "__main__":
    unittest.main()
