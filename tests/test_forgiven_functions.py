import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BRANCHES = 12
TS_BODY = "".join(f"  if (x === {n}) {{ return {n} }}\n" for n in range(BRANCHES))
SWIFT_BODY = "".join(f"    if x == {n} {{ return {n} }}\n" for n in range(BRANCHES))
FORGIVEN_TS = f"// #lizard forgives\nfunction big(x) {{\n{TS_BODY}  return -1\n}}\n\nfunction small() {{ return 1 }}\n"
FORGIVEN_SWIFT = f"// #lizard forgives\nfunc big(x: Int) -> Int {{\n{SWIFT_BODY}    return -1\n}}\n\nfunc small() -> Int {{ return 1 }}\n"
FORGIVEN_GLOBALLY = "// #lizard forgive global\n" + FORGIVEN_TS
FORGIVEN_BY_METRIC = FORGIVEN_TS.replace("forgives", "forgives(cyclomatic_complexity)")
EXIT_FAILED = 1

GATES = {
    "cc-check": lambda lang, file: ["quality_gates.quality_check", "--lang", lang, file],
    "crap": lambda lang, file: ["quality_gates.crap", "--lang", lang, "--no-coverage", file],
}


class ForgivenFunctionsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def gate(self, name, lang, file, text):
        (self.root / file).write_text(text, encoding="utf-8")
        module, *args = GATES[name](lang, file)
        return subprocess.run([sys.executable, "-m", module, *args], cwd=self.root, capture_output=True, text=True)

    def test_cc_check_fails_a_typescript_function_marked_forgiven_and_lists_it(self):
        done = self.gate("cc-check", "typescript", "a.ts", FORGIVEN_TS)
        self.assertEqual(done.returncode, EXIT_FAILED, done.stdout + done.stderr)
        self.assertIn("CC= 13  a.ts:2  big", done.stdout)

    def test_cc_check_counts_the_forgiven_typescript_function_among_those_checked(self):
        done = self.gate("cc-check", "typescript", "a.ts", FORGIVEN_TS)
        self.assertIn("Functions checked:  2", done.stdout)

    def test_crap_fails_a_typescript_function_marked_forgiven_and_lists_it(self):
        done = self.gate("crap", "typescript", "a.ts", FORGIVEN_TS)
        self.assertEqual(done.returncode, EXIT_FAILED, done.stdout + done.stderr)
        self.assertIn("a.ts:2  big", done.stdout)

    def test_crap_fails_a_swift_function_marked_forgiven_and_lists_it(self):
        done = self.gate("crap", "swift", "A.swift", FORGIVEN_SWIFT)
        self.assertEqual(done.returncode, EXIT_FAILED, done.stdout + done.stderr)
        self.assertIn("A.swift:2  big", done.stdout)

    def test_a_function_forgiven_for_one_metric_is_scored_too(self):
        done = self.gate("cc-check", "typescript", "a.ts", FORGIVEN_BY_METRIC)
        self.assertEqual(done.returncode, EXIT_FAILED, done.stdout + done.stderr)
        self.assertIn("a.ts:2  big", done.stdout)

    def test_a_file_forgiven_globally_is_scored_too(self):
        done = self.gate("cc-check", "typescript", "a.ts", FORGIVEN_GLOBALLY)
        self.assertEqual(done.returncode, EXIT_FAILED, done.stdout + done.stderr)
        self.assertIn("a.ts:3  big", done.stdout)


if __name__ == "__main__":
    unittest.main()
