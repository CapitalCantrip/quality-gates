import tempfile
import unittest
from pathlib import Path

from quality_gates import skills_sync

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "src/quality_gates/skills"
SETUP_STANDARDS = (SKILLS / "setup-standards/SKILL.md").read_text(encoding="utf-8")
CC_SWIFT = (SKILLS / "cc-swift/SKILL.md").read_text(encoding="utf-8")

NO_TEST_TARGET = (
    "A SwiftPM package with no test target (no `.testTarget` in its `Package.swift`) "
    "has no coverage to record, so CRAP is not set up for it. Report CRAP as **not done**, "
    "with the reason (no test target, so `swift test --enable-code-coverage` reports no tests found) "
    "and what it takes (add a test target with tests, then rerun `/setup-standards`)."
)
TEST_TARGET_COMMANDS = "In a SwiftPM package with a test target, run `swift test --enable-code-coverage`"
CI_WITH_TEST_TARGET = "A SwiftPM package with a test target also gets a CRAP step"
CI_WITHOUT_TEST_TARGET = "A SwiftPM package with no test target gets no CRAP step; step 3 says how to report it."
BASELINES_CAN_FINISH = "Done when each gate passes on today's tree, or is reported not done with its reason."
CLOSURE_RULE = (
    "In Swift, a new or changed closure (including a trailing closure or a nested `func`) "
    "that contains a branch has a test that runs it. Until #53 is built, the CRAP gate cannot "
    "catch an untested one; ADR-001's 2026-10-10 addendum on SwiftPM coverage has the reason."
)


def flat(text):
    return " ".join(text.split())


def section(text, heading, next_heading):
    return flat(text.split(heading, 1)[1].split(next_heading, 1)[0])


class SetupStandards(unittest.TestCase):
    def baselines(self):
        return section(SETUP_STANDARDS, "## 3. Baselines", "## 4. Hooks")

    def ci(self):
        return section(SETUP_STANDARDS, "## 5. CI", "## 6. The asking rule")

    def test_a_swiftpm_package_with_no_test_target_reports_crap_as_not_done_with_the_reason(self):
        self.assertIn(NO_TEST_TARGET, self.baselines())

    def test_the_swiftpm_coverage_commands_are_scoped_to_a_package_with_a_test_target(self):
        self.assertIn(TEST_TARGET_COMMANDS, self.baselines())

    def test_the_ci_crap_step_is_scoped_to_a_swiftpm_package_with_a_test_target(self):
        self.assertIn(CI_WITH_TEST_TARGET, self.ci())
        self.assertIn(CI_WITHOUT_TEST_TARGET, self.ci())

    def test_the_baselines_step_can_finish_with_crap_reported_not_done(self):
        self.assertIn(BASELINES_CAN_FINISH, self.baselines())


class ClosureReviewRule(unittest.TestCase):
    def test_the_closure_rule_sits_in_the_architectural_constraints_of_cc_swift(self):
        self.assertIn(CLOSURE_RULE, section(CC_SWIFT, "## Architectural constraints", "## Dependencies"))

    def test_the_closure_rule_appears_once_across_the_shipped_skills(self):
        occurrences = sum(flat(path.read_text(encoding="utf-8")).count(CLOSURE_RULE) for path in SKILLS.rglob("*.md"))
        self.assertEqual(occurrences, 1)

    def test_a_consumer_repo_gets_the_closure_rule_in_its_cc_swift_skill_after_a_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills"
            skills_sync.sync(dest)
            copied = flat((dest / "cc-swift" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn(CLOSURE_RULE, copied)


if __name__ == "__main__":
    unittest.main()
