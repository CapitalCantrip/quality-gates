import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from quality_gates import comment_debt as cd

REPO = Path(__file__).resolve().parents[1]


class CountingTest(unittest.TestCase):

    def test_a_hash_comment_on_its_own_line_is_debt(self):
        self.assertEqual(cd.debt_lines('x = 1\n# why\ny = 2\n'), [2])

    def test_a_trailing_comment_is_debt(self):
        self.assertEqual(cd.debt_lines('x = 1  # why\n'), [1])

    def test_every_line_of_a_docstring_is_debt(self):
        source = 'def f():\n    """One.\n\n    Two.\n    """\n    return 1\n'
        self.assertEqual(cd.debt_lines(source), [2, 3, 4, 5])

    def test_a_bare_string_used_as_a_comment_is_debt(self):
        source = 'def f():\n    x = 1\n    "why"\n    return x\n'
        self.assertEqual(cd.debt_lines(source), [3])

    def test_a_hash_inside_a_string_is_not_a_comment(self):
        self.assertEqual(cd.debt_lines('url = "a#b"\ncolour = "#fff"\n'), [])

    def test_a_string_that_is_assigned_is_not_debt(self):
        self.assertEqual(cd.debt_lines('HELP = """usage"""\n'), [])

    def test_a_shebang_and_a_coding_cookie_are_exempt(self):
        source = '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nx = 1\n'
        self.assertEqual(cd.debt_lines(source), [])

    def test_a_shebang_after_line_one_is_debt(self):
        self.assertEqual(cd.debt_lines('x = 1\n#!/bin/sh\n'), [2])

    def test_a_bare_pragma_is_exempt(self):
        source = (
            'import a  # noqa: E402\n'
            'import b  # noqa: E402, F401\n'
            'x = 1  # type: ignore[valid-type]\n'
            'if y:  # pragma: no cover\n'
            '    pass\n'
        )
        self.assertEqual(cd.debt_lines(source), [])

    def test_a_pragma_that_carries_prose_is_debt(self):
        self.assertEqual(cd.debt_lines('import a  # noqa: E402  (path set above)\n'), [1])


class RatchetTest(unittest.TestCase):

    def test_a_new_file_with_a_comment_is_over(self):
        over, _, _ = cd.ratchet({'new.py': [3]}, {})
        self.assertEqual(over, {'new.py': ([3], 0)})

    def test_a_file_at_its_baseline_passes(self):
        self.assertEqual(cd.ratchet({'a.py': [1, 2]}, {'a.py': 2}), ({}, {}, []))

    def test_a_file_below_its_baseline_is_reported_as_paid(self):
        _, under, _ = cd.ratchet({'a.py': [1]}, {'a.py': 2})
        self.assertEqual(under, {'a.py': (1, 2)})

    def test_a_baseline_entry_for_a_deleted_file_is_stale(self):
        _, _, stale = cd.ratchet({}, {'gone.py': 4})
        self.assertEqual(stale, ['gone.py'])

    def test_lowering_never_raises_a_count(self):
        self.assertEqual(cd.lowered({'a.py': [1, 2, 3]}, {'a.py': 2}), {'a.py': 2})

    def test_lowering_drops_files_that_reach_zero(self):
        self.assertEqual(cd.lowered({'a.py': [], 'b.py': [1]}, {'a.py': 3, 'b.py': 1}), {'b.py': 1})


class RepositoryTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        self.file = self.root / 'comment-debt.json'

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, text):
        (self.root / name).write_text(text)
        subprocess.run(['git', 'add', name], cwd=self.root, check=True)

    def run_gate(self, *argv):
        out = io.StringIO()
        return cd.main(list(argv), root=self.root, baseline=self.file, out=out), out.getvalue()

    def baseline(self):
        return json.loads(self.file.read_text())

    def test_the_check_refuses_to_run_without_a_baseline(self):
        self.assertEqual(self.run_gate()[0], 2)

    def test_the_first_update_records_existing_debt_and_the_check_then_passes(self):
        self.put('a.py', '# one\n# two\nx = 1\n')
        self.assertEqual(self.run_gate('--update')[0], 0)
        self.assertEqual(self.baseline(), {'a.py': 2})
        self.assertEqual(self.run_gate()[0], 0)

    def test_adding_a_comment_fails_the_check_and_names_the_lines(self):
        self.put('a.py', '# one\nx = 1\n')
        self.run_gate('--update')
        self.put('a.py', '# one\nx = 1  # two\n')
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn('a.py: 2 comment lines, baseline allows 1 — lines 1, 2', out)

    def test_update_will_not_record_a_new_comment(self):
        self.put('a.py', 'x = 1\n')
        self.run_gate('--update')
        self.put('a.py', '# new\nx = 1\n')
        self.assertEqual(self.run_gate('--update')[0], 1)
        self.assertEqual(self.baseline(), {})

    def test_paid_debt_fails_the_check_until_the_baseline_is_lowered(self):
        self.put('a.py', '# one\n# two\nx = 1\n')
        self.run_gate('--update')
        self.put('a.py', '# one\nx = 1\n')
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn('PAID a.py', out)
        self.run_gate('--update')
        self.assertEqual(self.baseline(), {'a.py': 1})
        self.assertEqual(self.run_gate()[0], 0)

    def test_the_baseline_defaults_to_comment_debt_json_at_the_repo_root(self):
        self.put('a.py', '# one\nx = 1\n')
        out = io.StringIO()
        self.assertEqual(cd.main(['--update'], root=self.root, out=out), 0)
        self.assertEqual(self.baseline(), {'a.py': 1})

    def test_the_baseline_flag_chooses_another_file(self):
        other = self.root / 'tools' / 'debt.json'
        other.parent.mkdir()
        self.put('a.py', '# one\nx = 1\n')
        out = io.StringIO()
        self.assertEqual(cd.main(['--update', '--baseline', str(other)], root=self.root, out=out), 0)
        self.assertEqual(json.loads(other.read_text()), {'a.py': 1})

    def test_an_excluded_prefix_is_not_counted(self):
        (self.root / 'backups').mkdir()
        self.put('backups/old.py', '# old\nx = 1\n')
        self.run_gate('--update', '--exclude', 'backups/')
        self.assertEqual(self.baseline(), {})

    def test_status_lists_each_file_under_its_area(self):
        self.put('a.py', '# a workaround for now\nx = 1\n')
        code, out = self.run_gate('--status')
        self.assertEqual(code, 0)
        self.assertIn('# Comment debt: 1 lines in 1 files', out)
        self.assertIn('    1    1  a.py', out)


class LiveRepositoryTest(unittest.TestCase):

    def test_this_repository_adds_no_comments_beyond_its_baseline(self):
        out = io.StringIO()
        code = cd.main([], root=REPO, out=out)
        self.assertEqual(code, 0, out.getvalue())


if __name__ == '__main__':
    unittest.main()
