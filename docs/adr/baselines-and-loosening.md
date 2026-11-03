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
- **An unmeasured function is never recorded, and keeps its entry.** `--update`
  lowers and removes entries for measured functions, adds none for an unmeasured
  one, and keeps an existing entry as it is while the function stays unmeasured.
  It writes the file, then exits 1 and lists the unmeasured functions. A check
  run reports a baselined function that is unmeasured as unmeasured, not as paid.
  A worst-case score for a function with no figure would sit in the baseline as
  accepted debt, and an entry dropped during a coverage outage could never be
  added back.
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

## Loosening

- **Today a project may tighten a standard, never loosen it.** `qg setup`
  refuses to switch off a gate the project has, or to remove a language that
  still has code. ([ADR-005](archive/ADR-005-direction-idea-to-release.md#loosening-a-standard))
- **Decided, not built yet (quality-gates#115):** a *recorded reason* relaxes a
  gate for one case and the agent may write it; a *loosening* relaxes a
  standard for the whole project (switching off a gate it has, raising a limit
  or the commit time limit, removing a language with code), needs the
  builder's yes as a merge of its own `loosening` pull request, a review date
  at most 90 days away, and always shows as a warning. Both live in
  `quality-gates-reasons.json`. ([ADR-009](archive/ADR-009-recorded-reasons-and-loosening.md))
- **Decided, not built yet (quality-gates#138): one ratchet module and one
  baseline format.** Gates only find; the ratchet applies recorded reasons,
  then the baseline, then the outcome, and turns a gate that could not run
  into exit 2, never a pass. ([ADR-011 § 3](archive/ADR-011-code-structure.md#3-one-gate-interface-and-one-ratchet))
