import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import manifest as manifests, project_files, qg, setup_choices, skills_sync, status

OURS = {"type": "ours"}
POCOCK = {"type": "upstream", "name": "mattpocock/skills"}
ADMISSIONS = [{"name": "mattpocock/skills", "kind": "upstream", "licence": "MIT", "practice": "Tagged releases.",
               "last_release": "2026-10-29"}]
CORE = {"id": "core", "name": "Core", "description": "The workflow.", "core": True, "languages": [],
        "origin": POCOCK, "parts": [{"kind": "skill", "id": "tdd"}]}
RISK = {"id": "risk", "name": "Risk gate", "description": "Flags tangled, untested code.", "core": False,
        "languages": ["python"], "origin": OURS,
        "parts": [{"kind": "skill", "id": "crap"}, {"kind": "baseline", "id": "crap-baseline.json"},
                  {"kind": "ci_step", "id": "crap-python", "marker": "crap --lang python"},
                  {"kind": "precommit_step", "id": "crap-commit", "marker": "crap --lang python"},
                  {"kind": "dependency", "id": "radon"}]}
HELPERS = {"id": "helpers", "name": "Helpers", "description": "Design helpers.", "core": False, "languages": [],
           "origin": POCOCK, "parts": [{"kind": "skill", "id": "codebase-design"}]}
RUST = {"id": "rust-lint", "name": "Rust lint", "description": "Lints Rust.", "core": False, "languages": ["rust"],
        "origin": OURS, "parts": [{"kind": "skill", "id": "cc-rust"}]}
FRESH = {"id": "fresh", "name": "Fresh gate", "description": "A gate a later release adds.", "core": False,
         "languages": ["python"], "origin": OURS, "parts": [{"kind": "skill", "id": "fresh-skill"}]}


def manifest_of(*components):
    return manifests.components_from({"format_version": 2, "admissions": ADMISSIONS, "components": list(components)})


MANIFEST = manifest_of(CORE, RISK, HELPERS, RUST)


def git_init(folder):
    subprocess.run(["git", "init", "-q", str(folder)], check=True)


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(root).parts}


class Setup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "shipped"
        for name in ("tdd", "crap", "codebase-design", "cc-rust", "fresh-skill"):
            self.write(self.source / name / "SKILL.md", f"{name} v1")
        self.hooks = self.tmp / "shipped-hooks"
        self.write(self.hooks / "stage_guard.py", "guard")
        self.repo = self.tmp / "repo"
        git_init(self.repo)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def set_up_at_v0_12_0(self):
        self.write(self.repo / "pyproject.toml", "[project]\nname = 'consumer'\n")
        self.write(self.repo / "src" / "app.py", "x = 1\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            skills_sync.main(["--dest", str(self.repo / ".claude" / "skills")], self.source, self.hooks)
        self.write(self.repo / "crap-baseline.json", "{}")
        self.write(self.repo / ".github" / "workflows" / "tests.yml", "steps:\n  - run: crap --lang python src\n")
        self.write(self.repo / ".githooks" / "pre-commit", "#!/bin/sh\ncrap --lang python src\n")

    def run_setup(self, *flags, manifest=MANIFEST):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = setup_choices.main(list(flags), root=self.repo, source=self.source, hooks=self.hooks,
                                      manifest=manifest)
        return code, out.getvalue(), err.getvalue()

    def proposal(self, *flags, manifest=MANIFEST):
        code, out, err = self.run_setup("--json", *flags, manifest=manifest)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def choice_of(self, proposal, component_id):
        return next(c["choice"] for c in proposal["components"] if c["id"] == component_id)

    def recorded(self):
        return project_files.read_choice(self.repo)

    def status_of(self, component_id, manifest=MANIFEST):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status.main(["--json"], root=self.repo, source=self.source, hooks=self.hooks, manifest=manifest)
        return next(c["status"] for c in json.loads(out.getvalue())["components"] if c["id"] == component_id)

    def test_setup_is_a_qg_subcommand(self):
        self.assertIs(qg.COMMANDS["setup"], setup_choices)

    def test_setup_on_a_repo_whose_only_shell_file_is_an_extensionless_sh_script_proposes_shell(self):
        self.write(self.repo / "bin" / "run", "#!/bin/sh\necho hi\n")
        self.assertEqual(self.proposal()["languages"], ["shell"])

    def test_setup_without_go_writes_nothing(self):
        self.set_up_at_v0_12_0()
        before = tree(self.repo)
        _, out, _ = self.run_setup()
        self.assertIn("quality-gates.json: will be created", out)
        self.assertEqual(tree(self.repo), before)

    def test_on_a_project_set_up_at_v0_12_0_go_writes_a_choice_file_matching_what_is_installed_and_nothing_else(self):
        self.set_up_at_v0_12_0()
        before = tree(self.repo)
        code, _, _ = self.run_setup("--go")
        self.assertEqual(code, 0)
        after = tree(self.repo)
        self.assertEqual(set(after) - set(before), {"quality-gates.json"})
        self.assertEqual({name: after[name] for name in before}, before)
        self.assertEqual(self.recorded().languages, ("python",))
        self.assertEqual(self.recorded().chosen, ("helpers", "risk"))
        self.assertEqual(self.recorded().declined, ())
        self.assertEqual([self.status_of(c) for c in ("core", "risk", "helpers")], ["installed"] * 3)

    def test_the_first_choice_file_records_the_default_fixture_exclusion(self):
        self.set_up_at_v0_12_0()
        self.write(self.repo / "tests" / "fixtures" / "a.ts", "x")
        self.run_setup("--go")
        self.assertEqual(self.recorded().exclude, ("tests/fixtures/",))

    def test_running_setup_again_after_go_changes_nothing(self):
        self.set_up_at_v0_12_0()
        self.run_setup("--go")
        before = tree(self.repo)
        _, out, _ = self.run_setup()
        self.assertIn("quality-gates.json: unchanged", out)
        self.run_setup("--go")
        self.assertEqual(tree(self.repo), before)

    def test_a_component_the_choice_file_does_not_list_is_offered_and_recommended(self):
        self.set_up_at_v0_12_0()
        self.run_setup("--go")
        with_fresh = manifest_of(CORE, RISK, HELPERS, RUST, FRESH)
        proposal = self.proposal(manifest=with_fresh)
        self.assertEqual(self.choice_of(proposal, "fresh"), "offered")
        self.assertTrue(next(c["recommended"] for c in proposal["components"] if c["id"] == "fresh"))
        self.assertEqual(self.status_of("fresh", with_fresh), "not yet offered")

    def test_a_declined_offer_is_recorded_and_shows_offered_declined(self):
        self.set_up_at_v0_12_0()
        self.run_setup("--go")
        with_fresh = manifest_of(CORE, RISK, HELPERS, RUST, FRESH)
        code, _, err = self.run_setup("--decline", "fresh", "--go", manifest=with_fresh)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.recorded().declined, ("fresh",))
        self.assertEqual(self.choice_of(self.proposal(manifest=with_fresh), "fresh"), "offered, declined")
        self.assertEqual(self.status_of("fresh", with_fresh), "offered, declined")

    def test_an_accepted_offer_is_recorded_as_chosen(self):
        self.set_up_at_v0_12_0()
        self.run_setup("--go")
        with_fresh = manifest_of(CORE, RISK, HELPERS, RUST, FRESH)
        self.run_setup("--go", manifest=with_fresh)
        self.assertIn("fresh", self.recorded().chosen)

    def test_switching_off_a_gate_the_project_has_is_refused(self):
        self.set_up_at_v0_12_0()
        code, _, err = self.run_setup("--decline", "risk", "--go")
        self.assertEqual(code, 1)
        self.assertIn("risk", err)
        self.assertIn("#115", err)
        self.assertIsNone(self.recorded())

    def test_the_core_never_switches_off(self):
        code, _, err = self.run_setup("--decline", "core")
        self.assertEqual(code, 1)
        self.assertIn("core", err)

    def test_a_helper_component_switches_off_freely(self):
        self.set_up_at_v0_12_0()
        self.run_setup("--go")
        code, _, err = self.run_setup("--decline", "helpers", "--go")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.recorded().declined, ("helpers",))
        self.assertNotIn("helpers", self.recorded().chosen)

    def test_a_component_for_a_language_the_project_does_not_use_is_not_recorded(self):
        self.set_up_at_v0_12_0()
        self.assertEqual(self.choice_of(self.proposal(), "rust-lint"), "not applicable")
        self.run_setup("--go")
        self.assertNotIn("rust-lint", self.recorded().chosen + self.recorded().declined)

    def test_a_language_may_be_added_before_it_has_any_code(self):
        self.set_up_at_v0_12_0()
        proposal = self.proposal("--add-language", "rust")
        self.assertEqual(proposal["languages"], ["python", "rust"])
        self.assertNotEqual(self.choice_of(proposal, "rust-lint"), "not applicable")

    def test_removing_a_language_that_still_has_code_is_refused(self):
        self.set_up_at_v0_12_0()
        code, _, err = self.run_setup("--remove-language", "python", "--go")
        self.assertEqual(code, 1)
        self.assertIn("python", err)
        self.assertIn("src/app.py", err)
        self.assertIsNone(self.recorded())

    def test_removing_a_language_with_no_code_is_allowed(self):
        self.set_up_at_v0_12_0()
        self.run_setup("--add-language", "rust", "--go")
        self.run_setup("--remove-language", "rust", "--go")
        self.assertEqual(self.recorded().languages, ("python",))

    def test_an_unknown_language_or_component_is_refused_by_name(self):
        code, _, err = self.run_setup("--add-language", "cobol")
        self.assertEqual(code, 1)
        self.assertIn("cobol", err)
        code, _, err = self.run_setup("--choose", "nothing-like-it")
        self.assertEqual(code, 1)
        self.assertIn("nothing-like-it", err)

    def test_code_in_a_language_the_file_does_not_record_is_proposed_for_adding(self):
        self.set_up_at_v0_12_0()
        self.run_setup("--go")
        self.write(self.repo / "bin" / "run", "#!/bin/sh\n")
        self.assertEqual(self.proposal()["languages"], ["python", "shell"])

    def test_setup_moves_the_comment_gate_exclusions_from_the_hook_into_the_file_and_again_changes_nothing(self):
        self.write(self.repo / ".githooks" / "pre-commit",
                   "#!/bin/sh\nset -e\ncomment-debt --exclude gen/ --exclude fixtures/\n")
        self.run_setup("--go")
        self.assertEqual(self.recorded().comment_exclude, ("fixtures/", "gen/"))
        before = tree(self.repo)
        self.run_setup("--go")
        self.assertEqual(tree(self.repo), before)
        self.assertIn("comment-debt --exclude gen/ --exclude fixtures/", (self.repo / ".githooks" / "pre-commit").read_text())

    def test_setup_moves_comment_gate_exclusions_from_the_ci_workflow_in_either_spelling(self):
        self.write(self.repo / ".github" / "workflows" / "ci.yml",
                   "steps:\n  - run: comment-debt --exclude=vendor/ --exclude 'docs/old/'\n  - run: other --exclude x/\n")
        self.run_setup("--go")
        self.assertEqual(self.recorded().comment_exclude, ("docs/old/", "vendor/"))

    def test_the_table_shows_each_components_description_and_cost(self):
        self.set_up_at_v0_12_0()
        _, out, _ = self.run_setup()
        self.assertIn("Flags tangled, untested code.", out)
        self.assertIn("cost: commit delay; CI time; outside tools: radon", out)
        self.assertIn("cost: none", out)

    def test_the_proposal_carries_each_components_cost(self):
        costs = {c["id"]: c["cost"] for c in self.proposal()["components"]}
        self.assertEqual(costs["risk"], ["commit delay", "CI time", "outside tools: radon"])
        self.assertEqual(costs["helpers"], [])

    def test_setup_keeps_the_choice_files_own_exclusions_and_commit_limit(self):
        self.set_up_at_v0_12_0()
        choice = project_files.Choice(languages=("python",), chosen=("risk",), exclude=("vendor/",),
                                      commit_time_limit_seconds=1)
        project_files.write_kept(self.repo, project_files.CHOICE_FILE, project_files.choice_text(choice))
        self.run_setup("--go")
        self.assertEqual((self.recorded().exclude, self.recorded().commit_time_limit_seconds), (("vendor/",), 1))

    def test_a_broken_choice_file_exits_3_with_one_plain_line(self):
        self.write(self.repo / project_files.CHOICE_FILE, "{")
        code, out, err = self.run_setup()
        self.assertEqual((code, out), (3, ""))
        self.assertTrue(err.startswith("qg setup: "), err)
        self.assertEqual(len(err.splitlines()), 1)

    def test_the_real_manifest_gives_a_proposal_for_every_component(self):
        self.set_up_at_v0_12_0()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = setup_choices.main(["--json"], root=self.repo)
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out.getvalue())["components"]), len(manifests.load_components().components))


if __name__ == "__main__":
    unittest.main()
