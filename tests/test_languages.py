import argparse
import ast
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from quality_gates import comment_debt, complexity_scan, crap, languages, languages_table, manifest, status, xccov
from quality_gates import quality_check as qc
from quality_gates.complexity_scan import Function

ROOT = Path(__file__).resolve().parents[1]
PYTHON_REPORT = "tests/fixtures/python/coverage-report.json"
PYTHON_SAMPLE = "tests/fixtures/python/sample.py"
SWIFT_REPORT = ROOT / "tests/fixtures/swift/xccov-report.json"
SWIFTPM_REPORT_AS_BUILT = ROOT / "tests/fixtures/swift/llvm-cov-export.json"
SWIFTPM_PACKAGE_IN_THIS_CHECKOUT = ROOT / "tests/fixtures/swift/package"
SWIFTPM_BUILT_IN_ANOTHER_CHECKOUT_AT = "/ci/SwiftCovFixture"
SWIFTPM_STORE = "tests/fixtures/swift/package/Sources/Grades/Store.swift"
TYPESCRIPT_REPORT = "tests/fixtures/typescript/coverage-final.json"
TYPESCRIPT_SAMPLE = "tests/fixtures/typescript/sample.ts"


def swiftpm_report_measured_in_this_checkout(test):
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    path = Path(tmp.name) / "llvm-cov-export.json"
    text = SWIFTPM_REPORT_AS_BUILT.read_text(encoding="utf-8")
    path.write_text(text.replace(SWIFTPM_BUILT_IN_ANOTHER_CHECKOUT_AT, str(SWIFTPM_PACKAGE_IN_THIS_CHECKOUT)), encoding="utf-8")
    return str(path)


def reader(flag):
    formats = {coverage.flag: coverage for coverage in crap.COVERAGE_FORMATS}
    return formats[flag].read


PACKAGE = ROOT / "src/quality_gates"
REGISTRY_MODULE = "languages"
WILDCARD = "*"
TABLE_NAME = "LANGUAGES"
ALLOWED_NAMES = {
    ("project_files.hook_names", "*.py"): "lists the package's own hooks, which are Python scripts",
    ("project_files.PIN_FILE", "pyproject.toml"): "the pin is read from the Python dependency file, not to detect a language",
}


def registered_names():
    names = set()
    for language in languages.REGISTERED:
        for suffix in language.suffixes + language.folder_suffixes:
            names |= {suffix, WILDCARD + suffix}
        names |= set(language.markers)
    return names


def place_name(node):
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        return node.name
    targets = node.targets if isinstance(node, ast.Assign) else []
    return targets[0].id if len(targets) == 1 and isinstance(targets[0], ast.Name) else "<module>"


def places(tree):
    for node in tree.body:
        yield place_name(node), node


def suffix_globs():
    return tuple(WILDCARD + suffix for language in languages.REGISTERED for suffix in language.suffixes)


def names_a_language_file(node, names):
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    return node.value in names or node.value.endswith(suffix_globs())


def language_names_outside_the_registry(module_paths):
    names, found = registered_names(), {}
    for path in module_paths:
        for place, top in places(ast.parse(path.read_text(encoding="utf-8"))):
            for node in ast.walk(top):
                if names_a_language_file(node, names):
                    found.setdefault((f"{path.stem}.{place}", node.value), node.lineno)
    return found


def imported_names(node):
    if isinstance(node, ast.ImportFrom):
        return [node.module or ""]
    return [alias.name for alias in node.names] if isinstance(node, ast.Import) else []


def imports_of(path):
    return [name for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) for name in imported_names(node)]


def outside_the_registry():
    return [path for path in sorted(PACKAGE.rglob("*.py")) if path.stem != REGISTRY_MODULE]


def declares_a_language_table(node):
    targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
    return any(isinstance(target, ast.Name) and target.id == TABLE_NAME for target in targets)


def declares_one_in(path):
    return any(declares_a_language_table(node) for node in ast.parse(path.read_text(encoding="utf-8")).body)


def module_name(path):
    return ".".join((PACKAGE.name, *path.relative_to(PACKAGE).with_suffix("").parts))


def module_language_tables(module_paths):
    return {f"{path.stem}.{TABLE_NAME}": getattr(importlib.import_module(module_name(path)), TABLE_NAME)
            for path in module_paths if declares_one_in(path)}


GATES = languages_table.GATES
LANGUAGE_TABLES = {
    **module_language_tables(outside_the_registry()),
    "complexity_scan.COUNTERS": complexity_scan.COUNTERS,
}


def installed_for(command, components):
    return {language for component in components for part in component.parts
            if (part.kind, part.id) == ("command", command) for language in component.languages}


class GateTables(unittest.TestCase):
    def test_every_gate_table_the_languages_page_shows_is_found_by_the_package_scan(self):
        found = [id(table) for table in LANGUAGE_TABLES.values()]
        for name, table in GATES.items():
            with self.subTest(name):
                self.assertIn(id(table), found)

    def test_the_package_scan_finds_a_language_table_declared_in_any_module(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "planted.py"
            for source in ("LANGUAGES = {}\n", "LANGUAGES: dict = {}\n"):
                with self.subTest(source):
                    path.write_text(source, encoding="utf-8")
                    self.assertTrue(declares_one_in(path))

    def test_every_gate_table_names_only_registered_languages(self):
        for name, table in LANGUAGE_TABLES.items():
            with self.subTest(name):
                self.assertLessEqual(set(table), set(languages.LANGUAGES))

    def test_a_shell_shebang_names_shell_directly_or_through_env(self):
        for line in ("#!/bin/sh", "#!/bin/bash -e", "#! /usr/bin/zsh", "#!/usr/bin/env dash", "#!/usr/bin/env -S bash -eu"):
            with self.subTest(line):
                self.assertEqual(languages.language_of_first_line(line), "shell")

    def test_a_first_line_that_is_not_a_shell_shebang_names_no_language(self):
        for line in ("", "#!/usr/bin/env python3", "#!", "# sh", "echo #!/bin/sh"):
            with self.subTest(line):
                self.assertIsNone(languages.language_of_first_line(line))

    def test_rust_and_shell_are_registered_though_no_gate_scores_them(self):
        self.assertEqual(list(languages.LANGUAGES), ["python", "swift", "typescript", "rust", "shell"])

    def test_the_manifest_installs_each_gate_for_exactly_the_languages_its_table_scores(self):
        components = manifest.load_components().components
        for command, table in GATES.items():
            with self.subTest(command):
                self.assertEqual(installed_for(command, components), set(table))


class RegistryOwnsSuffixesAndMarkers(unittest.TestCase):
    def test_outside_the_registry_no_code_names_a_language_suffix_or_project_marker(self):
        found = language_names_outside_the_registry(outside_the_registry())
        self.assertEqual({where: line for where, line in found.items() if where not in ALLOWED_NAMES}, {})

    def test_an_allowed_place_is_allowed_only_the_name_it_lists(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "project_files.py"
            path.write_text('def hook_names(source):\n    return source.glob("*.py"), source.name.endswith(".rs")\n',
                            encoding="utf-8")
            found = language_names_outside_the_registry([path])
        self.assertEqual({where for where in found if where not in ALLOWED_NAMES}, {("project_files.hook_names", ".rs")})

    def test_the_check_recognises_a_suffix_a_suffix_pattern_a_marker_and_a_project_folder(self):
        for source in ('f.endswith(".rs")', 'run(["git", "ls-files", "*.sh"])', '(root / "Cargo.toml").exists()',
                       'name.endswith(".xcodeproj")', 'root.glob("**/*.py")', 'root.glob("*.rs")',
                       'root.glob("src/*.tsx")'):
            with self.subTest(source):
                self.assertTrue(any(names_a_language_file(node, registered_names())
                                    for node in ast.walk(ast.parse(source))))

    def test_the_check_ignores_a_file_name_that_merely_ends_in_a_suffix(self):
        self.assertFalse(any(names_a_language_file(node, registered_names())
                             for node in ast.walk(ast.parse('GUARD = "stage_guard.py"'))))

    def test_every_allowed_place_still_names_one_so_the_list_holds_no_dead_entry(self):
        self.assertEqual(set(ALLOWED_NAMES) - set(language_names_outside_the_registry(outside_the_registry())), set())

    def test_the_registry_imports_no_gate_and_no_coverage_reader(self):
        imported = imports_of(PACKAGE / f"{REGISTRY_MODULE}.py")
        self.assertEqual([name for name in imported if name.startswith(PACKAGE.name)], [])


class LanguageRecordTest(unittest.TestCase):
    def test_every_language_crap_accepts_has_a_counting_tool_suffixes_and_a_coverage_reader(self):
        for name, scored in crap.LANGUAGES.items():
            with self.subTest(name):
                language = languages.LANGUAGES[name]
                counter = complexity_scan.COUNTERS[name]
                self.assertEqual(crap.build_parser().parse_args(["--lang", name]).lang, name)
                self.assertTrue(language.label)
                self.assertIn(counter.tool, complexity_scan.COUNTING_TOOLS)
                self.assertTrue(language.suffixes)
                self.assertTrue(scored.coverage)
                if counter.tool == complexity_scan.LIZARD:
                    self.assertTrue(counter.lizard_languages)
                for coverage in scored.coverage:
                    self.assertTrue(coverage.flag.startswith("--"))
                    self.assertTrue(coverage.flag[len("--"):])
                    self.assertTrue(coverage.source)
                    self.assertTrue(coverage.help)
                    self.assertTrue(callable(coverage.read))

    def test_every_language_says_where_its_coverage_comes_from(self):
        for name, scored in crap.LANGUAGES.items():
            with self.subTest(name):
                self.assertTrue(scored.coverage_from)

    def test_a_language_lists_its_suffixes_in_declaration_order_for_help(self):
        self.assertEqual(languages.LANGUAGES["typescript"].suffix_text, ".ts .tsx .js .jsx .cjs .mjs")

    def test_every_language_cc_check_accepts_has_a_nothing_found_message(self):
        self.assertEqual(list(qc.LANGUAGES), ["python", "typescript"])
        for name, nothing_found in qc.LANGUAGES.items():
            with self.subTest(name):
                self.assertEqual(qc.build_parser().parse_args(["--lang", name, "x"]).lang, name)
                self.assertTrue(nothing_found)

    def test_no_two_languages_share_a_coverage_flag(self):
        flags = [coverage.flag for coverage in crap.COVERAGE_FORMATS]
        self.assertEqual(sorted(flags), sorted(set(flags)))

    def test_coverage_flags_are_offered_in_language_order(self):
        flags = [coverage.flag for coverage in crap.COVERAGE_FORMATS]
        self.assertEqual(flags, ["--coverage-json", "--xcresult", "--llvm-cov-json", "--istanbul-json"])

    def test_each_coverage_format_names_its_own_json_source_tag(self):
        sources = {coverage.flag: coverage.source for coverage in crap.COVERAGE_FORMATS}
        self.assertEqual(sources, {
            "--coverage-json": "coverage-json", "--xcresult": "xcresult", "--llvm-cov-json": "llvm-cov-json",
            "--istanbul-json": "istanbul-json",
        })

    def test_each_coverage_format_stores_its_report_where_argparse_would_by_default(self):
        for coverage in crap.COVERAGE_FORMATS:
            with self.subTest(coverage.flag):
                self.assertEqual(argparse.ArgumentParser().add_argument(coverage.flag).dest, coverage.dest)


class CoverageReaderTest(unittest.TestCase):
    def setUp(self):
        before = os.getcwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, before)

    def xccov(self):
        stdout = SWIFT_REPORT.read_bytes()
        return patch.object(xccov, "run", return_value=CompletedProcess([], 0, stdout=stdout, stderr=b""))

    def test_python_coverage_is_the_branch_coverage_within_the_functions_lines(self):
        coverage_of = reader("--coverage-json")(PYTHON_REPORT)
        self.assertEqual(coverage_of(Function(PYTHON_SAMPLE, "grade", 2, 1, 4, "grade")), 0.5)

    def test_swift_coverage_is_matched_by_the_name_before_its_label_and_the_start_line(self):
        with self.xccov():
            coverage_of = reader("--xcresult")("App.xcresult")
        self.assertEqual(coverage_of(Function("/build/Sources/Store.swift", "load#2", 3, 20, 30, "load")), 0.25)

    def test_swiftpm_coverage_is_the_line_coverage_of_the_llvm_cov_body_that_opens_inside_the_function(self):
        coverage_of = reader("--llvm-cov-json")(swiftpm_report_measured_in_this_checkout(self))
        self.assertAlmostEqual(coverage_of(Function(SWIFTPM_STORE, "add", 3, 6, 16, "add")), 9 / 11)

    def test_typescript_coverage_is_the_branch_coverage_within_istanbuls_function_range(self):
        coverage_of = reader("--istanbul-json")(TYPESCRIPT_REPORT)
        self.assertEqual(coverage_of(Function(TYPESCRIPT_SAMPLE, "grade", 5, 1, 10, "grade")), 0.875)

    def test_a_function_in_a_file_the_report_does_not_cover_has_unknown_coverage(self):
        with self.xccov():
            readers = {
                "python": reader("--coverage-json")(PYTHON_REPORT),
                "swift": reader("--xcresult")("App.xcresult"),
                "swiftpm": reader("--llvm-cov-json")(swiftpm_report_measured_in_this_checkout(self)),
                "typescript": reader("--istanbul-json")(TYPESCRIPT_REPORT),
            }
        for lang, coverage_of in readers.items():
            with self.subTest(lang):
                self.assertIsNone(coverage_of(Function("elsewhere/Other.x", "f", 2, 1, 4, "f")))


if __name__ == "__main__":
    unittest.main()
