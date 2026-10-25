import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import skills_sync, status

OURS = {"type": "ours"}
POCOCK = {"type": "upstream", "name": "mattpocock/skills"}

MANIFEST = {
    "format_version": 1,
    "components": [
        {
            "id": "core",
            "name": "Core",
            "description": "The workflow.",
            "core": True,
            "languages": [],
            "origin": POCOCK,
            "parts": [
                {"kind": "skill", "id": "tdd"},
                {"kind": "hook", "id": "stage_guard.py"},
                {"kind": "claude_md_line", "id": "asking-rule"},
                {"kind": "command", "id": "qg-skills"},
            ],
        },
        {
            "id": "risk",
            "name": "Risk gate",
            "description": "Flags tangled, untested code.",
            "core": False,
            "languages": ["python", "swift"],
            "origin": OURS,
            "parts": [
                {"kind": "skill", "id": "crap"},
                {"kind": "baseline", "id": "crap-baseline.json"},
                {"kind": "ci_step", "id": "crap-python", "marker": "crap --lang python", "languages": ["python"]},
                {"kind": "ci_step", "id": "crap-swift", "marker": "crap --lang swift", "languages": ["swift"]},
                {"kind": "dependency", "id": "radon"},
            ],
        },
        {
            "id": "rust-lint",
            "name": "Rust lint",
            "description": "Lints Rust.",
            "core": False,
            "languages": ["rust"],
            "origin": OURS,
            "parts": [{"kind": "skill", "id": "cc-rust"}],
        },
    ],
}


def component(report, component_id):
    return next(c for c in report["components"] if c["id"] == component_id)


def part(report, component_id, kind, part_id):
    return next(p for p in component(report, component_id)["parts"] if p["kind"] == kind and p["id"] == part_id)


class Status(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "shipped"
        for name in ("tdd", "crap", "cc-rust"):
            self.write(self.source / name / "SKILL.md", f"{name} v1")
        self.hooks = self.tmp / "shipped-hooks"
        self.write(self.hooks / "stage_guard.py", "guard")
        self.repo = self.tmp / "repo"
        self.write(self.repo / "CLAUDE.md", "# Repo\n")
        self.write(self.repo / "pyproject.toml", "[project]\nname = 'consumer'\n")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def set_up(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            skills_sync.main(["--dest", str(self.repo / ".claude" / "skills")], self.source, self.hooks)
        self.write(self.repo / "crap-baseline.json", "{}")
        self.write(self.repo / ".github" / "workflows" / "tests.yml", "steps:\n  - run: crap --lang python src\n")

    def run_status(self, *flags, manifest=MANIFEST):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = status.main(["status", *flags], root=self.repo, source=self.source, hooks=self.hooks, manifest=manifest)
        return code, out.getvalue()

    def report(self, manifest=MANIFEST):
        code, out = self.run_status("--json", manifest=manifest)
        self.assertEqual(code, 0)
        return json.loads(out)

    def test_a_freshly_set_up_project_shows_every_applicable_component_installed(self):
        self.set_up()
        report = self.report()
        self.assertEqual(component(report, "core")["status"], "installed")
        self.assertEqual(component(report, "risk")["status"], "installed")

    def test_json_carries_the_manifest_format_version_and_the_installed_version(self):
        report = self.report()
        self.assertEqual(report["format_version"], 1)
        self.assertEqual(report["installed_version"], skills_sync.installed_version())

    def test_json_carries_each_components_id_description_origin_and_core_flag(self):
        self.set_up()
        core = component(self.report(), "core")
        self.assertEqual(core["description"], "The workflow.")
        self.assertEqual(core["origin"], POCOCK)
        self.assertTrue(core["core"])
        self.assertFalse(component(self.report(), "risk")["core"])

    def test_a_skill_the_project_lacks_is_missing(self):
        self.set_up()
        shutil.rmtree(self.repo / ".claude" / "skills" / "crap")
        report = self.report()
        self.assertEqual(part(report, "risk", "skill", "crap")["status"], "missing")
        self.assertEqual(component(report, "risk")["status"], "partly installed")

    def test_a_hand_edited_skill_copy_is_different(self):
        self.set_up()
        self.write(self.repo / ".claude" / "skills" / "tdd" / "SKILL.md", "edited")
        report = self.report()
        self.assertEqual(part(report, "core", "skill", "tdd")["status"], "different")
        self.assertEqual(component(report, "core")["status"], "different")

    def test_status_agrees_with_qg_skills_check_on_a_copied_file(self):
        self.set_up()
        self.write(self.repo / ".claude" / "skills" / "tdd" / "SKILL.md", "edited")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stop:
            skills_sync.main(["--dest", str(self.repo / ".claude" / "skills"), "--check"], self.source, self.hooks)
        self.assertEqual(stop.exception.code, 1)
        self.assertIn("tdd/SKILL.md: differs", out.getvalue())
        self.assertEqual(part(self.report(), "core", "skill", "tdd")["status"], "different")

    def test_an_edited_stage_guard_is_different(self):
        self.set_up()
        self.write(self.repo / ".claude" / "hooks" / "stage_guard.py", "edited")
        self.assertEqual(part(self.report(), "core", "hook", "stage_guard.py")["status"], "different")

    def test_a_stage_guard_that_is_not_registered_is_missing(self):
        self.set_up()
        (self.repo / ".claude" / "settings.json").unlink()
        self.assertEqual(part(self.report(), "core", "hook", "stage_guard.py")["status"], "missing")

    def test_a_missing_baseline_is_missing(self):
        self.set_up()
        (self.repo / "crap-baseline.json").unlink()
        self.assertEqual(part(self.report(), "risk", "baseline", "crap-baseline.json")["status"], "missing")

    def test_a_baseline_that_is_not_a_readable_file_is_unknown(self):
        self.set_up()
        (self.repo / "crap-baseline.json").unlink()
        (self.repo / "crap-baseline.json").mkdir()
        self.assertEqual(part(self.report(), "risk", "baseline", "crap-baseline.json")["status"], "unknown")

    def test_a_ci_step_is_unknown_when_a_workflow_file_cannot_be_read(self):
        self.set_up()
        (self.repo / ".github" / "workflows" / "tests.yml").write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(part(self.report(), "risk", "ci_step", "crap-python")["status"], "unknown")

    def test_a_ci_step_is_installed_when_a_workflow_runs_the_gate(self):
        self.set_up()
        self.assertEqual(part(self.report(), "risk", "ci_step", "crap-python")["status"], "installed")

    def test_a_ci_step_is_missing_when_no_workflow_runs_the_gate(self):
        self.set_up()
        self.write(self.repo / ".github" / "workflows" / "tests.yml", "steps:\n  - run: pytest\n")
        self.assertEqual(part(self.report(), "risk", "ci_step", "crap-python")["status"], "missing")

    def test_a_ci_step_is_not_found_in_a_longer_command_name(self):
        self.set_up()
        self.write(self.repo / ".github" / "workflows" / "tests.yml", "steps:\n  - run: echo my-crap\n")
        self.assertEqual(part(self.report(), "risk", "ci_step", "crap-python")["status"], "missing")

    def test_a_ci_step_is_judged_only_by_its_own_marker(self):
        self.set_up()
        self.write(self.repo / ".github" / "workflows" / "tests.yml", "steps:\n  - run: crap --lang typescript src\n")
        self.assertEqual(part(self.report(), "risk", "ci_step", "crap-python")["status"], "missing")

    def test_a_ci_step_that_runs_inside_a_named_file_is_installed_when_that_file_has_its_marker(self):
        manifest = {"format_version": 1, "components": [dict(MANIFEST["components"][1], parts=[
            {"kind": "ci_step", "id": "cc-check-python", "marker": "quality_check.main",
             "found_in": "tests/test_quality_gates.py"}])]}
        self.assertEqual(self.report(manifest)["components"][0]["parts"][0]["status"], "missing")
        self.write(self.repo / "tests" / "test_quality_gates.py", "self.exit_code(quality_check.main, argv)\n")
        self.assertEqual(self.report(manifest)["components"][0]["parts"][0]["status"], "installed")

    def test_a_part_for_a_language_the_project_does_not_use_is_not_applicable_and_left_out_of_the_roll_up(self):
        self.set_up()
        report = self.report()
        self.assertEqual(part(report, "risk", "ci_step", "crap-swift")["status"], "not applicable")
        self.assertEqual(component(report, "risk")["status"], "installed")

    def test_a_set_up_swift_project_shows_a_gate_with_a_swift_ci_step_installed(self):
        (self.repo / "pyproject.toml").unlink()
        self.write(self.repo / "Package.swift", "// package")
        self.set_up()
        self.write(self.repo / ".github" / "workflows" / "tests.yml", "steps:\n  - run: crap --lang swift Sources/\n")
        report = self.report()
        self.assertEqual(part(report, "risk", "ci_step", "crap-python")["status"], "not applicable")
        self.assertEqual(component(report, "risk")["status"], "installed")

    def test_a_missing_asking_rule_line_is_missing(self):
        self.set_up()
        self.write(self.repo / "CLAUDE.md", "# Repo\n")
        self.assertEqual(part(self.report(), "core", "claude_md_line", "asking-rule")["status"], "missing")

    def test_an_unreadable_instruction_file_is_unknown(self):
        self.set_up()
        (self.repo / "CLAUDE.md").write_bytes(b"\xff\xfe\x00bad")
        report = self.report()
        self.assertEqual(part(report, "core", "claude_md_line", "asking-rule")["status"], "unknown")
        self.assertEqual(component(report, "core")["status"], "unknown")

    def test_a_settings_file_that_is_not_json_makes_the_stage_guard_unknown(self):
        self.set_up()
        self.write(self.repo / ".claude" / "settings.json", "{not json")
        self.assertEqual(part(self.report(), "core", "hook", "stage_guard.py")["status"], "unknown")

    def test_different_outranks_unknown_in_the_roll_up(self):
        self.set_up()
        self.write(self.repo / ".claude" / "skills" / "tdd" / "SKILL.md", "edited")
        (self.repo / "CLAUDE.md").write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(component(self.report(), "core")["status"], "different")

    def test_a_component_with_nothing_installed_is_missing(self):
        self.assertEqual(component(self.report(), "core")["status"], "missing")

    def test_commands_and_dependencies_are_shown_as_provided_by_quality_gates_not_as_installed(self):
        report = self.report()
        self.assertEqual(part(report, "core", "command", "qg-skills")["status"], "provided by quality-gates")
        self.assertEqual(part(report, "risk", "dependency", "radon")["status"], "provided by quality-gates")

    def test_a_skill_the_release_does_not_ship_is_unknown(self):
        manifest = {"format_version": 1, "components": [dict(MANIFEST["components"][2], parts=[
            {"kind": "skill", "id": "not-shipped"}])]}
        self.write(self.repo / "Cargo.toml", "[package]\n")
        self.assertEqual(self.report(manifest)["components"][0]["parts"][0]["status"], "unknown")

    def test_a_python_project_shows_a_rust_component_as_not_applicable(self):
        self.assertEqual(component(self.report(), "rust-lint")["status"], "not applicable")

    def test_a_rust_project_shows_the_rust_component_as_applicable(self):
        self.write(self.repo / "Cargo.toml", "[package]\n")
        self.assertEqual(component(self.report(), "rust-lint")["status"], "missing")

    def test_a_swift_only_project_shows_a_python_only_component_as_not_applicable(self):
        (self.repo / "pyproject.toml").unlink()
        self.write(self.repo / "Package.swift", "// package")
        manifest = {"format_version": 1, "components": [dict(MANIFEST["components"][1], languages=["python"])]}
        self.assertEqual(self.report(manifest)["components"][0]["status"], "not applicable")

    def test_an_xcode_project_counts_as_a_swift_project(self):
        (self.repo / "pyproject.toml").unlink()
        (self.repo / "App.xcodeproj").mkdir()
        self.assertEqual(component(self.report(), "risk")["status"], "missing")

    def test_a_component_is_applicable_when_any_one_of_its_languages_is_used(self):
        (self.repo / "pyproject.toml").unlink()
        self.write(self.repo / "Sources" / "App.swift", "let a = 1")
        self.assertEqual(component(self.report(), "risk")["status"], "missing")

    def test_source_files_inside_the_virtual_environment_do_not_count_as_a_language(self):
        (self.repo / "pyproject.toml").unlink()
        self.write(self.repo / ".venv" / "lib" / "dep.py", "x = 1")
        self.assertEqual(component(self.report(), "risk")["status"], "not applicable")

    def test_the_copied_stage_guard_does_not_make_a_project_a_python_project(self):
        (self.repo / "pyproject.toml").unlink()
        self.write(self.repo / "src" / "app.ts", "export {}")
        self.set_up()
        manifest = {"format_version": 1, "components": [dict(MANIFEST["components"][1], languages=["python"])]}
        self.assertEqual(self.report(manifest)["components"][0]["status"], "not applicable")

    def test_source_files_in_build_and_vendored_output_do_not_count_as_a_language(self):
        (self.repo / "pyproject.toml").unlink()
        for folder in ("dist", "build", "target", "Pods", "DerivedData", ".tox", "lib/site-packages", ".build",
                       "node_modules", ".cache"):
            self.write(self.repo / folder / "vendored.py", "x = 1")
        manifest = {"format_version": 1, "components": [dict(MANIFEST["components"][1], languages=["python"])]}
        self.assertEqual(self.report(manifest)["components"][0]["status"], "not applicable")

    def test_a_language_component_is_applicable_to_a_project_with_typescript_files(self):
        (self.repo / "pyproject.toml").unlink()
        manifest = {"format_version": 1, "components": [dict(MANIFEST["components"][1], languages=["typescript"])]}
        self.write(self.repo / "src" / "app.tsx", "export {}")
        self.assertEqual(self.report(manifest)["components"][0]["status"], "missing")

    def test_the_pin_is_read_from_the_python_dev_dependencies(self):
        self.write(self.repo / "pyproject.toml", (
            '[project.optional-dependencies]\ndev = ["quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.11.1"]\n'))
        self.assertEqual(self.report()["pin"], "v0.11.1")

    def test_the_pin_is_read_from_the_install_line_in_a_ci_workflow(self):
        (self.repo / "pyproject.toml").unlink()
        self.write(self.repo / ".github" / "workflows" / "ci.yml", (
            '      - run: pip install "quality-gates @ git+https://github.com/CapitalCantrip/quality-gates@v0.12.0"\n'))
        self.assertEqual(self.report()["pin"], "v0.12.0")

    def test_no_pin_is_reported_as_pin_not_found_never_a_guess(self):
        report = self.report()
        self.assertIsNone(report["pin"])
        self.assertIn("pin not found", self.run_status()[1])

    def test_the_table_shows_the_pin_beside_the_installed_version(self):
        self.write(self.repo / "pyproject.toml", 'dev = ["quality-gates @ git+https://x/quality-gates@v9.9.9"]\n')
        _, out = self.run_status()
        self.assertIn("v9.9.9", out)
        self.assertIn(skills_sync.installed_version(), out)
        self.assertIn("differs", out)

    def test_the_pin_is_marked_matching_when_it_equals_the_installed_version(self):
        installed = skills_sync.installed_version()
        self.write(self.repo / "pyproject.toml", f'dev = ["quality-gates @ git+https://x/quality-gates@v{installed}"]\n')
        self.assertTrue(self.report()["pin_matches"])
        self.assertIn("matches", self.run_status()[1])

    def test_core_components_are_listed_first_and_marked_core(self):
        _, out = self.run_status()
        self.assertLess(out.index("core"), out.index("risk"))
        self.assertIn("Core", out)

    def test_not_applicable_components_are_listed_apart_from_the_rest(self):
        _, out = self.run_status()
        self.assertIn("Not applicable to this project", out)
        self.assertGreater(out.index("rust-lint"), out.index("Not applicable to this project"))

    def test_the_table_and_json_agree_on_every_components_status(self):
        self.set_up()
        self.write(self.repo / ".claude" / "skills" / "tdd" / "SKILL.md", "edited")
        _, table = self.run_status()
        for item in self.report()["components"]:
            line = next(l for l in table.splitlines() if l.strip().startswith(item["id"]))
            self.assertIn(item["status"], line)

    def test_the_table_shows_each_description_and_origin(self):
        _, out = self.run_status()
        self.assertIn("The workflow.", out)
        self.assertIn("mattpocock/skills", out)

    def test_the_table_names_the_parts_that_need_attention(self):
        self.set_up()
        self.write(self.repo / ".claude" / "skills" / "tdd" / "SKILL.md", "edited")
        self.assertIn("skill tdd: different", self.run_status()[1])

    def test_needs_attention_lists_only_parts_that_count_toward_status(self):
        self.set_up()
        (self.repo / "crap-baseline.json").unlink()
        _, out = self.run_status()
        attention = [line for line in out.splitlines() if "Needs attention" in line]
        self.assertEqual(attention, ["    Needs attention: baseline crap-baseline.json: missing"])

    def test_an_empty_folder_gets_a_plain_report_and_exit_0(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = status.main(["status"], root=empty, source=self.source, hooks=self.hooks, manifest=MANIFEST)
        self.assertEqual(code, 0)
        self.assertIn("No quality-gates parts found", out.getvalue())

    def test_status_exits_0_even_when_everything_is_different(self):
        self.set_up()
        self.write(self.repo / ".claude" / "skills" / "tdd" / "SKILL.md", "edited")
        self.assertEqual(self.run_status()[0], 0)

    def test_status_leaves_the_project_unchanged(self):
        self.set_up()
        before = sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*"))
        self.run_status()
        self.run_status("--json")
        after = sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*"))
        self.assertEqual(before, after)

    def test_the_real_manifest_reports_every_component_with_a_status(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = status.main(["status", "--json"], root=self.repo)
        report = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(report["format_version"], status.load_manifest()["format_version"])
        self.assertEqual(len(report["components"]), len(status.load_manifest()["components"]))


if __name__ == "__main__":
    unittest.main()
