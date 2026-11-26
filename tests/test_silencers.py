import contextlib
import dataclasses
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from quality_gates import comment_debt as cd
from quality_gates import crap, ratchet, setup_choices

PYTHON = cd.LANGUAGES['python']

WORD = 'prag' + 'ma'
COVER = f'# {WORD}: no cover'
BRANCH = f'# {WORD}: no branch'
FORMS_COVERAGE_PY_HONOURS = (
    COVER, BRANCH, f'#{WORD}: no cover', f'# {WORD}:no cover', f'# {WORD} no cover', f'# {WORD}: no  cover',
    f'# {WORD.upper()}: NO COVER', f'{COVER} - the other branch is tested elsewhere', f'# noqa  {COVER}',
    f'# type: ignore  {BRANCH}', f'{COVER}  # reason',
)
NOT_SILENCERS = (
    '# noqa', '# noqa: E402', '# type: ignore', '# type: ignore[valid-type]', '# fmt: off', '# fmt: on',
    '# fmt: skip', '# pragma: no mutate', '# pragma: cover', '# a plain comment', '# no cover',
)


def reading(source):
    return PYTHON.reading(source, ())


def silenced(text):
    return PYTHON.silencer(None, text)


class PythonSilencerReaderTest(unittest.TestCase):

    def test_every_form_coverage_py_honours_is_a_silencer_on_its_line(self):
        for text in FORMS_COVERAGE_PY_HONOURS:
            with self.subTest(text=text):
                self.assertEqual(silenced(f'x = 1\nif x:  {text}\n    pass\n'), (2,))

    def test_noqa_type_ignore_fmt_and_other_pragmas_are_not_silencers(self):
        for text in NOT_SILENCERS:
            with self.subTest(text=text):
                self.assertEqual(silenced(f'if x:  {text}\n    pass\n'), ())

    def test_a_silencer_is_read_from_the_physical_line_as_coverage_py_matches_it_so_lines_stay_in_step_after_a_form_feed(self):
        self.assertEqual(silenced(f'x = 1\n\x0c\nif x:  {COVER}\n    pass\n'), (3,))

    def test_every_language_reads_its_silencers_through_a_callable_taking_the_reading_and_the_source(self):
        for name, row in cd.LANGUAGES.items():
            with self.subTest(name):
                self.assertTrue(callable(row.silencer))


class PythonSilencerReadingTest(unittest.TestCase):

    def test_a_pragma_no_cover_and_a_pragma_no_branch_are_silencers_at_their_lines(self):
        source = f'def f(x):\n    if x:  {COVER}\n        return 1\n    while x:  {BRANCH}\n        x -= 1\n'
        self.assertEqual(reading(source).silencers, (2, 4))

    def test_a_silencer_is_not_also_a_comment_line(self):
        self.assertEqual(reading(f'if x:  {COVER}\n    pass\n').debt, {})

    def test_a_silencer_that_carries_prose_is_a_silencer_and_not_also_a_comment_line(self):
        found = reading(f'if x:  {COVER} - tested by hand\n    pass\n')
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_a_comment_beside_a_silencer_on_another_line_stays_a_comment_line(self):
        found = reading(f'# why\nif x:  {COVER}\n    pass\n')
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1]))

    def test_noqa_type_ignore_and_fmt_are_neither_comment_debt_nor_silencers(self):
        source = 'import a  # noqa: E402\nx = 1  # type: ignore[valid-type]\ny = [1,2]  # fmt: skip\n# fmt: off\n# fmt: on\n'
        found = reading(source)
        self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_a_pragma_inside_a_string_is_a_silencer_because_coverage_py_matches_the_raw_line(self):
        found = reading(f'MARKER = "{COVER}"\n')
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_a_docstring_line_holding_a_pragma_is_a_silencer_and_not_also_a_string_comment_line(self):
        found = reading(f'def f():\n    """One.\n    {COVER}\n    """\n    return 1\n')
        self.assertEqual((found.silencers, list(found.debt)), ((3,), [2, 4]))

    def test_a_pragma_for_a_tool_that_is_not_ours_stays_a_comment_line(self):
        found = reading('x = 1  # pragma: no mutate\n')
        self.assertEqual((found.silencers, list(found.debt)), ((), [1]))

    def test_a_docstring_is_still_comment_debt_beside_a_silencer(self):
        found = reading(f'def f(x):\n    """One."""\n    if x:  {COVER}\n        return 1\n')
        self.assertEqual((found.silencers, list(found.debt)), ((3,), [2]))



class SharedReaderSilencerTest(unittest.TestCase):

    def test_a_comment_matching_a_languages_silencer_pattern_is_a_silencer_and_not_a_comment_line_in_a_language_the_shared_reader_reads(self):
        row = dataclasses.replace(cd.LANGUAGES['typescript'], silencer=cd.in_comments(re.compile(r'//\s*silence\b')))
        found = row.reading('// why\nf(); // silence me\nlet s = "// silence";\n', ())
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1]))

    def test_a_silencer_callable_is_handed_the_readers_code_with_strings_and_comments_blanked(self):
        seen = []
        row = dataclasses.replace(cd.LANGUAGES['rust'], silencer=lambda reading, source: seen.append(reading.blanked) or ())
        row.reading('let s = "x"; // c\n', ())
        self.assertEqual(len(seen), 1)
        self.assertIn('let s', seen[0])
        self.assertNotIn('"x"', seen[0])
        self.assertNotIn('// c', seen[0])


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


class SilencerGateCase(unittest.TestCase):

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



class SilencerGateTest(SilencerGateCase):

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

    def test_a_silencer_baseline_that_does_not_read_stops_the_run_before_the_comment_baseline_is_written(self):
        self.put('m.py', f'# one\n# two\nif x:  {COVER}\n    pass\n')
        self.gate('--update')
        self.put('m.py', f'# one\nif x:  {COVER}\n    pass\n')
        self.silencers.write_text('[]\n')
        before = self.comments.read_text()
        code, out = self.gate('--update')
        self.assertEqual(code, 2)
        self.assertIn('bad baseline', out)
        self.assertIn('silencer-baseline.json', out)
        self.assertEqual(self.comments.read_text(), before)

    def test_a_silencer_baseline_that_is_missing_stops_the_check_before_any_comment_output(self):
        self.put('m.py', '# one\nx = 1\n')
        self.comments.write_text('{}\n')
        code, out = self.gate()
        self.assertEqual(code, 2)
        self.assertNotIn('FAIL', out)

    def test_an_unreadable_file_is_named_with_the_same_cause_wording_for_comments_and_silencers(self):
        self.assertTrue(cd.UNREAD.startswith(cd.UNREAD_CAUSE))
        self.assertTrue(cd.UNREAD_SILENCERS.startswith(cd.UNREAD_CAUSE))

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

    def test_switching_on_a_second_comment_language_records_the_silencers_of_the_language_already_chosen_when_there_is_no_silencer_baseline_yet(self):
        with contextlib.redirect_stdout(io.StringIO()):
            setup_choices.main(['--go', '--choose', 'no-comments'], root=self.root)
        (self.root / 'silencer-baseline.json').unlink()
        (self.root / 'main.rs').write_text('fn main() {}\n')
        with contextlib.redirect_stdout(io.StringIO()):
            code = setup_choices.main(['--go', '--choose', 'no-comments-rust'], root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.root / 'silencer-baseline.json').read_text()), {'m.py': 1})
        self.assertEqual(cd.main([], root=self.root, out=io.StringIO()), 0)

    def test_switching_on_a_second_comment_language_leaves_the_recorded_silencers_of_the_first_as_they_were(self):
        with contextlib.redirect_stdout(io.StringIO()):
            setup_choices.main(['--go', '--choose', 'no-comments'], root=self.root)
        (self.root / 'main.rs').write_text('fn main() {}\n')
        with contextlib.redirect_stdout(io.StringIO()):
            setup_choices.main(['--go', '--choose', 'no-comments-rust'], root=self.root)
        self.assertEqual(json.loads((self.root / 'silencer-baseline.json').read_text()), {'m.py': 1})

    def test_choosing_the_comment_gate_records_the_silencers_already_there_so_the_gate_then_passes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = setup_choices.main(['--go', '--choose', 'no-comments'], root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads((self.root / 'silencer-baseline.json').read_text()), {'m.py': 1})
        self.assertEqual(json.loads((self.root / 'comment-debt.json').read_text()), {'m.py': 1})
        self.assertEqual(cd.main([], root=self.root, out=io.StringIO()), 0)


SWIFT = cd.LANGUAGES['swift']
RULES = 'cyclomatic_complexity force_cast'


def swift_reading(source):
    return SWIFT.reading(source, ())


def swift_with(comment):
    return f'{comment}\nfunc f(_ x: Int) -> Int {{\n    return x\n}}\n'


class SwiftSilencerReaderTest(unittest.TestCase):

    def silenced_by(self, comment):
        found = swift_reading(swift_with(comment))
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_a_plain_swiftlint_disable_is_a_silencer(self):
        self.silenced_by('// swiftlint:disable')

    def test_a_plain_swiftlint_disable_naming_rules_is_a_silencer(self):
        self.silenced_by(f'// swiftlint:disable {RULES}')

    def test_a_swiftlint_disable_next_is_a_silencer(self):
        self.silenced_by('// swiftlint:disable:next')

    def test_a_swiftlint_disable_next_naming_rules_is_a_silencer(self):
        self.silenced_by(f'// swiftlint:disable:next {RULES}')

    def test_a_swiftlint_disable_this_is_a_silencer(self):
        self.silenced_by('// swiftlint:disable:this')

    def test_a_swiftlint_disable_this_naming_rules_is_a_silencer(self):
        self.silenced_by(f'// swiftlint:disable:this {RULES}')

    def test_a_swiftlint_disable_previous_is_a_silencer(self):
        self.silenced_by('// swiftlint:disable:previous')

    def test_a_swiftlint_disable_previous_naming_rules_is_a_silencer(self):
        self.silenced_by(f'// swiftlint:disable:previous {RULES}')

    def test_a_swiftlint_disable_naming_a_rule_other_than_complexity_is_still_a_silencer(self):
        self.silenced_by('// swiftlint:disable force_cast')

    def test_a_swiftlint_disable_that_carries_prose_is_a_silencer_and_not_also_a_comment_line(self):
        self.silenced_by('// swiftlint:disable force_cast, the API returns Any')

    def test_a_swiftlint_disable_in_a_block_comment_is_comment_debt_and_not_a_silencer(self):
        for comment in ('/* swiftlint:disable:next cyclomatic_complexity */', '/* swiftlint:disable */',
                        '/* swiftlint:disable cyclomatic_complexity\n   the reason */'):
            with self.subTest(comment=comment):
                found = swift_reading(swift_with(comment))
                self.assertEqual((found.silencers, set(found.debt.values())), ((), {'block'}))

    def test_a_swiftlint_disable_in_a_doc_comment_is_comment_debt_and_not_a_silencer(self):
        for comment in ('/// swiftlint:disable cyclomatic_complexity', '/** swiftlint:disable:next force_cast */'):
            with self.subTest(comment=comment):
                found = swift_reading(swift_with(comment))
                self.assertEqual((found.silencers, set(found.debt.values())), ((), {'doc'}))

    def test_a_trailing_swiftlint_disable_this_is_a_silencer_on_its_own_line(self):
        found = swift_reading('func f() {  // swiftlint:disable:this cyclomatic_complexity\n}\n')
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def exempt(self, form):
        for comment in (f'// swiftlint:{form}', f'// swiftlint:{form} {RULES}'):
            with self.subTest(comment=comment):
                found = swift_reading(swift_with(comment))
                self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_a_plain_swiftlint_enable_is_neither_a_comment_line_nor_a_silencer(self):
        self.exempt('enable')

    def test_a_swiftlint_enable_next_is_neither_a_comment_line_nor_a_silencer(self):
        self.exempt('enable:next')

    def test_a_swiftlint_enable_this_is_neither_a_comment_line_nor_a_silencer(self):
        self.exempt('enable:this')

    def test_a_swiftlint_enable_previous_is_neither_a_comment_line_nor_a_silencer(self):
        self.exempt('enable:previous')

    def test_a_swiftlint_disable_inside_a_string_literal_is_neither_a_comment_line_nor_a_silencer(self):
        source = ('let a = "// swiftlint:disable"\nlet b = "x \\(y) // swiftlint:disable:next force_cast"\n'
                  'let c = """\n  // swiftlint:disable\n  """\nlet d = #"// swiftlint:disable"#\n')
        found = swift_reading(source)
        self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_a_word_that_only_starts_like_swiftlint_disable_is_not_a_silencer(self):
        found = swift_reading('// swiftlint:disabled\n// swiftlint\n')
        self.assertEqual((found.silencers, list(found.debt)), ((), [1, 2]))

    def test_a_comment_beside_a_swiftlint_disable_on_another_line_stays_a_comment_line(self):
        found = swift_reading('// why\n// swiftlint:disable:next force_cast\nlet a = b as! C\n')
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1]))


def swift_function_over_the_limit(marker):
    ifs = ''.join(f'    if x == {n} {{ return {n} }}\n' for n in range(1, 10))
    return f'{marker}func f(_ x: Int) -> Int {{\n{ifs}    return 0\n}}\n'


DISABLE_NEXT = '// swiftlint:disable:next cyclomatic_complexity\n'
SWIFTLINT_CONFIG = 'only_rules:\n  - cyclomatic_complexity\ncyclomatic_complexity:\n  warning: 8\n  error: 8\n'


class SwiftSilencerGateTest(SilencerGateCase):

    def setUp(self):
        super().setUp()
        (self.root / 'quality-gates.json').write_text(json.dumps({
            'format_version': 1, 'languages': ['swift'], 'exclude': [],
            'components': {'chosen': ['no-comments-swift'], 'declined': []}, 'commit_time_limit_seconds': 2,
            'settings': {'no-comments': {'exclude': [], 'conventions': []}},
        }))

    def swiftlint_exit(self):
        (self.root / '.swiftlint.yml').write_text(SWIFTLINT_CONFIG)
        run = subprocess.run(['swiftlint', 'lint', '--quiet', '--config', '.swiftlint.yml', 'A.swift'],
                             cwd=self.root, capture_output=True, text=True)
        return run.returncode

    def test_a_function_over_the_limit_hidden_by_swiftlint_disable_next_fails_the_comment_gate_until_it_is_recorded(self):
        self.put('A.swift', swift_function_over_the_limit(DISABLE_NEXT))
        self.comments.write_text('{}\n')
        self.silencers.write_text('{}\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('FAIL A.swift: 1 silencers, baseline allows 0 — lines 1', out)
        self.silencers.unlink()
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {'A.swift': 1})
        self.assertEqual(self.gate()[0], 0)

    @unittest.skipUnless(shutil.which('swiftlint'), 'swiftlint is not installed')
    def test_swiftlint_passes_the_function_over_the_limit_that_swiftlint_disable_next_hides(self):
        self.put('A.swift', swift_function_over_the_limit(DISABLE_NEXT))
        self.assertEqual(self.swiftlint_exit(), 0)

    @unittest.skipUnless(shutil.which('swiftlint'), 'swiftlint is not installed')
    def test_the_same_function_without_its_swiftlint_disable_fails_swiftlint(self):
        self.put('A.swift', swift_function_over_the_limit(''))
        self.assertEqual(self.swiftlint_exit(), 2)

    def test_the_swiftlint_disable_lines_are_not_recorded_as_comment_debt(self):
        self.put('A.swift', swift_function_over_the_limit(DISABLE_NEXT))
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(json.loads(self.comments.read_text()), {})

    def test_a_new_swiftlint_disable_added_after_recording_fails_and_names_its_line(self):
        self.put('A.swift', swift_function_over_the_limit(DISABLE_NEXT))
        self.gate('--update')
        self.put('A.swift', swift_function_over_the_limit(DISABLE_NEXT) + DISABLE_NEXT + 'let a = b as! C\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('FAIL A.swift: 2 silencers, baseline allows 1 — lines 1, 14', out)

    def test_update_will_not_record_a_new_swiftlint_disable(self):
        self.put('A.swift', 'let a = 1\n')
        self.gate('--update')
        self.put('A.swift', DISABLE_NEXT + 'let a = b as! C\n')
        code, out = self.gate('--update')
        self.assertEqual(code, 1)
        self.assertIn('It will not record a new silencer', out)
        self.assertEqual(self.recorded(), {})

    def test_a_swiftlint_disable_that_is_removed_shows_as_paid_until_update_lowers_the_baseline(self):
        self.put('A.swift', DISABLE_NEXT + 'let a = b as! C\n' + DISABLE_NEXT + 'let d = e as! F\n')
        self.gate('--update')
        self.put('A.swift', DISABLE_NEXT + 'let a = b as! C\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('PAID A.swift: 1 silencers, baseline still says 2', out)
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {'A.swift': 1})
        self.assertEqual(self.gate()[0], 0)

    def test_swiftlint_enable_and_a_swiftlint_disable_in_a_string_literal_leave_both_baselines_empty(self):
        self.put('A.swift', 'let a = "// swiftlint:disable"\n// swiftlint:enable force_cast\n')
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual((self.recorded(), json.loads(self.comments.read_text())), ({}, {}))


RUST = cd.LANGUAGES['rust']
COMPLEXITY = 'clippy::cognitive_complexity'
LENGTH = 'clippy::too_many_lines'


def rust_reading(source):
    return RUST.reading(source, ())


def rust_with(attribute):
    return f'{attribute}\nfn f(x: i32) -> i32 {{\n    x\n}}\n'


class RustSilencerReaderTest(unittest.TestCase):

    def silenced_at(self, attribute, lines=(1,)):
        found = rust_reading(rust_with(attribute))
        self.assertEqual((found.silencers, found.debt), (lines, {}))

    def silences_nothing(self, source):
        found = rust_reading(source)
        self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_an_outer_allow_of_cognitive_complexity_is_a_silencer(self):
        self.silenced_at(f'#[allow({COMPLEXITY})]')

    def test_an_outer_allow_of_too_many_lines_is_a_silencer(self):
        self.silenced_at(f'#[allow({LENGTH})]')

    def test_an_inner_allow_of_cognitive_complexity_is_a_silencer(self):
        self.silenced_at(f'#![allow({COMPLEXITY})]')

    def test_an_inner_allow_of_too_many_lines_is_a_silencer(self):
        self.silenced_at(f'#![allow({LENGTH})]')

    def test_an_outer_allow_of_cognitive_complexity_inside_a_longer_list_is_a_silencer(self):
        self.silenced_at(f'#[allow(dead_code, {COMPLEXITY}, unused_mut)]')

    def test_an_outer_allow_of_too_many_lines_inside_a_longer_list_is_a_silencer(self):
        self.silenced_at(f'#[allow(dead_code, {LENGTH})]')

    def test_an_inner_allow_of_cognitive_complexity_inside_a_longer_list_is_a_silencer(self):
        self.silenced_at(f'#![allow(dead_code, {COMPLEXITY})]')

    def test_an_inner_allow_of_too_many_lines_inside_a_longer_list_is_a_silencer(self):
        self.silenced_at(f'#![allow({LENGTH}, dead_code)]')

    def test_one_attribute_naming_both_lints_is_one_silencer(self):
        self.silenced_at(f'#[allow({COMPLEXITY}, {LENGTH})]')

    def test_two_attributes_on_one_line_are_two_silencers(self):
        found = rust_reading(f'#[allow({COMPLEXITY})] #[allow({LENGTH})] fn f() {{}}\n')
        self.assertEqual(found.silencers, (1, 1))

    def test_an_attribute_split_over_several_lines_is_found_at_its_first_line(self):
        self.silenced_at(f'#[allow(\n    dead_code,\n    {LENGTH}\n)]')

    def test_two_split_attributes_are_each_found_at_their_own_first_line(self):
        source = f'#[allow(\n    {LENGTH}\n)]\nfn a() {{}}\n#[allow(\n    {COMPLEXITY}\n)]\nfn b() {{}}\n'
        self.assertEqual(rust_reading(source).silencers, (1, 5))

    def test_a_space_between_the_hash_and_the_bracket_still_makes_a_silencer(self):
        self.silenced_at(f'# [allow({LENGTH})]')

    def test_a_space_around_the_path_separator_still_makes_a_silencer(self):
        self.silenced_at('#[allow(clippy :: too_many_lines)]')

    def test_a_trailing_comma_and_a_reason_still_make_a_silencer(self):
        self.silenced_at(f'#[allow({LENGTH}, {COMPLEXITY}, reason = "why",)]')

    def test_an_allow_inside_cfg_attr_is_a_silencer(self):
        self.silenced_at(f'#[cfg_attr(test, allow({COMPLEXITY}))]')

    def test_an_allow_nested_in_two_cfg_attrs_is_a_silencer(self):
        self.silenced_at(f'#[cfg_attr(a, cfg_attr(b, allow(dead_code, {LENGTH})))]')

    def test_an_allow_after_another_allow_in_one_cfg_attr_is_a_silencer(self):
        self.silenced_at(f'#[cfg_attr(a, allow(dead_code), allow({LENGTH}))]')

    def test_an_expect_of_either_lint_is_a_silencer_because_clippy_then_stops_reporting_it(self):
        self.silenced_at(f'#[expect({COMPLEXITY})]')
        self.silenced_at(f'#![expect(dead_code, {LENGTH})]')

    def test_an_allow_on_an_impl_or_a_module_that_holds_the_functions_is_a_silencer(self):
        found = rust_reading(f'#[allow({LENGTH})]\nimpl A {{\n    fn f(&self) {{}}\n}}\n#![allow({COMPLEXITY})]\n')
        self.assertEqual(found.silencers, (1, 5))

    def test_a_lint_name_inside_a_string_is_not_a_silencer(self):
        self.silences_nothing(f'let a = "#[allow({LENGTH})]";\nlet b = "#![allow({COMPLEXITY})]";\n')

    def test_a_lint_name_inside_a_raw_string_is_not_a_silencer(self):
        self.silences_nothing(f'let a = r#"#[allow({LENGTH})]"#;\nlet b = r##"\n#![allow({COMPLEXITY})]\n"##;\n')

    def test_a_lint_name_inside_a_string_argument_of_another_attribute_is_not_a_silencer(self):
        self.silences_nothing(f'#[cfg(feature = "allow({LENGTH})")]\nfn f() {{}}\n#[doc(alias = "allow({COMPLEXITY})")]\nfn g() {{}}\n')

    def test_a_lint_name_inside_a_comment_is_not_a_silencer_and_the_comment_stays_debt(self):
        for comment in (f'// #[allow({LENGTH})]', f'/* #[allow({COMPLEXITY})] */', f'/* a /* #[allow({LENGTH})] */ b */',
                        f'/// #[allow({LENGTH})]', f'//! #![allow({COMPLEXITY})]', f'/** #[allow({LENGTH})] */'):
            with self.subTest(comment=comment):
                found = rust_reading(f'{comment}\nfn f() {{}}\n')
                self.assertEqual((found.silencers, list(found.debt)), ((), [1]))

    def test_an_allow_for_any_other_lint_is_not_a_silencer(self):
        for attribute in ('#[allow(dead_code)]', '#[allow(clippy::needless_return)]', '#[allow(unused_mut, clippy::len_zero)]',
                          '#![allow(clippy::too_many_arguments)]', '#[allow(clippy::type_complexity)]', '#[allow()]'):
            with self.subTest(attribute=attribute):
                self.silences_nothing(rust_with(attribute))

    def test_the_setup_attributes_that_deny_or_warn_are_not_silencers(self):
        for attribute in (f'#![deny({COMPLEXITY})]', f'#![deny({LENGTH})]', f'#[warn({LENGTH})]', f'#![forbid({COMPLEXITY})]',
                          f'#[cfg_attr(test, deny({LENGTH}), allow(dead_code))]'):
            with self.subTest(attribute=attribute):
                self.silences_nothing(rust_with(attribute))

    def test_a_name_that_only_starts_like_a_complexity_lint_is_not_a_silencer(self):
        for attribute in ('#[allow(clippy::too_many_lines_extra)]', '#[allow(clippy::cognitive_complexity2)]',
                          f'#[allow(other::{LENGTH})]', '#[allow(too_many_lines)]'):
            with self.subTest(attribute=attribute):
                self.silences_nothing(rust_with(attribute))

    def test_a_comment_beside_an_allow_on_another_line_stays_a_comment_line(self):
        found = rust_reading(f'// why\n#[allow({LENGTH})]\nfn f() {{}}\n')
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1]))

    def test_an_allow_is_not_comment_debt(self):
        self.assertEqual(rust_reading(f'#[allow({LENGTH})]\nfn f() {{}}\n').debt, {})


def rust_function_over_the_limit(marker):
    ifs = ''.join(f'    if x == {n} {{ total += {n}; }}\n' for n in range(1, 13))
    return f'{marker}fn f(x: i32) -> i32 {{\n    let mut total = 0;\n{ifs}    total\n}}\n'


ALLOW_COMPLEXITY = f'#[allow({COMPLEXITY})]\n'
DENY_BOTH = f'#![deny({COMPLEXITY})]\n#![deny({LENGTH})]\n'
CLIPPY_CONFIG = 'cognitive-complexity-threshold = 10\ntoo-many-lines-threshold = 25\n'
CARGO_MANIFEST = '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n'


def clippy_is_installed():
    if not shutil.which('cargo'):
        return False
    return subprocess.run(['cargo', 'clippy', '--version'], capture_output=True).returncode == 0


class RustSilencerGateTest(SilencerGateCase):

    def setUp(self):
        super().setUp()
        (self.root / 'quality-gates.json').write_text(json.dumps({
            'format_version': 1, 'languages': ['rust'], 'exclude': [],
            'components': {'chosen': ['no-comments-rust'], 'declined': []}, 'commit_time_limit_seconds': 2,
            'settings': {'no-comments': {'exclude': [], 'conventions': []}},
        }))

    def clippy_exit(self, function):
        (self.root / 'src').mkdir(exist_ok=True)
        (self.root / 'Cargo.toml').write_text(CARGO_MANIFEST)
        (self.root / 'clippy.toml').write_text(CLIPPY_CONFIG)
        (self.root / 'src' / 'main.rs').write_text(f'{DENY_BOTH}fn main() {{}}\n{function}')
        run = subprocess.run(['cargo', 'clippy', '--offline', '--quiet'], cwd=self.root, capture_output=True, text=True)
        return run.returncode

    def test_a_function_over_the_limit_hidden_by_an_allow_of_cognitive_complexity_fails_the_comment_gate_until_it_is_recorded(self):
        self.put('lib.rs', rust_function_over_the_limit(ALLOW_COMPLEXITY))
        self.comments.write_text('{}\n')
        self.silencers.write_text('{}\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('FAIL lib.rs: 1 silencers, baseline allows 0 — lines 1', out)
        self.silencers.unlink()
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {'lib.rs': 1})
        self.assertEqual(self.gate()[0], 0)

    @unittest.skipUnless(clippy_is_installed(), 'cargo clippy is not installed')
    def test_clippy_passes_the_function_over_the_limit_that_an_allow_of_cognitive_complexity_hides(self):
        self.assertEqual(self.clippy_exit(rust_function_over_the_limit(ALLOW_COMPLEXITY)), 0)

    @unittest.skipUnless(clippy_is_installed(), 'cargo clippy is not installed')
    def test_the_same_function_without_its_allow_fails_clippy(self):
        self.assertEqual(self.clippy_exit(rust_function_over_the_limit('')), 101)

    @unittest.skipUnless(clippy_is_installed(), 'cargo clippy is not installed')
    def test_clippy_honours_the_expect_a_cfg_attr_and_a_split_attribute_the_gate_counts(self):
        for marker in (f'#[expect({COMPLEXITY})]\n', f'#[cfg_attr(all(), allow({COMPLEXITY}))]\n',
                       f'#[allow(\n    {COMPLEXITY}\n)]\n', '# [allow(clippy :: cognitive_complexity)]\n'):
            with self.subTest(marker=marker):
                self.assertEqual(self.clippy_exit(rust_function_over_the_limit(marker)), 0)
                self.assertEqual(rust_reading(marker + 'fn f() {}\n').silencers, (1,))

    def test_the_allow_lines_are_not_recorded_as_comment_debt(self):
        self.put('lib.rs', rust_function_over_the_limit(ALLOW_COMPLEXITY))
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(json.loads(self.comments.read_text()), {})

    def test_a_new_allow_added_after_recording_fails_and_names_its_line(self):
        self.put('lib.rs', rust_function_over_the_limit(ALLOW_COMPLEXITY))
        self.gate('--update')
        self.put('lib.rs', rust_function_over_the_limit(ALLOW_COMPLEXITY) + f'#[allow({LENGTH})]\nfn g() {{}}\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('FAIL lib.rs: 2 silencers, baseline allows 1 — lines 1, 18', out)

    def test_update_will_not_record_a_new_allow(self):
        self.put('lib.rs', 'fn g() {}\n')
        self.gate('--update')
        self.put('lib.rs', ALLOW_COMPLEXITY + 'fn g() {}\n')
        code, out = self.gate('--update')
        self.assertEqual(code, 1)
        self.assertIn('It will not record a new silencer', out)
        self.assertEqual(self.recorded(), {})

    def test_an_allow_that_is_removed_shows_as_paid_until_update_lowers_the_baseline(self):
        self.put('lib.rs', ALLOW_COMPLEXITY + 'fn g() {}\n' + f'#![allow({LENGTH})]\n')
        self.gate('--update')
        self.put('lib.rs', ALLOW_COMPLEXITY + 'fn g() {}\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn('PAID lib.rs: 1 silencers, baseline still says 2', out)
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {'lib.rs': 1})
        self.assertEqual(self.gate()[0], 0)

    def test_an_allow_for_another_lint_and_a_lint_name_in_a_string_leave_both_baselines_empty(self):
        self.put('lib.rs', f'#[allow(dead_code)]\nfn g() {{}}\nconst A: &str = r#"#[allow({LENGTH})]"#;\n')
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual((self.recorded(), json.loads(self.comments.read_text())), ({}, {}))

    def test_an_allow_goes_uncounted_while_the_rust_comment_row_is_not_chosen(self):
        (self.root / 'quality-gates.json').write_text(json.dumps({
            'format_version': 1, 'languages': ['python', 'rust'], 'exclude': [],
            'components': {'chosen': ['no-comments'], 'declined': ['no-comments-rust']}, 'commit_time_limit_seconds': 2,
            'settings': {'no-comments': {'exclude': [], 'conventions': []}},
        }))
        self.put('lib.rs', rust_function_over_the_limit(ALLOW_COMPLEXITY))
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {})

    def test_the_status_names_the_allow_lines_beside_the_comment_total(self):
        self.put('lib.rs', f'// why\n#[allow({LENGTH})]\nfn g() {{}}\n')
        self.assertIn('# Silencers: 1 in 1 files\n', self.gate('--status')[1])
        self.assertIn('# Silencers: 1 in 1 files\n', self.gate('--report', 'rust')[1])


class SetupRecordsRustSilencersTest(unittest.TestCase):

    def test_choosing_the_rust_comment_row_records_the_allow_lines_already_there_so_the_gate_then_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / 'lib.rs').write_text(f'#[allow({COMPLEXITY})]\nfn g() {{}}\n')
            subprocess.run(['git', 'add', 'lib.rs'], cwd=root, check=True)
            with contextlib.redirect_stdout(io.StringIO()):
                code = setup_choices.main(['--go', '--choose', 'no-comments-rust'], root=root)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((root / 'silencer-baseline.json').read_text()), {'lib.rs': 1})
            self.assertEqual(cd.main([], root=root, out=io.StringIO()), 0)
