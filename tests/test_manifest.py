import ast
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import manifest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_FILES = ("components.json", "upstream.json")
COMPONENTS = {
    "format_version": 1,
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
            {"kind": "dependency", "id": "radon", "origin": {"type": "dependency", "name": "radon", "version": ">=6"}},
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
        self.assertEqual(loaded.format_version, 1)
        self.assertTrue(core.core)
        self.assertEqual(core.origin.type, "upstream")
        self.assertIn(("skill", "tdd"), [(p.kind, p.id) for p in core.parts])

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
