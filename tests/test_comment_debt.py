import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from quality_gates import comment_debt as cd
from quality_gates import ratchet, setup_choices

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

    def judged(self, counts, baseline):
        found = [ratchet.Finding(ratchet.Location(path), n, cd.FINDING_KIND, '') for path, n in counts.items()]
        return ratchet.judge(found, baseline)

    def outcomes(self, counts, baseline):
        return {v.location.key: (v.outcome, v.now, v.allowed) for v in self.judged(counts, baseline).verdicts}

    def test_a_new_file_with_a_comment_is_over(self):
        self.assertEqual(self.outcomes({'new.py': 1}, {}), {'new.py': (ratchet.Outcome.FAILED, 1, None)})

    def test_a_file_at_its_baseline_passes(self):
        self.assertEqual(self.outcomes({'a.py': 2}, {'a.py': 2}), {'a.py': (ratchet.Outcome.PASSED, 2, 2)})

    def test_a_file_below_its_baseline_is_reported_as_paid(self):
        self.assertEqual(self.outcomes({'a.py': 1}, {'a.py': 2}), {'a.py': (ratchet.Outcome.BEHIND, 1, 2)})

    def test_a_baseline_entry_for_a_deleted_file_is_stale(self):
        self.assertEqual(self.outcomes({}, {'gone.py': 4}), {'gone.py': (ratchet.Outcome.BEHIND, None, 4)})

    def test_lowering_never_raises_a_count(self):
        self.assertEqual(ratchet.lowered(self.judged({'a.py': 2}, {'a.py': 3})), {'a.py': 2})

    def test_lowering_drops_files_that_reach_zero(self):
        self.assertEqual(ratchet.lowered(self.judged({'a.py': 0, 'b.py': 1}, {'a.py': 3, 'b.py': 1})), {'b.py': 1})


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

    def test_an_empty_or_whitespace_only_baseline_flag_is_refused_naming_the_flag(self):
        self.put('a.py', '# one\nx = 1\n')
        for value in ('', '  '):
            for mode in ([], ['--update']):
                with self.subTest(value=value, mode=mode):
                    out = io.StringIO()
                    self.assertEqual(cd.main([*mode, '--baseline', value], root=self.root, out=out), 2)
                    self.assertIn('--baseline was given an empty path', out.getvalue())
        self.assertFalse(self.file.exists())

    def choose(self, chosen=('no-comments',), exclude=(), comment_gate_exclude=()):
        (self.root / 'quality-gates.json').write_text(json.dumps({
            'format_version': 1,
            'languages': ['python'],
            'exclude': list(exclude),
            'components': {'chosen': list(chosen), 'declined': []},
            'commit_time_limit_seconds': 2,
            'settings': {'no-comments': {'exclude': list(comment_gate_exclude), 'conventions': []}},
        }))

    def keep_untracked(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_a_tracked_file_under_the_choice_files_exclude_is_not_checked(self):
        self.choose(exclude=['vendor'])
        self.keep_untracked('vendor/v.py', '# vendored\n')
        subprocess.run(['git', 'add', 'vendor/v.py'], cwd=self.root, check=True)
        self.assertEqual(self.run_gate('--update')[0], 0)
        self.assertEqual(self.baseline(), {})
        self.assertEqual(self.run_gate()[0], 0)

    def test_a_file_in_a_default_fixture_folder_is_not_checked_without_a_choice_file(self):
        self.keep_untracked('tests/fixtures/f.py', '# fixture\n')
        subprocess.run(['git', 'add', 'tests/fixtures/f.py'], cwd=self.root, check=True)
        self.assertEqual(self.run_gate('--update')[0], 0)
        self.assertEqual(self.baseline(), {})

    def test_the_comment_gates_own_exclude_skips_whole_path_segments_only(self):
        self.choose(comment_gate_exclude=['build'])
        self.keep_untracked('build/x.py', '# built\n')
        self.keep_untracked('buildscripts/x.py', '# scripted\n')
        self.run_gate('--update')
        self.assertEqual(self.baseline(), {'buildscripts/x.py': 1})

    def test_an_untracked_file_that_git_would_commit_is_checked(self):
        self.keep_untracked('new.py', '# new\n')
        self.run_gate('--update')
        self.assertEqual(self.baseline(), {'new.py': 1})

    def test_an_untracked_file_the_gitignore_lists_is_not_checked(self):
        self.put('.gitignore', 'gen/\n')
        self.keep_untracked('gen/g.py', '# generated\n')
        self.run_gate('--update')
        self.assertEqual(self.baseline(), {})

    def test_python_is_not_checked_when_the_choice_file_does_not_choose_no_comments(self):
        self.choose(chosen=[])
        self.put('a.py', '# one\n')
        self.run_gate('--update')
        self.assertEqual(self.baseline(), {})

    def test_python_is_checked_when_the_choice_file_chooses_no_comments(self):
        self.choose()
        self.put('a.py', '# one\n')
        self.run_gate('--update')
        self.assertEqual(self.baseline(), {'a.py': 1})

    def test_rust_is_checked_when_the_choice_file_chooses_no_comments_rust(self):
        self.choose(chosen=['no-comments', 'no-comments-rust'])
        self.put('main.rs', 'fn main() {\n    // a comment\n}\n')
        self.file.write_text('{"main.rs": 1}\n')
        self.assertEqual(self.run_gate(), (0, 'comment debt: 1 lines in 1 files, none new\n'))

    def test_rust_is_not_checked_when_the_choice_file_does_not_choose_no_comments_rust(self):
        self.choose()
        self.put('main.rs', 'fn main() {\n    // a comment\n}\n')
        self.file.write_text('{}\n')
        self.assertEqual(self.run_gate(), (0, 'comment debt: 0 lines in 0 files, none new\n'))

    def test_rust_is_not_checked_without_a_choice_file(self):
        self.put('main.rs', 'fn main() {\n    // a comment\n}\n')
        self.file.write_text('{}\n')
        self.assertEqual(self.run_gate(), (0, 'comment debt: 0 lines in 0 files, none new\n'))

    def test_update_still_refuses_to_add_an_entry_for_a_chosen_language(self):
        self.choose(chosen=['no-comments', 'no-comments-rust'])
        self.put('main.rs', 'fn main() {\n    // a comment\n}\n')
        self.file.write_text('{}\n')
        code, out = self.run_gate('--update')
        self.assertEqual(code, 1)
        self.assertIn('FAIL main.rs: 1 comment lines, baseline allows 0', out)
        self.assertIn(cd.UPDATE_REFUSAL, out)
        self.assertEqual(self.file.read_text(), '{}\n')

    def test_the_report_totals_one_languages_comments_before_it_is_chosen_and_judges_nothing(self):
        self.choose()
        self.put('a.py', '# one\n')
        self.put('main.rs', '// one\nfn main() {\n    // two\n}\n')
        self.put('lib.rs', '// three\n')
        self.put('plain.rs', 'fn f() {}\n')
        self.assertEqual(self.run_gate('--report', 'rust'), (0, '# Rust comment debt: 3 lines in 2 files\n'))
        self.assertFalse(self.file.exists())

    def test_the_exclude_flag_is_refused_and_names_setup_standards(self):
        self.put('a.py', 'x = 1\n')
        for argv in (['--exclude', 'x'], ['--exclude=x'], ['--status', '--exclude', 'x'], ['--update', '--exclude', 'x']):
            with self.subTest(argv=argv):
                code, out = self.run_gate(*argv)
                self.assertEqual(code, 2)
                self.assertIn('/setup-standards', out)
                self.assertIn('--exclude', out)
        self.assertFalse(self.file.exists())

    def test_each_tracked_file_is_one_finding_with_its_comment_count_and_line_numbers(self):
        self.put('a.py', '# one\nx = 1\ny = 2  # two\n')
        self.put('b.py', 'x = 1\n')
        self.assertEqual(cd.findings(self.root), [
            ratchet.Finding(ratchet.Location('a.py'), 2, 'comment lines', '1, 3'),
            ratchet.Finding(ratchet.Location('b.py'), 0, 'comment lines', ''),
        ])

    def test_comment_debt_keeps_no_ratchet_or_baseline_code_of_its_own(self):
        self.assertIs(cd.ratchet, ratchet)
        for name in ('lowered', 'load_baseline', 'write_baseline', 'check', 'update'):
            with self.subTest(name=name):
                self.assertFalse(hasattr(cd, name))

    def test_status_lists_each_file_under_its_area(self):
        self.put('a.py', '# a workaround for now\nx = 1\n')
        code, out = self.run_gate('--status')
        self.assertEqual(code, 0)
        self.assertIn('# Comment debt: 1 lines in 1 files', out)
        self.assertIn('    1    1  a.py', out)

    def test_a_file_named_only_by_its_suffix_is_counted_as_git_lists_it(self):
        (self.root / 'pkg').mkdir()
        self.put('pkg/.py', '# a workaround for now\nx = 1\n')
        code, out = self.run_gate('--status')
        self.assertEqual(code, 0)
        self.assertIn('## pkg — 1 lines', out)


class AcceptingRustEndToEndTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        self.file = self.root / 'comment-debt.json'
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'app.py').write_text('# why\nx = 1\n')
        (self.root / 'main.rs').write_text('fn main() {\n    // a comment\n}\n')

    def tearDown(self):
        self.tmp.cleanup()

    def setup(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = setup_choices.main(list(argv), root=self.root)
        self.assertEqual(code, 0, err.getvalue())
        return out.getvalue()

    def gate(self, *argv):
        out = io.StringIO()
        return cd.main(list(argv), root=self.root, out=out), out.getvalue()

    def offered(self):
        rows = json.loads(self.setup('--json'))['components']
        return next(row['choice'] for row in rows if row['id'] == 'no-comments-rust')

    def test_setup_offers_rust_shows_its_total_and_choosing_it_adds_rust_entries_beside_pythons_unchanged(self):
        self.setup('--go', '--choose', 'no-comments')
        python_only = self.file.read_text()

        self.assertEqual(self.offered(), 'offered')
        self.assertEqual(self.gate('--report', 'rust'), (0, '# Rust comment debt: 1 lines in 1 files\n'))
        self.assertEqual(self.file.read_text(), python_only)

        self.setup('--go', '--choose', 'no-comments-rust')
        self.assertEqual(self.file.read_text().replace('  "main.rs": 1,\n', ''), python_only)

    def test_choosing_rust_replaces_every_rust_entry_and_leaves_every_other_entry_as_it_was(self):
        self.setup('--go', '--choose', 'no-comments')
        self.file.write_text('{\n  "old.py": 4,\n  "old.rs": 2,\n  "src/app.py": 1\n}\n')
        self.setup('--go', '--choose', 'no-comments-rust')
        self.assertEqual(self.file.read_text(), '{\n  "main.rs": 1,\n  "old.py": 4,\n  "src/app.py": 1\n}\n')

    def test_setup_without_go_lists_the_baseline_among_its_planned_changes_and_writes_nothing(self):
        self.setup('--go', '--choose', 'no-comments')
        before = self.file.read_text(), (self.root / 'quality-gates.json').read_text()
        out = self.setup('--choose', 'no-comments-rust')
        self.assertIn('  comment-debt.json: will change\n', out)
        self.assertEqual((self.file.read_text(), (self.root / 'quality-gates.json').read_text()), before)

    def test_choosing_rust_again_once_it_is_chosen_never_raises_its_entries(self):
        self.setup('--go', '--choose', 'no-comments', '--choose', 'no-comments-rust')
        recorded = self.file.read_text()
        (self.root / 'main.rs').write_text('fn main() {\n    // a comment\n    // another\n}\n')
        self.setup('--go', '--choose', 'no-comments-rust')
        self.assertEqual(self.file.read_text(), recorded)
        self.assertEqual(self.gate()[0], 1)

    def test_choosing_rust_records_only_the_files_the_gate_checks_after_the_exclusions_setup_moves_in_the_same_run(self):
        self.setup('--go', '--choose', 'no-comments')
        (self.root / 'vendor').mkdir()
        (self.root / 'vendor' / 'v.rs').write_text('// vendored\n')
        (self.root / '.githooks').mkdir()
        (self.root / '.githooks' / 'pre-commit').write_text('#!/bin/sh\ncomment-debt --exclude vendor/\n')
        self.setup('--go', '--choose', 'no-comments-rust')
        self.assertEqual(json.loads(self.file.read_text()), {'main.rs': 1, 'src/app.py': 1})
        self.assertEqual(self.gate(), (0, 'comment debt: 2 lines in 2 files, none new\n'))

    def test_a_malformed_baseline_stops_setup_choosing_rust_and_nothing_is_written(self):
        self.setup('--go', '--choose', 'no-comments')
        choice = (self.root / 'quality-gates.json').read_text()
        self.file.write_text('[]')
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = setup_choices.main(['--go', '--choose', 'no-comments-rust'], root=self.root)
        self.assertEqual(code, 2)
        self.assertIn('comment-debt.json', err.getvalue())
        self.assertEqual(((self.root / 'quality-gates.json').read_text(), self.file.read_text()), (choice, '[]'))

    def test_choosing_rust_in_setup_records_its_comments_so_the_gate_passes_and_a_new_rust_comment_fails(self):
        self.setup('--go', '--choose', 'no-comments')
        self.gate('--update')
        self.assertEqual(self.gate(), (0, 'comment debt: 1 lines in 1 files, none new\n'))

        self.setup('--go', '--choose', 'no-comments-rust')
        self.assertEqual(json.loads(self.file.read_text()), {'main.rs': 1, 'src/app.py': 1})
        self.assertEqual(self.gate(), (0, 'comment debt: 2 lines in 2 files, none new\n'))

        (self.root / 'main.rs').write_text('fn main() {\n    // a comment\n    // another\n}\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('FAIL main.rs: 2 comment lines, baseline allows 1 — lines 2, 3', out)


class LiveRepositoryTest(unittest.TestCase):

    def test_this_repository_adds_no_comments_beyond_its_baseline(self):
        out = io.StringIO()
        code = cd.main([], root=REPO, out=out)
        self.assertEqual(code, 0, out.getvalue())

    def test_update_on_this_repository_leaves_its_baseline_byte_for_byte_the_same(self):
        original = (REPO / 'comment-debt.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'comment-debt.json'
            copy.write_bytes(original)
            code = cd.main(['--update'], root=REPO, baseline=copy, out=io.StringIO())
            self.assertEqual((code, copy.read_bytes()), (0, original))


if __name__ == '__main__':
    unittest.main()
