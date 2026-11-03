# Components and setup

Read this when you add, change or ship a component, touch `qg setup`,
`qg status`, `qg explain`, `/setup-standards`, the choice file, `qg-skills`,
or admit an outside tool or skill.

## Core and components

- **A small core is always on:** the working method, proving that work works,
  the asking rule, the project map and the checkpoints. Everything else is an
  optional **component**: one capability with all its parts (command, skill,
  CI step, baseline, explainer), switched on or off together.
  ([ADR-005](archive/ADR-005-direction-idea-to-release.md#core-and-components))
- **`components.json` says what a consumer can install;** `upstream.json`
  records which upstream commit each copied file came from. The manifest is a
  contract with a format version; a shape change needs a new version and a
  CHANGELOG note. ([ADR-005 addendum 2026-10-25](archive/ADR-005-direction-idea-to-release.md#addendum-2026-10-25-the-component-manifest-and-qg-status))
- **`qg status` is a report, not a gate:** read-only, offline, exit 0, except
  exit 3 when the shipped manifest itself is broken.
  ([ADR-005 addenda](archive/ADR-005-direction-idea-to-release.md#addendum-2026-11-01-qg-status-when-the-shipped-manifest-is-broken))

## Choosing components

Built in 0.13.0 unless marked otherwise. Source: [ADR-007](archive/ADR-007-component-install.md).

- **Setup shows one table:** each component, its description and its cost
  (commit delay, CI time, tools fetched), the recommended set ticked. The
  builder says "go" or names changes.
- **Explainers:** each component ships a short plain-words page with up to
  three checked outside links; `qg explain <name>` prints it. The agent reads
  it rather than writing an explanation fresh.
- **The choice file,** `quality-gates.json`, records the languages, the chosen
  and declined components, `exclude`, the commit time limit and the comment
  gate's settings. Languages are confirmed by the builder and then the file,
  not detection, is the source of truth.
- **Pin bumps:** a component a release adds is off until accepted. Setup
  offers it, and an offer is recorded only when the builder chooses or
  declines it. A gate whose only part present is the skill `qg-skills` copied
  does not count as installed.
- **Switching off** never applies to the core. Switching off a gate the
  project has is loosening (see [Baselines and loosening](baselines-and-loosening.md));
  helpers and components for unused languages switch off freely.
- **Decided, not built yet:** the runner (`qg run commit` / `qg run ci`, which
  runs the chosen components' steps), the 2-second commit time limit that
  warns but never fails, "could not check" for a missing tool, the track
  record of catches (`qg tally`), and the *Can't run here* setup block
  (quality-gates#138, #141).

## Shipped skills

<!-- rule:vendored-skills -->
`qg-skills` ships 17 of Matt Pocock's skills beside the standards skills, copied
from `mattpocock/skills` at one pinned commit:

- every step the size rule names: `wayfinder`, `grill-with-docs`, `to-spec`,
  `to-tickets`, `implement`, `implement-spec`, `tdd`, `diagnosing-bugs`,
  `improve-codebase-architecture`, and his `code-review` as
  `review-against-spec`;
- what those steps call or the builder uses beside them: `codebase-design`,
  `domain-modeling`, `pr`, `triage`, `retro`, `writing-for-agents`, `handoff`.

Each copied skill carries his MIT notice as `LICENSE-mattpocock`.

**Copied word for word, except for a listed set of changes.** Each change is
recorded with what changed, why, and how to redo it on a newer upstream file.

**`code-review` ships as `review-against-spec`.** As a project skill named
`code-review` it would hide Claude Code's own `/code-review`, which does a
different job: it hunts for bugs, where Pocock's checks the change against the
project's written standards and the issue or spec it came from. The builder
wants both. The three skills that call it by name are changed to match.

**`setup-matt-pocock-skills` is replaced by a pointer skill** of the same name
that sends the builder to `/setup-standards`. Six of the copied skills tell the
builder to run his setup when the project's agent docs are missing;
`/setup-standards` already writes them from his templates. A pointer keeps those
six skills word for word.

**An update is a release.** A monthly check opens an issue when a watched
upstream file changes. Adopting the change means replacing the word-for-word
copies, redoing each listed change, moving the pinned commit, and releasing.
Consumers get it by bumping their pin; their `qg-skills --check` test fails
until they rerun `qg-skills`, so a stale copy cannot pass CI.
<!-- /rule:vendored-skills -->

- **Copied word for word, except where `docs/upstream-adaptations.md` lists a
  change,** with how to redo it on a newer upstream file. An upstream update
  is a release. ([ADR-003](archive/ADR-003-vendor-pocock-skills.md#decision))
- **`/setup-standards` sets up a project for all three layers** and, run
  again, is the upgrade after a pin bump: it changes nothing already correct
  and ends with a report accounting for every step.
  ([ADR-002](archive/ADR-002-engineering-standards.md#setting-up-a-project-one-command))

## Admitting outside sources

Source: [ADR-010](archive/ADR-010-admission-and-recognised-conventions.md#admitting-an-outside-source).

- **Licence:** copied material needs MIT, Apache-2.0, BSD or ISC; a dependency,
  never copied, may have any OSI-approved licence.
- **Record:** each source is recorded once in `components.json` with its
  licence, a sentence on its author's practice, and a last release date or a
  "stable" reason. A source with no admission does not ship. The monthly
  upstream workflow flags a source with no release in 12 months.
- **Pinning:** a downloaded tool gets an exact, checksum-verified version; a
  Python package this package installs gets a minimum version plus the version
  CI tested; a tool setup installs into a project gets an exact version moved
  by a pin bump.
- **A conflict with a decision here** is resolved by an entry in
  `docs/upstream-adaptations.md` for copied text, or a new decision for a
  dependency.
