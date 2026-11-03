# What gets scored

Read this when a gate scores a file you did not expect, skips one you did, or
when you change how the files are found: `exclude`, `.gitignore`, symlinks,
submodules, or running outside the repo.

## The files in scope

<!-- rule:files-in-scope -->
**The files in scope** are the files git would commit: tracked files plus
untracked files that the project's `.gitignore` does not ignore. Both gates and
language detection use them; outside a git repo, every command that looks for
the project's root stops with exit 2 and one line saying so. The paths given on the command line narrow the set,
and `exclude` in `quality-gates.json` applies on top: each entry names a
folder or file by its path from the repo root, such as `tests/fixtures/`, and
matches whole path segments, so `build` leaves out the folder or file `build`
and never `buildscripts/` or `build_utils.py`. A trailing `/` changes nothing.

Without a choice file, every outermost folder named `fixtures`, `fixture`,
`__fixtures__` or `testdata` is excluded, whatever its case, so `Fixtures`
too, and setup writes that default into the file. A path given on the command
line that is itself inside an excluded prefix is scanned, so a fixture can
still be scored on purpose. A path given on the command line that git ignores
is not scored either; the gate names it in one line on stderr, so a JSON
report stays valid.

Each file is listed once, by its real path, so a file named twice, or named and
also inside a scanned folder, is scored once.

A git submodule is its own repo: the superproject's git lists only the
submodule's folder, so a scan from the superproject scores none of its files.
The *Skipped N folder(s)* line names it, marked `libs/core (a submodule: scan
it from inside)`; scan a path inside it to score it by its own git. Besides
submodules, that line names only folders marked `(already scanned)`.
<!-- /rule:files-in-scope -->

## Symlinked folders

<!-- rule:symlinked-folders -->
**The rule.** The walk follows a symlinked folder that git would commit (a
link is committed as a link), and never walks the same real folder twice in one
scan:

- **Once each, across the whole scan.** A folder's identity, its device and
  inode, is recorded when the walk enters it, including each scanned path
  itself. Path text cannot tell folders apart: on a case-insensitive volume
  `shared/Shop` and `shared/shop` are one folder under two spellings. A folder
  whose identity was already entered is not walked again, which covers a link to
  an ancestor (a loop), two links to one folder, a link beside the real folder,
  and a folder reached from two scanned paths. The second visit is named on the
  *Skipped N folder(s)* line, marked `src/Shop (already scanned)`: the folder's
  files were scanned once, through the first visit.
- **Which visit wins is fixed.** Among the folders under one parent, real
  folders are entered before links, then by name; the walk is depth first in
  that order. The first visit is scanned, so the same arguments on the same
  checkout always yield the same file names. Scanned paths are entered in the
  order given, so a different argument order can change which spelling a file
  shows on screen; its baseline key does not change.
- **File names on screen keep the link path as scanned.** A file reached through
  a link is reported as `Sources/Shop/Shop.swift`, not its real path, and the
  coverage readers (which resolve both sides to a real path) still match it. The
  baseline key is the file's real path.
- **Inside the repo, git decides by location.** A file or folder reached through
  a link is in scope when its location (the real folder it sits in, plus its own
  name) is one git would commit and not excluded. A link the `.gitignore` lists is not followed. A link to a
  folder that does not exist is ignored. A scanned path that is itself a link is
  followed.
- **Outside the repo, a linked folder is scanned in full, less dependency and
  build folders.** Git cannot say what it would commit there, so a link to
  `../shared/Shop`, or a scanned path in no repo, widens the scan to that whole
  folder, except folders named `.git`, `.venv`, `venv`, `.direnv`,
  `node_modules`, `__pycache__`, `backups`, `build`, `.build`, `dist`, `.tox`,
  `.mypy_cache`, `.pytest_cache` or `.worktrees`, which are never walked there.
  Remove the link or exclude it to narrow it further.
- **Files are listed once too.** The same file named twice on the command line,
  or once inside a folder that is also scanned, is listed once, under the first
  spelling met.
<!-- /rule:symlinked-folders -->

## Decisions behind these rules

- **Git is required, and there is no fallback to the current folder.**
  Outside a git repo every command that looks for the project's root exits 2
  with one line. Projects without GitHub are quality-gates#150.
  ([ADR-011 § 1](archive/ADR-011-code-structure.md#1-one-project-module))
- **Tests are gated; fixtures are not.** Test code is agent-written code, so
  it counts toward the languages and is scored. Fixture folders are excluded by
  a default written into the choice file, where it can be seen and changed.
  ([ADR-011 § 1](archive/ADR-011-code-structure.md#1-one-project-module),
  [ADR-007 addendum 2026-11-01](archive/ADR-007-component-install.md#addendum-2026-11-01-test-folders-count-toward-the-languages))
- **One project per git repo,** with one choice file at its root.
  ([ADR-011 § 1](archive/ADR-011-code-structure.md#1-one-project-module))
- **The project's `.gitignore` replaced quality-gates' own skip list,** except
  outside the repo, where git cannot say what it would commit.
  ([ADR-001 addendum 2026-11-01](archive/ADR-001-complexity-standards.md#addendum-2026-11-01-the-files-git-would-commit-v0130))
