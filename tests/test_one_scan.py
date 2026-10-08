import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from quality_gates import complexity_scan, crap
from quality_gates import quality_check as qc

ROOT = Path(__file__).resolve().parents[1]
TS_FIXTURES = str(ROOT / "tests/fixtures/typescript")
LIZARD_MISSING = "lizard is missing, though quality-gates depends on it.\n  Reinstall quality-gates in this environment.\n"
RADON_MISSING = "radon is not installed.\n  Install with: pip3 install radon\n"

NESTED = """\
class K:
    def m(self, x):
        if x:
            return 1
        return 2

    class Inner:
        def deep(self, x):
            if x:
                return 1
            return 2


def outer(x):
    def inner(y):
        if y:
            return 1
        return 2
    return inner(x) if x else 0


def outer(x):
    return 1 if x else 2
"""


def call(main, argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(argv)
        except SystemExit as stop:
            return stop.code, out.getvalue(), err.getvalue()
    raise AssertionError("main did not exit")


def cc_names(*argv):
    return {(r["file"], r["fullname"]) for r in json.loads(call(qc.main, [*argv, "--format", "json"])[1])}


def crap_names(*argv):
    out = call(crap.main, [*argv, "--no-coverage", "--min-cc", "1", "--json"])[1]
    return {(f["file"], f["name"]) for f in json.loads(out)["functions"]}


class InTempDir(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        before = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, before)

    def write(self, path, text):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")


class SameFunctionsTest(InTempDir):
    def test_both_gates_list_the_same_python_functions_by_the_same_names(self):
        self.write("src/mod.py", NESTED)
        expected = {("src/mod.py", name) for name in ("K.m", "K.Inner.deep", "outer", "outer.inner", "outer#2")}
        self.assertEqual(cc_names("src"), expected)
        self.assertEqual(crap_names("--lang", "python", "src"), expected)

    def test_both_gates_list_the_same_typescript_functions_by_the_same_names(self):
        names = cc_names("--lang", "typescript", TS_FIXTURES)
        self.assertIn((f"{TS_FIXTURES}/sample.ts", "(anonymous)#2"), names)
        self.assertEqual(crap_names("--lang", "typescript", TS_FIXTURES), names)

    def test_a_file_radon_cannot_parse_is_skipped_by_both_gates(self):
        self.write("src/bad.py", "def broken(:\n")
        self.write("src/good.py", "def good(x):\n    return 1 if x else 2\n")
        self.assertEqual(cc_names("src"), {("src/good.py", "good")})
        self.assertEqual(crap_names("--lang", "python", "src"), {("src/good.py", "good")})

    def test_a_hidden_folder_off_the_skip_list_is_scanned_by_both_gates(self):
        self.write(".claude/hooks/hook.py", "def hook(x):\n    return 1 if x else 2\n")
        expected = {(".claude/hooks/hook.py", "hook")}
        self.assertEqual(cc_names("."), expected)
        self.assertEqual(crap_names("--lang", "python", "."), expected)


class SkippedFolderLineTest(InTempDir):
    def setUp(self):
        super().setUp()
        self.write("src/build/gen.py", "def gen(x):\n    return 1 if x else 2\n")
        self.write("src/dist/out.py", "def out(x):\n    return 1 if x else 2\n")
        self.write("src/real.py", "def real(x):\n    return 1 if x else 2\n")

    def test_crap_names_the_skipped_folders_after_its_report(self):
        _, out, _ = call(crap.main, ["--lang", "python", "src", "--no-coverage", "--no-color"])
        self.assertTrue(out.endswith("Skipped 2 folder(s): src/build, src/dist\n"))

    def test_crap_json_lists_the_skipped_folders(self):
        _, out, _ = call(crap.main, ["--lang", "python", "src", "--no-coverage", "--json"])
        self.assertEqual(json.loads(out)["skipped"], ["src/build", "src/dist"])

    def test_crap_prints_no_skipped_line_when_nothing_was_skipped(self):
        _, out, _ = call(crap.main, ["--lang", "python", "src/real.py", "--no-coverage"])
        self.assertNotIn("Skipped", out)

    def test_crap_json_has_an_empty_skipped_list_when_nothing_was_skipped(self):
        _, out, _ = call(crap.main, ["--lang", "python", "src/real.py", "--no-coverage", "--json"])
        self.assertEqual(json.loads(out)["skipped"], [])


class ToolErrorMessageTest(InTempDir):
    def setUp(self):
        super().setUp()
        self.write("src/a.ts", "function a(x) { return x ? 1 : 2; }\n")
        self.write("src/a.py", "def a(x):\n    return 1 if x else 2\n")

    def both(self, *argv):
        return call(qc.main, list(argv)), call(crap.main, ["--no-coverage", *argv])

    def assert_messages(self, results, body):
        (cc_code, _, cc_err), (crap_code, _, crap_err) = results
        self.assertEqual((cc_code, cc_err), (2, f"ERROR: {body}"))
        self.assertEqual((crap_code, crap_err), (2, f"[crap] {body}"))

    def test_a_missing_lizard_exits_2_in_both_gates_with_the_same_message(self):
        with patch.object(complexity_scan.importlib.util, "find_spec", return_value=None):
            self.assert_messages(self.both("--lang", "typescript", "src"), LIZARD_MISSING)

    def test_a_crashed_lizard_exits_2_in_both_gates_with_the_same_message(self):
        crashed = CompletedProcess([], 2, stdout="", stderr="boom")
        with patch.object(complexity_scan, "run", return_value=crashed):
            self.assert_messages(self.both("--lang", "typescript", "src"), "lizard failed:\nboom\n")

    def test_a_missing_radon_exits_2_in_both_gates_with_the_same_message(self):
        with patch.dict(sys.modules, {"radon": None, "radon.visitors": None}):
            self.assert_messages(self.both("--lang", "python", "src"), RADON_MISSING)


if __name__ == "__main__":
    unittest.main()
