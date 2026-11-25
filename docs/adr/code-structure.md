# Code structure

Read this before adding a module, a command or a file format, or when you are
unsure which module new code belongs in. `CLAUDE.md`'s rule is: new code goes
in the module this page names, and when that module does not exist yet, stop
and ask rather than add a second copy.

Source: [ADR-011](archive/ADR-011-code-structure.md). Each part landed, or
lands, as a refactor with no behaviour change just before the first build that
needs it.

## One project module

`project_files` owns finding the root, deciding which files the gates look at
(see [What gets scored](what-gets-scored.md)); the comment gate asks it for the
files of each language, and it applies the choice file, so the gate lists no
files itself. It also owns reading and writing every
file quality-gates keeps in a project: the choice file, baselines, the hook,
CI, the instruction file, `docs/agents/*` and the PR template. Every write goes
through one planned-changes step that setup shows before the builder's "go".
Built for CI (quality-gates#234): setup adds the `qg tolerated` step between
quality-gates' markers in the one job that runs a gate on pull requests,
writes nothing and prints a note when no job or more than one qualifies, and
edits only the lines between the markers. Decided, not built yet: the same for
the hook.
Built (quality-gates#234): it reads main's copy of a file, the bytes
committed on the default branch or a plain "absent", a file's bytes at any
ref that names a commit, and the choice file at a ref; no gate or `qg`
command runs git outside the project module. The default branch is the
remote's `HEAD`, then `main`, `master`, `origin/main` and `origin/master`. ([ADR-011 addendum 2026-11-25](archive/ADR-011-code-structure.md#addendum-2026-11-25-mains-copy-of-a-file-and-the-tolerated-module))

## The tolerated module

Decided, not built yet (quality-gates#192): `tolerated` adds up the tolerated
list (every baseline, both exclude lists, the silencer baseline, and recorded
reasons once quality-gates#115 lands) for the tree and for a git ref, and
returns what grew. It reads baselines through the ratchet and files through the
project module, and parses nothing itself. `qg tolerated --against <ref>` runs
it in CI. Silencer patterns are rows in `comment-debt`'s per-language table, not
the registry. Built so far (quality-gates#234): the module and
`qg tolerated`, which find no growth yet; `ratchet.baseline_from`, which reads
a baseline from bytes; and a silencer pattern on each row of the table, which
matches nothing until quality-gates#195, with the ratchet asking for
`silencer-baseline.json` by the name the project module knows. ([ADR-011 addendum 2026-11-25](archive/ADR-011-code-structure.md#addendum-2026-11-25-mains-copy-of-a-file-and-the-tolerated-module))

## One language registry

`languages` holds what makes a language (name, label, suffixes, project
markers) and nothing about gates. Each gate keeps its own table of what it
supports, keyed by language name; a test fails when a gate names a language
the registry does not know. Every language the choice file can record is
registered. The registry never walks the tree. `languages_table.py` generates
`docs/languages-by-gates.md` from the gate tables; it is a tool for this
repo's docs, not a consumer command.

## One gate interface and one ratchet

Built: `comment-debt`, `cc-check` and `crap` only find, returning findings
with a location, a number and a kind; each turns its flags into one
`ratchet.Asked` and reads no baseline file. Two runs skip judging until
quality-gates#138: for `cc-check --format json` without `--baseline` and for
`comment-debt --status` the gate sets `judged` to false in its `Asked`, and
`ratchet.enforce` then returns no verdicts. Otherwise `ratchet` reads the
baseline, keys each location by its real path from the root only when a
baseline is used, compares, writes the baseline on `--update` and returns a
result with one outcome per location: passed, failed, behind the baseline,
unmeasured or did not run. `ratchet.recorded` is the record step: given what a
gate finds for one comment language and which baseline paths belong to it, it
returns the baseline with that language's entries replaced by its counts now
(no entry for a count of zero), and every nonzero entry outside that language
as it was. A count of zero sets no allowance, so it does not displace the
entry of a file that is also unmeasured (`ratchet.owed_counts`). Setup puts
the result among its planned changes when it switches a comment language on,
so recording and choosing are one step, while `--update` still only lowers.
Both write through one function, `ratchet.surviving`, which decides which
stored entries survive: the counts still owed, an unmeasured file's entry, and
every entry outside the files the write covers; it drops any entry of zero, so
no write keeps one. A new rule about what a write keeps goes there and nowhere
else. A gate may say which baseline paths it covers: entries outside them are
not judged and `--update` writes them back as they were, less any entry of
zero, which is how `comment-debt` keeps the entries of a language that is not
chosen. A gate that could not run raises `errors.ToolError`, and so does
`ratchet` for a missing, unreadable or malformed baseline; the one place that
catches it is `ratchet.attempt`, reached through `ratchet.run_gate`, which
turns it into *did not run* and exits 2. On a gate's path the one other catch,
in `project_files.root_of_scanned`, is a retry: when the scanned path is not
inside a git repository, it looks for the root from the working folder
instead. Outside the gates, the setup commands and `qg status` catch it to
report their own errors. Decided, not built yet: the one common baseline
format, the line for a language a gate does not support and the runner's
record of *did not run* (quality-gates#138), and recorded reasons
(quality-gates#115). See [Baselines and
loosening](baselines-and-loosening.md).

## One code reader

Built for Rust, TypeScript, Swift and shell (quality-gates#210, #186, #187):
`code_reader` is the one reader of
comments and strings for the non-Python languages. For one file and one
language's syntax it returns each comment (kind, text, start and end line) and
a copy of the source with strings and comments blanked, line numbers kept. It
is a module-level function, not private to `comment-debt`, because the
swallowed-error and escape-hatch gates (quality-gates#132, #133) search that
copy. Each language's comment syntax is a row in `comment-debt`'s own table,
keyed by registry name, not a module and not part of the registry. A literal
with interpolation, such as TypeScript's `${}` or Swift's `\( )`, names its
bracket pair and the pattern that reads the literal on after the closing
bracket; the reader reads the code between the brackets as code. Python keeps
its own reader.

## Left to the runner

`comment-debt` reads the choice file for its files and exclusions and has no
`--exclude`; `--update`, `--status`, `--report` and `--baseline` stay.
Decided, not built yet (quality-gates#138): the one common baseline format,
which makes `comment-debt.json` a location in it instead of a count per file, and every
gate flag other than `--exclude` going away.

## Coverage matching in one place

Decided, not built yet: readers only parse into one shared shape; one matcher
pairs scanned functions with report entries. See
[How complexity is counted](counting-complexity.md).

## One manifest module and a thin `qg`

`manifest` reads and validates `components.json` and `upstream.json` on every
load and hands out typed records; no caller reads raw JSON. What a component
installs for and what a gate scores stay separate, and a test fails when they
differ. `qg` is a dispatcher with no logic of its own: every new command is a
`qg` subcommand. Decided, not built yet: the old command names fold into
`qg <name>` (quality-gates#138).
