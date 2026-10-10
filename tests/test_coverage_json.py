import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from quality_gates import coverage_json

ASCII_LOCALE = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "PYTHONIOENCODING": "utf-8"}
LOAD_REPORT = "from quality_gates import coverage_json; print(sorted(coverage_json.load(%r)))"


class PythonCoverageTest(unittest.TestCase):
    def test_branch_map_counts_taken_and_total_branches_per_source_line(self):
        bmap = coverage_json._build_branch_map([[3, 4], [3, 6], [9, 10]], [[3, 8], [9, 12]])
        self.assertEqual(bmap, {3: [2, 3], 9: [1, 2]})

    def test_branch_coverage_is_preferred_over_line_coverage(self):
        entry = coverage_json._parse_file_coverage({
            "executed_lines": [1, 2, 3, 4],
            "missing_lines": [],
            "executed_branches": [[2, 3]],
            "missing_branches": [[2, 4]],
        })
        self.assertEqual(coverage_json.function_coverage({"m.py": entry}, "m.py", 1, 4), 0.5)

    def test_line_coverage_is_used_when_the_function_has_no_branches(self):
        entry = coverage_json._parse_file_coverage({
            "executed_lines": [1, 2, 10],
            "missing_lines": [3, 4],
            "executed_branches": [[10, 11]],
            "missing_branches": [],
        })
        self.assertEqual(coverage_json.function_coverage({"m.py": entry}, "m.py", 1, 4), 0.5)

    def test_a_file_missing_from_coverage_has_no_coverage(self):
        self.assertIsNone(coverage_json.function_coverage({}, "m.py", 1, 4))

    def test_a_function_with_no_tracked_lines_has_no_coverage(self):
        entry = coverage_json._parse_file_coverage({"executed_lines": [20], "missing_lines": []})
        self.assertIsNone(coverage_json.function_coverage({"m.py": entry}, "m.py", 1, 4))

    def test_a_report_with_a_non_ascii_path_loads_whatever_the_machines_locale(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "coverage.json"
            report.write_text(json.dumps({"files": {"caf\u00e9.py": {}}}, ensure_ascii=False), encoding="utf-8")
            done = subprocess.run(
                [sys.executable, "-c", LOAD_REPORT % str(report)],
                env={**os.environ, **ASCII_LOCALE}, capture_output=True, text=True, encoding="utf-8",
            )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("caf\u00e9.py", done.stdout)


if __name__ == "__main__":
    unittest.main()
