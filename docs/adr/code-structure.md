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
(see [What gets scored](what-gets-scored.md)), and reading and writing every
file quality-gates keeps in a project: the choice file, baselines, the hook,
CI, the instruction file, `docs/agents/*` and the PR template. Every write goes
through one planned-changes step that setup shows before the builder's "go".
Decided, not built yet: code edits the hook and CI only between quality-gates'
markers.

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
with a location, a number and a kind; they read no baseline and no flag that
picks the outcome, except `cc-check --format json` without `--baseline` and
`comment-debt --status`, which skip judging until quality-gates#138.
`ratchet` decides whether a run is judged and against which baseline, keys
each location by its real path from the root only when a baseline is used,
compares, writes the baseline on `--update` and returns a result with one
outcome per location: passed, failed, behind the baseline, unmeasured or did
not run. A gate that could not run raises `errors.ToolError`, and so does
`ratchet` for a missing, unreadable or malformed baseline; `ratchet.run_gate`
is the one place that catches it, turns it into *did not run* and exits 2.
Decided, not built yet: the one common baseline format, the line for a
language a gate does not support and the runner's record of *did not run*
(quality-gates#138), and recorded reasons (quality-gates#115). See
[Baselines and loosening](baselines-and-loosening.md).

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
