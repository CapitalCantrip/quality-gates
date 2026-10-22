import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from quality_gates import amendments, references, skills_sync

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "src/quality_gates/skills"
SETUP_STANDARDS = (SKILLS / "setup-standards/SKILL.md").read_text(encoding="utf-8")
CC_SWIFT = (SKILLS / "cc-swift/SKILL.md").read_text(encoding="utf-8")

NO_TEST_TARGET_PHRASES = (
    "no `.testTarget` in its `Package.swift`",
    "Report CRAP as **not done**",
    "reports no tests found",
    "add a test target with tests",
)
TEST_TARGET_COMMANDS = "In a SwiftPM package with a test target, run `swift test --enable-code-coverage`"
CI_WITH_TEST_TARGET = "A SwiftPM package with a test target also gets a CRAP step"
CI_WITHOUT_TEST_TARGET_PHRASES = (
    "A SwiftPM package with no test target gets no CRAP step",
    "report CRAP as **not done**, as step 3 says",
)
BASELINES_CAN_FINISH = "except a CRAP gate step 2 or 3 says to report as not done, which is reported not done with its reason"
CLOSURE_RULE = (
    "a new or changed closure (including a trailing closure or a nested `func`) "
    "that contains a branch has a test that runs it"
)
NESTED_FUNC_REASON = (
    "A nested `func`: the CRAP gate scores it on its own and fails an untested one with two or more branches. "
    "A small one (a single branch, CRAP 6) can still pass untested, which is why the rule asks for a test for it too."
)

PIN = re.compile(r"quality-gates@v(\d+\.\d+\.\d+)")
PIN_HOMES = ("setup-standards/SKILL.md", "setup-standards/ci-typescript.md")
PYPROJECT_VERSION = re.compile(r'^version = "([^"]+)"', re.MULTILINE)


def flat(text):
    return " ".join(text.split())


def section(case, text, heading, next_heading):
    case.assertIn(heading, text, f"the skill has no heading {heading!r}")
    after_heading = text.split(heading, 1)[1]
    case.assertIn(next_heading, after_heading, f"no heading {next_heading!r} after {heading!r}")
    return flat(after_heading.split(next_heading, 1)[0])


SCAN_SKILLS = ("cc-python", "cc-swift", "cc-typescript", "crap")
KEY_RULE_SKILLS = ("cc-python", "cc-typescript", "crap")
SKIP_LIST_SENTENCE = (
    "skips the folders on the [skip list](references/skip-list.md) "
    "and follows symlinked folders by the [symlink rule](references/symlinked-folders.md)."
)
REAL_PATH_REFERENCE = "](references/baseline-keys.md)"
ADR_DIR = ROOT / "docs/adr"
ADR_MENTION = re.compile(r"\bADR-\d{3}\b")
ADR_FILE = re.compile(r"ADR-\d{3}-[a-z]")
CITED_BY_DATE = re.compile(r"ADR-001's 20\d\d-\d\d-\d\d addendum")


def skill_text(name):
    return flat((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))


def hand_written_skill_files():
    return [path for path in SKILLS.rglob("*.md") if "references" not in path.relative_to(SKILLS).parts]


def paragraphs(path):
    return [flat(block) for block in path.read_text(encoding="utf-8").split("\n\n")]


def reference_links(path):
    found = [references.link_target(match.group(1)) for match in references.LINK.finditer(path.read_text(encoding="utf-8"))]
    return [target for target in found if target is not None]


class ScanSkillsLinkTheirRules(unittest.TestCase):
    def test_each_scan_skill_links_the_skip_list_and_symlink_rule_in_one_sentence(self):
        for name in SCAN_SKILLS:
            self.assertIn(SKIP_LIST_SENTENCE, skill_text(name), name)

    def test_each_skill_that_gives_baseline_keys_links_the_real_path_key_rule(self):
        for name in KEY_RULE_SKILLS:
            self.assertIn(REAL_PATH_REFERENCE, skill_text(name), name)

    def test_no_shipped_skill_cites_an_adr_addendum_by_its_date(self):
        for path in SKILLS.glob("*/SKILL.md"):
            self.assertIsNone(CITED_BY_DATE.search(flat(path.read_text(encoding="utf-8"))), path.parent.name)

    def test_the_readme_cites_no_adr_addendum_by_its_date(self):
        self.assertIsNone(CITED_BY_DATE.search(flat((ROOT / "README.md").read_text(encoding="utf-8"))))


class ReferenceFiles(unittest.TestCase):
    def test_every_shipped_reference_file_matches_its_tagged_adr_section(self):
        self.assertEqual(references.check(ADR_DIR, SKILLS), [])

    def test_every_tagged_rule_stands_alone_in_a_consumer_repo(self):
        rules, _ = references.read_rules(ADR_DIR)
        self.assertEqual([pointer for rule in rules.values() for pointer in references.outside_pointers(rule)], [])

    def test_every_adr_links_each_amendment_and_the_text_it_amends_both_ways(self):
        self.assertEqual([problem for path in sorted(ADR_DIR.glob("ADR-*.md")) for problem in amendments.problems(path)], [])

    def test_no_shipped_skill_names_an_adr_file_by_path(self):
        for path in SKILLS.rglob("*.md"):
            self.assertIsNone(ADR_FILE.search(path.read_text(encoding="utf-8")), path.relative_to(SKILLS))

    def test_every_adr_mention_in_a_shipped_skill_links_the_reference_file_beside_it(self):
        for path in hand_written_skill_files():
            for paragraph in paragraphs(path):
                if ADR_MENTION.search(paragraph):
                    self.assertRegex(paragraph, references.LINK, f"{path.relative_to(SKILLS)}: {paragraph[:80]}")

    def test_after_qg_skills_every_skill_link_to_a_reference_file_resolves_in_a_consumer_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "CLAUDE.md").write_text("# Consumer\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stop:
                skills_sync.main(["--dest", str(repo / ".claude" / "skills")])
            self.assertEqual(stop.exception.code, 0)
            checked = 0
            for path in (repo / ".claude" / "skills").rglob("*.md"):
                for link in reference_links(path):
                    self.assertTrue((path.parent / link).is_file(), f"{path.relative_to(repo)} -> {link}")
                    checked += 1
        self.assertGreater(checked, 20)


README = ROOT / "README.md"
README_REFERENCE_LINK = re.compile(r"\]\((src/quality_gates/skills/[a-z-]+/references/[a-z0-9-]+\.md)\)")
SHARED_RUN = 8


def word_runs(text):
    words = text.replace("`", "").replace("*", "").split()
    return {tuple(words[start:start + SHARED_RUN]) for start in range(len(words) - SHARED_RUN + 1)}


def readme_prose():
    lines = README.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("|")).split("\n\n")


class ReadmeLinksRules(unittest.TestCase):
    def test_no_readme_paragraph_repeats_eight_words_of_a_tagged_adr_rule(self):
        rules, problems = references.read_rules(ADR_DIR)
        self.assertEqual(problems, [])
        for paragraph in readme_prose():
            for name, rule in rules.items():
                shared = word_runs(paragraph) & word_runs(rule.text)
                self.assertFalse(shared, f"README repeats rule:{name}: {' '.join(sorted(shared)[0]) if shared else ''}")

    def test_every_readme_link_to_a_reference_file_reaches_a_shipped_file(self):
        found = README_REFERENCE_LINK.findall(README.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(found), 7)
        for link in found:
            self.assertTrue((ROOT / link).is_file(), link)

    def test_the_readme_links_the_naming_rules_instead_of_restating_them(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("references/function-names.md)", text)
        for example in ("path::outer.inner", "path::K.Inner.deep", "path::(anonymous)#2"):
            self.assertNotIn(example, text)


class SetupStandards(unittest.TestCase):
    def baselines(self):
        return section(self, SETUP_STANDARDS, "## 3. Baselines", "## 4. Hooks")

    def ci(self):
        return section(self, SETUP_STANDARDS, "## 5. CI", "## 6. The asking rule")

    def test_a_swiftpm_package_with_no_test_target_reports_crap_as_not_done_with_the_reason(self):
        for phrase in NO_TEST_TARGET_PHRASES:
            self.assertIn(phrase, self.baselines())

    def test_the_swiftpm_coverage_commands_are_scoped_to_a_package_with_a_test_target(self):
        self.assertIn(TEST_TARGET_COMMANDS, self.baselines())

    def test_the_ci_crap_step_is_scoped_to_a_swiftpm_package_with_a_test_target(self):
        self.assertIn(CI_WITH_TEST_TARGET, self.ci())
        for phrase in CI_WITHOUT_TEST_TARGET_PHRASES:
            self.assertIn(phrase, self.ci())

    def test_the_baselines_step_can_finish_with_crap_reported_not_done(self):
        self.assertIn(BASELINES_CAN_FINISH, self.baselines())


class ClosureReviewRule(unittest.TestCase):
    def test_the_closure_rule_sits_under_its_own_review_rule_heading_in_cc_swift(self):
        self.assertIn(CLOSURE_RULE, section(self, CC_SWIFT, "## Review rule", "## Dependencies"))

    def test_a_small_nested_func_the_gate_passes_untested_still_needs_a_test_in_the_review_rule(self):
        self.assertIn(NESTED_FUNC_REASON, section(self, CC_SWIFT, "## Review rule", "## Dependencies"))

    def test_the_closure_rule_appears_once_across_the_shipped_skills(self):
        occurrences = sum(flat(path.read_text(encoding="utf-8")).count(CLOSURE_RULE) for path in SKILLS.rglob("*.md"))
        self.assertEqual(occurrences, 1)

    def test_a_consumer_repo_gets_the_closure_rule_in_its_cc_swift_skill_after_a_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            skills_sync.sync(dest)
            copied = flat((dest / "cc-swift" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn(CLOSURE_RULE, copied)


class VersionPin(unittest.TestCase):
    def pins(self):
        found = {}
        for path in SKILLS.rglob("*"):
            if path.is_file() and path.suffix == ".md":
                for version in PIN.findall(path.read_text(encoding="utf-8")):
                    found.setdefault(path.relative_to(SKILLS).as_posix(), []).append(version)
        return found

    def test_every_pin_in_the_shipped_skills_matches_the_version_in_pyproject(self):
        project = PYPROJECT_VERSION.search((ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1)
        readme = PIN.findall((ROOT / "README.md").read_text(encoding="utf-8"))
        mismatched = {name: versions for name, versions in self.pins().items() if set(versions) != {project}}
        self.assertEqual((mismatched, set(readme)), ({}, {project}))

    def test_only_setup_standards_carries_the_install_pin(self):
        self.assertEqual(sorted(self.pins()), sorted(PIN_HOMES))


if __name__ == "__main__":
    unittest.main()
