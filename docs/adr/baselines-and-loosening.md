# Baselines and loosening

Read this when a gate reports `PAID`, `new` or `worse`, when you update a
baseline, or when a project wants to relax a standard for one case or for
everything.

## The baseline ratchet

<!-- rule:baseline-ratchet -->
`cc-check` and `crap` take `--baseline`, so a repo with existing debt can
enforce the limits in CI without first paying it all off.

- **Only functions over the threshold are recorded.** A function that drops to
  the threshold leaves the baseline at the next `--update`, and cannot return.
- **A missing baseline is an error, except with `--update`.** Treating it as
  empty would fail every adopting repo on its first run; treating it as
  permissive would let a mistyped path pass CI.
- **`--update` will not recreate a baseline that main has.** When the file is
  missing and the default branch of the repository holding it has it
  committed (under any spelling where git ignores case), `--update` writes
  nothing, exits 2 and says to restore it with `git checkout <branch> --
  <file>`, or to run `--rerecord`. With no such copy, no default branch, or a
  baseline outside any repository, it records a new one. Otherwise deleting
  the file and running `--update` would record every new and worse function.
  It guards only the local default branch's copy; CI compares against the
  real base.
- **`--rerecord` records a baseline afresh** from the tree for the re-record
  steps a release asks for: measured entries become what the gate finds now.
  Unmeasured entries and entries outside what the gate checks stay, and an
  unreadable baseline stops it, so delete that file first. CI's
  `qg tolerated` then asks for the builder's label.
- **An unmeasured function is never recorded, and keeps a nonzero entry.**
  `--update` lowers and removes entries for measured functions, adds none for an
  unmeasured one, and keeps an existing nonzero entry as it is while the
  function stays unmeasured. It writes the file, then exits 1 and lists the
  unmeasured functions. A check run reports a baselined function that is
  unmeasured as unmeasured, not as paid. A worst-case score for a function with
  no figure would sit in the baseline as accepted debt, and an entry dropped
  during a coverage outage could never be added back.
  A file the gate could not read is unmeasured as a whole, and keeps the entries
  of all its functions the same way.
- **CRAP baselines need coverage,** because CRAP without coverage is a ranking,
  not a gate.
<!-- /rule:baseline-ratchet -->

## Baseline keys

<!-- rule:baseline-keys -->
**The rule.** A baseline key is the file's real path relative to the real path of
the repo root (the working directory outside a git repo), followed by `::` and
the function name, with a method as `Class.method`. Symlinks are resolved and a
`..` step lands where it really lands, so `src/Shop/../up.py` is keyed by the
folder `src/Shop` links to, not by `src`. One file gets one key whatever spelling
or argument order reached it. File names on screen, in the table and in `--json`,
keep the link path as scanned.

**A key carries no line number,** so editing elsewhere in the file does not move
it. A renamed or moved function counts as new, so debt cannot be laundered by
renaming.

**The real path has the case stored on disk.** On a case-insensitive volume a
link keeps its own spelling when resolved, so `pa/x -> ../shared/Shop` and
`pb/x -> ../shared/shop` would key one file two ways, and one run would miss the
coverage the other found. On macOS the real path is therefore read back from the
filesystem (`F_GETPATH`), which gives `shared/Shop`; elsewhere, or when that read
fails, it is the resolved path. The key and every coverage reader (coverage.json,
Istanbul, llvm-cov, xccov) use the same function.

**A link to a folder outside the repo** gives a key that starts with `../` and
depends on where that folder sits relative to the repo on each machine. A
checkout whose shared folder lies elsewhere sees those functions as new and their
old rows as paid. This is accepted: such links are rare, and the alternative,
keeping link-path keys and patching each way a path can be typed, fails more
often.
<!-- /rule:baseline-keys -->

## Debt and recorded reasons

- **Problems found when a gate is adopted are debt,** recorded in its baseline
  and paid down busiest files first (quality-gates#42). A deliberate exception
  is a **recorded reason** instead: why, what would let the standard come
  back, and a review date or trigger where the gate asks for one. Two gates
  take no debt: a test switched off at adoption and a key found in history
  each need a reason first. ([ADR-006](archive/ADR-006-gates-beyond-complexity.md#two-kinds-of-exception-debt-and-recorded-reasons))
- **No gate accepts an in-code marker** such as `gitleaks:allow` or
  `# pragma: no mutate` as its exception: markers are comments, and they cannot
  be reviewed in one place. ([ADR-006](archive/ADR-006-gates-beyond-complexity.md#two-kinds-of-exception-debt-and-recorded-reasons))
- **Built: a marker that switches off one of our own gates is a silencer,**
  recorded in `silencer-baseline.json`, a count per file that only shrinks, and
  part of the tolerated list. `comment-debt` finds it and the ratchet judges it
  (`PAID`, `new`, `worse`, unmeasured) like any baseline; `comment-debt
  --update` records the silencers already there once and only lowers the file
  after that. Python's are `# pragma: no cover` and `# pragma: no branch`;
  Swift's is `swiftlint:disable` in every form (the Swift setup step records
  existing debt with one, so the silencer baseline is where that debt is
  counted); TypeScript and Rust follow in quality-gates#236 and #237.
  ([ADR-010 addendum 2026-11-26](archive/ADR-010-admission-and-recognised-conventions.md#addendum-2026-11-26-silencers-a-second-kind-of-finding), [Swift](archive/ADR-010-admission-and-recognised-conventions.md#addendum-2026-11-26-swifts-swiftlintdisable-is-a-silencer-235))

## Loosening

- **Today a project may tighten a standard, never loosen it.** `qg setup`
  refuses to switch off a gate the project has, or to remove a language that
  still has code. ([ADR-005](archive/ADR-005-direction-idea-to-release.md#loosening-a-standard))
- **Decided, not built yet (quality-gates#115):** a *recorded reason* relaxes a
  gate for one case and the agent may write it, with the builder's label on a
  new one (below); a *loosening* relaxes a
  standard for the whole project (switching off a gate it has, raising a limit
  or the commit time limit, removing a language with code), needs the
  builder's yes as a merge of its own `loosening` pull request, a review date
  at most 90 days away, and always shows as a warning. Both live in
  `quality-gates-reasons.json`. ([ADR-009](archive/ADR-009-recorded-reasons-and-loosening.md))
- **Decided, not built yet (quality-gates#115): a passed review date warns on
  commit and fails on the pull request.** The warning starts 14 days ahead, or
  on the day written for a shorter record; dates are in UTC and the review
  date is the last day a record holds. CI on main only warns. The agent may
  renew a one-case reason in the same pull request; a lapsed loosening blocks
  every pull request until its own renewal is merged. Triggers fire as before.
  ([ADR-009 addendum 2026-11-23](archive/ADR-009-recorded-reasons-and-loosening.md#addendum-2026-11-23-warn-before-a-review-date-reasons-count-as-tolerated-growth))
- **Built (quality-gates#192): a pull request that grows the tolerated list
  fails CI without the builder's label.** `qg tolerated --against <ref>`
  compares the tree with the pull request's base and prints one line saying
  what grew. The list is every baseline (`cc-baseline.json`,
  `crap-baseline.json`, `comment-debt.json`, `silencer-baseline.json`), the
  choice file's `exclude` and `settings.no-comments.exclude`. Growth is a
  baseline entry new or higher, or an exclude prefix covering a path no
  prefix at the base covered; a `settings.no-comments.exclude` prefix the
  base's top-level `exclude` covered is not new. With no choice file in the
  tree, the tree's list is the fixture folders the scan then skips. Lowering
  or removing is not growth. A baseline for a gate with none at the base, or a choice file where
  the base has none, is adoption, not growth. With growth it exits 1 unless
  the pull request carries `tolerated-growth`, or `loosening` on a loosening
  pull request, read from `QG_PR_LABELS` that the CI step fills; the
  `pull_request` trigger lists `labeled` and `unlabeled` so the label re-runs
  it, and `qg setup` says what to add when either is missing. An agent never
  applies either label: the label is the builder's yes on record, not a lock,
  since a pull request can set `QG_PR_LABELS` in its own workflow.
  ([ADR-009 addendum 2026-11-26](archive/ADR-009-recorded-reasons-and-loosening.md#addendum-2026-11-26-the-tolerated-check-as-built---update-will-not-recreate-mains-baseline))
- **Decided, not built yet (quality-gates#115): recorded reasons are part
  of the tolerated list.** A new record needs the builder's label on its pull
  request; a renewal does not, and is named in the check's one line. The
  `loosening` label counts as that label.
  ([ADR-009 addendum 2026-11-23](archive/ADR-009-recorded-reasons-and-loosening.md#addendum-2026-11-23-warn-before-a-review-date-reasons-count-as-tolerated-growth))
- **Built: one ratchet module.** Gates only find, except `cc-check --format
  json` without `--baseline` and `comment-debt --status`, which skip judging
  until quality-gates#138; the ratchet applies the baseline, then the outcome, and turns a gate that could not run into exit
  2, never a pass. Each gate keeps its own baseline file and format.
  ([ADR-011 § 3](archive/ADR-011-code-structure.md#3-one-gate-interface-and-one-ratchet))
- **Decided: baselines stay stored and committed.** The runner builds on them;
  comparing the branch against main on every run was declined.
  ([ADR-007 addendum 2026-11-16](archive/ADR-007-component-install.md#addendum-2026-11-16-stored-baselines-stay-a-gate-may-measure-on-one-system))
- **Decided, not built yet (quality-gates#138): one baseline format,** the
  line for a language a gate does not support, and the runner's record of a
  gate that did not run. Recorded reasons go in before the baseline with
  quality-gates#115.
