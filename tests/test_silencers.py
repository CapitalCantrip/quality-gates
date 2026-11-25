import contextlib
import dataclasses
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from quality_gates import comment_debt as cd
from quality_gates import crap, ratchet, setup_choices

PYTHON = cd.LANGUAGES['python']

COVER = '# pragma: no cover'
BRANCH = '# pragma: no branch'
FORMS_COVERAGE_PY_HONOURS = (
    '# pragma: no cover', '# pragma: no branch', '#pragma: no cover', '# pragma:no cover', '# pragma no cover',
    '# pragma: no  cover', '# PRAGMA: NO COVER', '# pragma: no cover - the other branch is tested elsewhere',
    '# noqa  # pragma: no cover', '# type: ignore  # pragma: no branch', '# pragma: no cover  # reason',
)
NOT_SILENCERS = (
    '# noqa', '# noqa: E402', '# type: ignore', '# type: ignore[valid-type]', '# fmt: off', '# fmt: on',
    '# fmt: skip', '# pragma: no mutate', '# pragma: cover', '# a plain comment', '# no cover',
)


def reading(source):
    return PYTHON.reading(source, ())


class PythonSilencerPatternTest(unittest.TestCase):

    def test_every_form_coverage_py_honours_matches_pythons_silencer_pattern(self):
        for text in FORMS_COVERAGE_PY_HONOURS:
            with self.subTest(text=text):
                self.assertIsNotNone(PYTHON.silencer.search(text))

    def test_noqa_type_ignore_fmt_and_other_pragmas_are_not_silencers(self):
        for text in NOT_SILENCERS:
            with self.subTest(text=text):
                self.assertIsNone(PYTHON.silencer.search(text))


class PythonSilencerReadingTest(unittest.TestCase):

    def test_a_pragma_no_cover_and_a_pragma_no_branch_are_silencers_at_their_lines(self):
        source = f'def f(x):\n    if x:  {COVER}\n        return 1\n    while x:  {BRANCH}\n        x -= 1\n'
        self.assertEqual(reading(source).silencers, (2, 4))

    def test_a_silencer_is_not_also_a_comment_line(self):
        self.assertEqual(reading(f'if x:  {COVER}\n    pass\n').debt, {})

    def test_a_silencer_that_carries_prose_is_a_silencer_and_not_also_a_comment_line(self):
        found = reading('if x:  # pragma: no cover - tested by hand\n    pass\n')
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_a_comment_beside_a_silencer_on_another_line_stays_a_comment_line(self):
        found = reading(f'# why\nif x:  {COVER}\n    pass\n')
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1]))

    def test_noqa_type_ignore_and_fmt_are_neither_comment_debt_nor_silencers(self):
        source = 'import a  # noqa: E402\nx = 1  # type: ignore[valid-type]\ny = [1,2]  # fmt: skip\n# fmt: off\n# fmt: on\n'
        found = reading(source)
        self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_a_pragma_inside_a_string_is_not_a_silencer(self):
        found = reading('MARKER = "# pragma: no cover"\n')
        self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_a_pragma_for_a_tool_that_is_not_ours_stays_a_comment_line(self):
        found = reading('x = 1  # pragma: no mutate\n')
        self.assertEqual((found.silencers, list(found.debt)), ((), [1]))

    def test_a_docstring_is_still_comment_debt_beside_a_silencer(self):
        found = reading(f'def f(x):\n    """One."""\n    if x:  {COVER}\n        return 1\n')
        self.assertEqual((found.silencers, list(found.debt)), ((3,), [2]))

    def test_the_checker_the_gate_calls_for_comment_lines_leaves_silencers_out(self):
        self.assertEqual(PYTHON.checker(f'if x:  {COVER}\n    pass\n', ()), {})


class SharedReaderSilencerTest(unittest.TestCase):

    def test_a_comment_matching_a_languages_silencer_pattern_is_a_silencer_and_not_a_comment_line_in_a_language_the_shared_reader_reads(self):
        row = dataclasses.replace(cd.LANGUAGES['typescript'], silencer=re.compile(r'//\s*silence\b'))
        found = row.reading('// why\nf(); // silence me\nlet s = "// silence";\n', ())
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1]))


def f_with_six_untested_branches(marker):
    ifs = ''.join(f'    if x == {n}:{marker}\n        return {n}\n' for n in range(1, 7))
    return f'def f(x):\n{ifs}    if x == 9:\n        return 9\n    return 0\n'


SOURCE_WITH_PRAGMAS = f_with_six_untested_branches(f'  {COVER}')
SOURCE_WITHOUT_PRAGMAS = f_with_six_untested_branches('')
PRAGMA_LINES = [2, 4, 6, 8, 10, 12]


def coverage_of(root, executed, missing, excluded, executed_branches, missing_branches):
    return json.dumps({'meta': {'branch_coverage': True}, 'files': {str(root / 'm.py'): {
        'executed_lines': executed, 'missing_lines': missing, 'excluded_lines': excluded,
        'executed_branches': executed_branches, 'missing_branches': missing_branches,
    }}})


def coverage_with_pragmas(root):
    return coverage_of(root, [1, 14, 15, 16], [], list(range(2, 14)), [[14, 15], [14, 16]], [])


def coverage_without_pragmas(root):
    return coverage_of(
        root, [1, 2, 4, 6, 8, 10, 12, 14, 15, 16], [3, 5, 7, 9, 11, 13], [],
        [[2, 4], [4, 6], [6, 8], [8, 10], [10, 12], [12, 14], [14, 15], [14, 16]],
        [[2, 3], [4, 5], [6, 7], [8, 9], [10, 11], [12, 13]])


class SilencerGateTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        self.comments = self.root / 'comment-debt.json'
        self.silencers = self.root / 'silencer-baseline.json'

    def put(self, name, text):
        (self.root / name).write_text(text)
        subprocess.run(['git', 'add', name], cwd=self.root, check=True)

    def gate(self, *argv):
        out = io.StringIO()
        return cd.main(list(argv), root=self.root, out=out), out.getvalue()

    def recorded(self):
        return json.loads(self.silencers.read_text())

    def crap_exit(self, coverage):
        (self.root / 'cov.json').write_text(coverage)
        argv = ['--lang', 'python', '--coverage-json', str(self.root / 'cov.json'), str(self.root / 'm.py')]
        with contextlib.redirect_stdout(io.StringIO()):
            return ratchet.exit_code(crap.gate(argv, self.root))

    def test_a_function_over_the_limit_hidden_by_pragmas_passes_crap_and_fails_the_comment_gate_until_the_silencers_are_recorded(self):
        self.put('m.py', SOURCE_WITH_PRAGMAS)
        self.comments.write_text('{}\n')
        self.silencers.write_text('{}\n')
        self.assertEqual(self.crap_exit(coverage_with_pragmas(self.root)), 0)
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('FAIL m.py: 6 silencers, baseline allows 0 — lines 2, 4, 6, 8, 10, 12', out)
        self.silencers.unlink()
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {'m.py': 6})
        self.assertEqual(self.gate()[0], 0)

    def test_the_same_function_without_its_pragmas_fails_crap(self):
        self.put('m.py', SOURCE_WITHOUT_PRAGMAS)
        self.assertEqual(self.crap_exit(coverage_without_pragmas(self.root)), 1)

    def test_the_silencers_are_not_recorded_as_comment_debt(self):
        self.put('m.py', SOURCE_WITH_PRAGMAS)
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(json.loads(self.comments.read_text()), {})

    def test_a_new_pragma_no_cover_added_after_recording_fails_and_names_its_line(self):
        self.put('m.py', f'def f(x):\n    if x:  {COVER}\n        return 1\n    return 0\n')
        self.gate('--update')
        self.put('m.py', f'def f(x):\n    if x:  {COVER}\n        return 1\n    if x > 1:  {COVER}\n        return 2\n    return 0\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('FAIL m.py: 2 silencers, baseline allows 1 — lines 2, 4', out)

    def test_update_will_not_record_a_new_silencer(self):
        self.put('m.py', 'x = 1\n')
        self.gate('--update')
        self.put('m.py', f'if x:  {COVER}\n    pass\n')
        code, out = self.gate('--update')
        self.assertEqual(code, 1)
        self.assertIn('It will not record a new silencer', out)
        self.assertEqual(self.recorded(), {})

    def test_a_silencer_that_is_removed_shows_as_paid_until_update_lowers_the_baseline(self):
        self.put('m.py', f'if x:  {COVER}\n    pass\nif y:  {COVER}\n    pass\n')
        self.gate('--update')
        self.put('m.py', f'if x:  {COVER}\n    pass\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('PAID m.py: 1 silencers, baseline still says 2', out)
        self.assertIn('silencer-baseline.json', out)
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {'m.py': 1})
        self.assertEqual(self.gate()[0], 0)

    def test_a_file_that_loses_every_silencer_leaves_the_baseline_on_update(self):
        self.put('m.py', f'if x:  {COVER}\n    pass\n')
        self.gate('--update')
        self.put('m.py', 'if x:\n    pass\n')
        self.gate('--update')
        self.assertEqual(self.recorded(), {})

    def test_the_check_refuses_to_run_without_a_silencer_baseline_and_says_where_it_looked(self):
        self.put('m.py', 'x = 1\n')
        self.comments.write_text('{}\n')
        code, out = self.gate()
        self.assertEqual(code, 2)
        self.assertIn('silencer-baseline.json', out)

    def test_a_pass_says_how_many_silencers_are_recorded(self):
        self.put('m.py', f'if x:  {COVER}\n    pass\n')
        self.gate('--update')
        self.assertIn('silencers: 1 in 1 files, none new', self.gate()[1])

    def test_a_silencer_in_a_file_that_does_not_parse_is_unmeasured_and_its_recorded_entry_stays(self):
        self.put('m.py', f'if x:  {COVER}\n    pass\n')
        self.gate('--update')
        self.put('m.py', 'def f(:\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn(f'UNMEASURED m.py: {cd.UNREAD_SILENCERS}', out)
        self.gate('--update')
        self.assertEqual(self.recorded(), {'m.py': 1})

    def test_the_status_and_the_report_name_the_silencers_beside_the_comment_total(self):
        self.put('m.py', f'# why\nif x:  {COVER}\n    pass\n')
        self.assertIn('# Silencers: 1 in 1 files\n', self.gate('--status')[1])
        self.assertIn('# Silencers: 1 in 1 files\n', self.gate('--report', 'python')[1])

    def test_the_status_and_the_report_add_no_silencer_line_when_there_is_none(self):
        self.put('m.py', '# why\nx = 1\n')
        self.assertNotIn('Silencers', self.gate('--status')[1])
        self.assertNotIn('Silencers', self.gate('--report', 'python')[1])

    def test_the_status_and_the_report_do_not_need_a_silencer_baseline(self):
        self.put('m.py', f'if x:  {COVER}\n    pass\n')
        self.assertEqual(self.gate('--status')[0], 0)
        self.assertEqual(self.gate('--report', 'python')[0], 0)

    def test_the_baseline_flag_moves_the_comment_baseline_and_leaves_the_silencer_baseline_at_the_root(self):
        other = self.root / 'tools' / 'debt.json'
        other.parent.mkdir()
        self.put('m.py', f'# why\nif x:  {COVER}\n    pass\n')
        self.assertEqual(self.gate('--update', '--baseline', str(other))[0], 0)
        self.assertEqual(json.loads(other.read_text()), {'m.py': 1})
        self.assertEqual(self.recorded(), {'m.py': 1})


class SetupRecordsSilencersTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        (self.root / 'm.py').write_text(f'# why\nif x:  {COVER}\n    pass\n')
        subprocess.run(['git', 'add', 'm.py'], cwd=self.root, check=True)

    def test_choosing_the_comment_gate_records_the_silencers_already_there_so_the_gate_then_passes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = setup_choices.main(['--go', '--choose', 'no-comments'], root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.root / 'silencer-baseline.json').read_text()), {'m.py': 1})
        self.assertEqual(json.loads((self.root / 'comment-debt.json').read_text()), {'m.py': 1})
        self.assertEqual(cd.main([], root=self.root, out=io.StringIO()), 0)
