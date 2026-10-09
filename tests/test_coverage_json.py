import unittest

from quality_gates import coverage_json


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


if __name__ == "__main__":
    unittest.main()
