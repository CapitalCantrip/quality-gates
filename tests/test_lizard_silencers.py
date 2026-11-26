import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from quality_gates import comment_debt as cd
from quality_gates import complexity_scan, crap, ratchet, setup_choices
from quality_gates import quality_check as qc
from test_silencers import SilencerGateCase

TYPESCRIPT = cd.LANGUAGES['typescript']
SWIFT = cd.LANGUAGES['swift']
PYTHON = cd.LANGUAGES['python']

FORGIVE = '// #lizard forgive\n'
TS_SUFFIXES = ('ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs')

HONOURED = (
    '// #lizard forgive', '//#lizard forgive', '//    #lizard forgive', '//\t#lizard forgive',
    '// #lizard forgive', '// #lizard forgive: the reason', '// #lizard forgives', '// #lizard forgiveness',
    '// #lizard forgive(cyclomatic_complexity)', '// #lizard forgives (cyclomatic_complexity)',
    '// #lizard forgive  global', '/* #lizard forgive */', '/*#lizard forgive*/', '/*\n   #lizard forgive\n*/',
    '/*\n\n#lizard forgive */',
)
NOT_HONOURED = (
    '/** #lizard forgive */', '/// #lizard forgive', '//// #lizard forgive', '// #Lizard forgive',
    '// #LIZARD FORGIVE', '// #lizard  forgive', '// # lizard forgive', '// lizard forgive', '// see #lizard forgive',
    '/* why\n #lizard forgive */', '/* why #lizard forgive */', '// #lizard forgives(cyclomatic_complexity)',
    '// #lizard forgives(cyclomatic_complexity, nloc)', '/* #lizard forgives(\n cyclomatic_complexity) */',
    '// #lizard forgives(', '// #lizard forgive global', '// #lizard forgive globally',
)


def ts_function(marker=''):
    ifs = ''.join(f'  if (x === {n}) {{ return {n}; }}\n' for n in range(1, 10))
    return f'{marker}export function f(x: number): number {{\n{ifs}  return 0;\n}}\n'


def swift_function(marker=''):
    ifs = ''.join(f'    if x == {n} {{ return {n} }}\n' for n in range(1, 10))
    return f'{marker}func f(_ x: Int) -> Int {{\n{ifs}    return 0\n}}\n'


def python_function(marker=''):
    ifs = ''.join(f'    if x == {n}:\n        return {n}\n' for n in range(1, 10))
    return f'{marker}def f(x):\n{ifs}    return 0\n'


def lizard_sees(text, suffix, language):
    with tempfile.TemporaryDirectory() as folder:
        file = Path(folder, f'm.{suffix}')
        file.write_text(text, encoding='utf-8')
        return [fn.name for fn in complexity_scan.count_functions(complexity_scan.Sources([file], []), language).functions]


def lizard_forgives(text, suffix, language):
    return lizard_sees(text, suffix, language) == []


class LizardForgiveFormsTest(unittest.TestCase):

    def test_every_form_lizard_honours_is_a_silencer_and_lizard_drops_the_function_behind_it_in_every_typescript_and_javascript_file_kind(self):
        for suffix in TS_SUFFIXES:
            for comment in HONOURED:
                with self.subTest(suffix=suffix, comment=comment):
                    text = ts_function(comment + '\n')
                    self.assertTrue(lizard_forgives(text, suffix, 'typescript'))
                    self.assertTrue(TYPESCRIPT.reading(text, ()).silencers)

    def test_every_form_lizard_honours_is_a_silencer_and_lizard_drops_the_function_behind_it_in_swift(self):
        for comment in HONOURED:
            with self.subTest(comment=comment):
                text = swift_function(comment + '\n')
                self.assertTrue(lizard_forgives(text, 'swift', 'swift'))
                self.assertTrue(SWIFT.reading(text, ()).silencers)

    def test_a_form_lizard_does_not_honour_is_a_comment_line_and_no_silencer_and_lizard_keeps_the_function_in_every_typescript_and_javascript_file_kind(self):
        for suffix in TS_SUFFIXES:
            for comment in NOT_HONOURED:
                with self.subTest(suffix=suffix, comment=comment):
                    text = ts_function(comment + '\n')
                    found = TYPESCRIPT.reading(text, ())
                    self.assertEqual(lizard_sees(text, suffix, 'typescript'), ['f'])
                    self.assertEqual((found.silencers, bool(found.debt)), ((), True))

    def test_a_form_lizard_does_not_honour_is_a_comment_line_and_no_silencer_and_lizard_keeps_the_function_in_swift(self):
        for comment in NOT_HONOURED:
            with self.subTest(comment=comment):
                text = swift_function(comment + '\n')
                found = SWIFT.reading(text, ())
                self.assertEqual(lizard_sees(text, 'swift', 'swift'), ['f'])
                self.assertEqual((found.silencers, bool(found.debt)), ((), True))

    def test_a_forgive_inside_a_nested_swift_block_comment_is_not_a_silencer_because_lizard_ends_the_comment_at_the_first_close(self):
        for comment in ('/* a /* b */ #lizard forgive */', '/* /* b */ #lizard forgive */'):
            with self.subTest(comment=comment):
                text = swift_function(comment + '\n')
                self.assertEqual(lizard_sees(text, 'swift', 'swift'), ['f'])
                self.assertEqual(SWIFT.reading(text, ()).silencers, ())

    def test_a_forgive_that_opens_a_swift_block_comment_holding_a_nested_one_is_a_silencer(self):
        text = swift_function('/* #lizard forgive /* b */ */\n')
        self.assertTrue(lizard_forgives(text, 'swift', 'swift'))
        self.assertEqual(SWIFT.reading(text, ()).silencers, (1,))

    def test_a_forgive_in_a_string_literal_is_neither_a_silencer_nor_a_comment_line_and_lizard_keeps_the_function(self):
        for literal in ('"// #lizard forgive"', "'// #lizard forgive'", '`// #lizard forgive`', '/#lizard forgive/'):
            with self.subTest(literal=literal):
                text = f'export const s = {literal};\n' + ts_function()
                found = TYPESCRIPT.reading(text, ())
                self.assertEqual(lizard_sees(text, 'ts', 'typescript'), ['f'])
                self.assertEqual((found.silencers, found.debt), ((), {}))
        for literal in ('"// #lizard forgive"', '#"// #lizard forgive"#', '"""\n// #lizard forgive\n"""'):
            with self.subTest(literal=literal):
                text = f'let s = {literal}\n' + swift_function()
                found = SWIFT.reading(text, ())
                self.assertEqual(lizard_sees(text, 'swift', 'swift'), ['f'])
                self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_a_forgive_after_a_division_the_reader_takes_for_a_regex_start_is_missed_where_lizard_honours_it_a_known_gap_of_260(self):
        for line in ('return of / 2;', 'const y = await / 2;', 'const y = a.b<c> / 2;'):
            with self.subTest(line=line):
                text = f'{line} // #lizard forgive\n' + ts_function()
                found = TYPESCRIPT.reading(text, ())
                self.assertTrue(lizard_forgives(text, 'ts', 'typescript'))
                self.assertEqual((found.silencers, found.debt), ((), {}))

    def test_a_forgive_the_reader_counts_and_lizard_ignores_is_a_known_over_count_listed_in_the_addendum(self):
        cases = (
            ('tsx', TYPESCRIPT, 'export const E = () => <p>/* #lizard forgive */</p>;\n' + ts_function(), 'typescript'),
            ('tsx', TYPESCRIPT, 'export const E = () => <p>// #lizard forgive</p>;\n' + ts_function(), 'typescript'),
            ('ts', TYPESCRIPT, 'const s = `${ // #lizard forgive\n 1 }`;\n' + ts_function(), 'typescript'),
            ('ts', TYPESCRIPT, '//\u2028#lizard forgive\n' + ts_function(), 'typescript'),
            ('ts', TYPESCRIPT, '//\u2029#lizard forgive\n' + ts_function(), 'typescript'),
            ('ts', TYPESCRIPT, '//\r#lizard forgive\n' + ts_function(), 'typescript'),
            ('swift', SWIFT, '//\r#lizard forgive\n' + swift_function(), 'swift'),
            ('swift', SWIFT, 'let r = #/a// #lizard forgive/#\n' + swift_function(), 'swift'),
            ('ts', TYPESCRIPT, '// #lizard forgive\nconst g = (a, b);\n' + ts_function(), 'typescript'),
        )
        for suffix, language, text, name in cases:
            with self.subTest(text=text):
                self.assertEqual(lizard_sees(text, suffix, name)[-1], 'f')
                self.assertEqual(len(language.reading(text, ()).silencers), 1)

    def test_a_forgive_inside_a_function_body_is_a_silencer_where_it_hides_that_function(self):
        ts = 'export function f(x: number): number { // #lizard forgive\n' + ts_function().split('\n', 1)[1]
        swift = 'func f(_ x: Int) -> Int { // #lizard forgive\n' + swift_function().split('\n', 1)[1]
        self.assertTrue(lizard_forgives(ts, 'ts', 'typescript'))
        self.assertEqual(TYPESCRIPT.reading(ts, ()).silencers, (1,))
        self.assertTrue(lizard_forgives(swift, 'swift', 'swift'))
        self.assertEqual(SWIFT.reading(swift, ()).silencers, (1,))

    def test_a_forgive_above_a_method_or_an_arrow_function_is_a_silencer_where_it_hides_that_function(self):
        method = 'class C {\n' + swift_function(FORGIVE) + '}\n'
        arrow = FORGIVE + ts_function().replace('export function f(x: number): number {', 'export const f = (x: number): number => {')
        self.assertTrue(lizard_forgives(method, 'swift', 'swift'))
        self.assertEqual(SWIFT.reading(method, ()).silencers, (2,))
        self.assertTrue(lizard_forgives(arrow, 'ts', 'typescript'))
        self.assertEqual(TYPESCRIPT.reading(arrow, ()).silencers, (1,))

    def test_a_forgive_with_no_function_after_it_is_still_a_silencer_because_where_a_marker_stands_is_not_checked(self):
        for comment in (FORGIVE, '/* #lizard forgive */\n'):
            with self.subTest(comment=comment):
                text = ts_function() + comment
                self.assertEqual(lizard_sees(text, 'ts', 'typescript'), ['f'])
                self.assertEqual(TYPESCRIPT.reading(text, ()).silencers, (13,))

    def test_a_forgive_left_after_a_function_hides_the_next_function_so_it_is_a_silencer_all_the_same(self):
        text = ts_function() + FORGIVE + ts_function().replace('function f(', 'function g(')
        self.assertEqual(lizard_sees(text, 'ts', 'typescript'), ['f'])
        self.assertEqual(TYPESCRIPT.reading(text, ()).silencers, (13,))

    def test_a_forgive_with_text_after_it_is_a_silencer_and_not_also_a_comment_line(self):
        found = TYPESCRIPT.reading(ts_function('// #lizard forgive: the reason it is long\n'), ())
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_a_forgive_block_that_runs_over_several_lines_is_a_silencer_on_the_line_its_marker_sits_on_and_its_other_lines_stay_comment_debt(self):
        found = TYPESCRIPT.reading(ts_function('/*\n   #lizard forgive\n   the reason\n*/\n'), ())
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1, 3, 4]))

    def test_a_comment_beside_a_forgive_on_another_line_stays_a_comment_line(self):
        found = TYPESCRIPT.reading(ts_function('// why\n' + FORGIVE), ())
        self.assertEqual((found.silencers, list(found.debt)), ((2,), [1]))

    def test_a_trailing_forgive_is_a_silencer_on_its_own_line(self):
        found = TYPESCRIPT.reading('export const a = 1; // #lizard forgive\n', ())
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_the_two_forgive_forms_lizard_ignores_leave_the_function_scored_and_both_stay_comment_debt(self):
        for comment in ('// #lizard forgive global', '// #lizard forgives(cyclomatic_complexity)'):
            with self.subTest(comment=comment):
                text = ts_function(comment + '\n')
                self.assertEqual(lizard_sees(text, 'ts', 'typescript'), ['f'])
                self.assertEqual(TYPESCRIPT.reading(text, ()).debt, {1: 'line'})

    def test_a_forgive_in_python_rust_or_shell_is_ordinary_comment_debt_because_radon_clippy_and_no_scan_read_it(self):
        for name, text in (('python', '# #lizard forgive\nx = 1\n'), ('rust', '// #lizard forgive\nfn f() {}\n'),
                           ('shell', '# #lizard forgive\nx=1\n')):
            with self.subTest(name):
                found = cd.LANGUAGES[name].reading(text, ())
                self.assertEqual((found.silencers, list(found.debt)), ((), [1]))


class CombinedSilencersTest(unittest.TestCase):

    def test_a_typescript_file_with_an_istanbul_marker_and_a_lizard_forgive_reports_both(self):
        found = TYPESCRIPT.reading('/* istanbul ignore next */\nexport const a = 1;\n// #lizard forgive\nexport const b = 2;\n', ())
        self.assertEqual((found.silencers, found.debt), ((1, 3), {}))

    def test_a_swift_file_with_a_swiftlint_disable_and_a_lizard_forgive_reports_both(self):
        found = SWIFT.reading('// swiftlint:disable:next cyclomatic_complexity\nlet a = 1\n// #lizard forgive\nlet b = 2\n', ())
        self.assertEqual((found.silencers, found.debt), ((1, 3), {}))

    def test_two_markers_on_one_line_are_one_silencer_in_typescript(self):
        found = TYPESCRIPT.reading('/* istanbul ignore next */ /* #lizard forgive */\nexport const a = 1;\n', ())
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_two_markers_on_one_line_are_one_silencer_in_swift(self):
        found = SWIFT.reading('/* #lizard forgive */ // swiftlint:disable:next force_cast\nlet a = b as! C\n', ())
        self.assertEqual((found.silencers, found.debt), ((1,), {}))

    def test_any_of_returns_the_sorted_lines_every_reader_found_once(self):
        both = cd.any_of(lambda reading, source: (3, 1), lambda reading, source: (1, 2))
        self.assertEqual(both(None, ''), (1, 2, 3))


class LizardForgiveGateTests:

    def setUp(self):
        super().setUp()
        self.choose(self.COMPONENT)

    def choose(self, component):
        (self.root / 'quality-gates.json').write_text(json.dumps({
            'format_version': 1, 'languages': [self.LANGUAGE], 'exclude': [],
            'components': {'chosen': [component], 'declined': []}, 'commit_time_limit_seconds': 2,
            'settings': {'no-comments': {'exclude': [], 'conventions': []}},
        }))

    def crap_exit(self):
        argv = ['--lang', self.LANGUAGE, '--no-coverage', str(self.root / self.FILE)]
        with contextlib.redirect_stdout(io.StringIO()):
            return ratchet.exit_code(crap.gate(argv, self.root))

    def cc_exit(self):
        argv = ['--lang', self.LANGUAGE, str(self.root / self.FILE)]
        with contextlib.redirect_stdout(io.StringIO()):
            return ratchet.exit_code(qc.gate(argv, self.root))

    def test_a_function_over_the_limit_behind_a_lizard_forgive_passes_crap_and_the_same_function_without_it_fails(self):
        self.put(self.FILE, self.MAKE(FORGIVE) + self.TRIVIAL)
        self.assertEqual(self.crap_exit(), 0)
        self.put(self.FILE, self.MAKE('') + self.TRIVIAL)
        self.assertEqual(self.crap_exit(), 1)

    def test_a_lizard_forgive_fails_the_comment_gate_until_the_silencer_is_recorded(self):
        self.put(self.FILE, self.MAKE(FORGIVE))
        self.comments.write_text('{}\n')
        self.silencers.write_text('{}\n')
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn(f'FAIL {self.FILE}: 1 silencers, baseline allows 0 — lines 1', out)
        self.silencers.unlink()
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {self.FILE: 1})
        self.assertEqual(self.gate()[0], 0)

    def test_the_lizard_forgive_line_is_not_recorded_as_comment_debt(self):
        self.put(self.FILE, self.MAKE(FORGIVE))
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(json.loads(self.comments.read_text()), {})

    def test_a_new_lizard_forgive_added_after_recording_fails_and_names_its_line(self):
        self.put(self.FILE, self.MAKE(FORGIVE))
        self.gate('--update')
        self.put(self.FILE, self.MAKE(FORGIVE) + '\n' + FORGIVE + self.STATEMENT)
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertRegex(out, rf'FAIL {self.FILE}: 2 silencers, baseline allows 1 — lines 1, \d+')

    def test_update_will_not_record_a_new_lizard_forgive(self):
        self.put(self.FILE, self.MAKE(''))
        self.gate('--update')
        self.put(self.FILE, self.MAKE(FORGIVE))
        code, out = self.gate('--update')
        self.assertEqual(code, 1)
        self.assertIn('It will not record a new silencer', out)
        self.assertEqual(self.recorded(), {})

    def test_a_lizard_forgive_that_is_removed_shows_as_paid_until_update_lowers_the_baseline(self):
        self.put(self.FILE, self.MAKE(FORGIVE) + '\n' + FORGIVE + self.MAKE('').replace(' f(', ' g('))
        self.gate('--update')
        self.assertEqual(self.recorded(), {self.FILE: 2})
        self.put(self.FILE, self.MAKE(FORGIVE))
        code, out = self.gate()
        self.assertEqual(code, 1)
        self.assertIn(f'PAID {self.FILE}: 1 silencers, baseline still says 2', out)
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {self.FILE: 1})
        self.assertEqual(self.gate()[0], 0)

    def test_a_forgive_that_lizard_ignores_stays_comment_debt_and_records_no_silencer(self):
        self.put(self.FILE, self.MAKE('// #lizard forgives(cyclomatic_complexity)\n// #lizard forgive global\n'))
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual((self.recorded(), json.loads(self.comments.read_text())), ({}, {self.FILE: 2}))

    def test_a_forgive_is_not_counted_when_the_comment_row_for_the_language_is_not_chosen(self):
        self.choose('no-comments')
        self.put(self.FILE, self.MAKE(FORGIVE))
        self.put('m.py', 'x = 1\n')
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual((self.recorded(), json.loads(self.comments.read_text())), ({}, {}))

    def test_the_status_names_the_silencers_beside_the_comment_total(self):
        self.put(self.FILE, self.MAKE('// why\n' + FORGIVE))
        out = self.gate('--status')[1]
        self.assertIn('# Silencers: 1 in 1 files\n', out)
        self.assertIn('# Comment debt: 1 lines in 1 files\n', out)

    def test_choosing_the_comment_gate_records_the_forgives_already_there_so_the_gate_then_passes(self):
        self.put(self.FILE, self.MAKE('// why\n' + FORGIVE))
        (self.root / 'quality-gates.json').unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            code = setup_choices.main(['--go', '--choose', self.COMPONENT], root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(self.recorded(), {self.FILE: 1})
        self.assertEqual(json.loads(self.comments.read_text()), {self.FILE: 1})
        self.assertEqual(self.gate()[0], 0)


class LizardForgiveTypeScriptGateTest(LizardForgiveGateTests, SilencerGateCase):
    FILE = 'm.ts'
    LANGUAGE = 'typescript'
    COMPONENT = 'no-comments-typescript'
    MAKE = staticmethod(ts_function)
    STATEMENT = 'export const b = 2;\n'
    TRIVIAL = 'export function ok(x: number): number { if (x) { return 1; } return 0; }\n'

    def test_a_function_over_the_limit_behind_a_lizard_forgive_passes_cc_check_and_the_same_function_without_it_fails(self):
        self.put(self.FILE, ts_function(FORGIVE) + self.TRIVIAL)
        self.assertEqual(self.cc_exit(), 0)
        self.put(self.FILE, ts_function('') + self.TRIVIAL)
        self.assertEqual(self.cc_exit(), 1)

    def test_a_javascript_file_is_read_the_same_way(self):
        self.put('m.js', ts_function(FORGIVE).replace(': number', '').replace('export ', ''))
        self.assertEqual(self.gate('--update')[0], 0)
        self.assertEqual(self.recorded(), {'m.js': 1})


class LizardForgiveSwiftGateTest(LizardForgiveGateTests, SilencerGateCase):
    FILE = 'A.swift'
    LANGUAGE = 'swift'
    COMPONENT = 'no-comments-swift'
    MAKE = staticmethod(swift_function)
    STATEMENT = 'let b = 2\n'
    TRIVIAL = 'func ok(_ x: Int) -> Int { if x > 0 { return 1 }; return 0 }\n'


class LizardForgiveRadonTest(SilencerGateCase):

    def test_a_python_function_over_the_limit_behind_a_lizard_forgive_comment_still_fails_cc_check_because_radon_does_not_read_it(self):
        self.put('m.py', python_function('# #lizard forgive\n'))
        argv = [str(self.root / 'm.py')]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ratchet.exit_code(qc.gate(argv, self.root)), 1)
