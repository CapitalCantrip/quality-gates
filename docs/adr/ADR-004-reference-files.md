---
status: accepted
date: 2026-10-12
---

# ADR-004: Rules ship with the skills as generated reference files

## Context

The gate skills cited ADR-001 for the rules they depend on: the skip list, the
symlink rule, how Functions are named and keyed, how lizard's Swift bugs are
worked around. Thirteen lines in the shipped skills named an ADR addendum, and
the `standards` skill named `docs/adr/ADR-002-engineering-standards.md` by path.
`qg-skills` copies only the skills, so in a consumer each pointer named a file
that is not there (#62). The README restated some of the same rules in its own
words, a second copy that could drift from the ADR (#63).

The builder decided on 2026-10-10: the rules that skills depend on ship inside
the skills, as reference files built from tagged ADR sections, never written by
hand; a test catches drift on every commit, and the release step rebuilds them.
The README links to them.

A first build tagged the rules where they already stood in the ADRs. Making each
tagged span stand alone meant cutting and reordering accepted text, and review
found rules lost on the way. The builder chose on 2026-10-12 to leave the ADR
history untouched and restate each rule in a dated section of its own, and asked
that every amendment and the text it amends link to each other inside the ADR.

## Decision

**The ADR history is never rewritten.** A rule a skill depends on gets a dated
section of its own at the end of its ADR, `## Current rule, restated <date>:
<rule>`, which states the whole current rule as one text. The body of that
section is tagged with a pair of Markdown comments, invisible when the ADR is
rendered:

```markdown
## Current rule, restated 2026-10-12: the skip list

Amends: [Addendum 2026-10-09: one complexity scan for both gates (v0.7.0)](#addendum-2026-10-09-one-complexity-scan-for-both-gates-v070)

<!-- rule:skip-list -->
**The skip list** is `.git`, `.venv`, ...
<!-- /rule:skip-list -->
```

A tag name is lowercase letters, digits and hyphens, and is used once across all
ADRs. Each marker sits on a line of its own. The decision text and the addenda
it came from stay exactly as accepted, untagged. When the rule changes again,
the change is a new addendum, and a new restated section takes the tag; the old
restated section stays as history and gets an *Amended by* link to the new one.

**Tagged text stands alone.** A consumer has the reference file and nothing else
from quality-gates, so `qg-references --check` fails when tagged text points at
something it lacks:

- a bare issue number such as `#58` (write `quality-gates#58`; a key suffix in
  code, `` `#2` ``, is not a pointer);
- a relative position: "(below)", "(above)", "see below", "the text above";
- "see Rejected" or "under Rejected";
- another ADR (`ADR-001`), or an addendum or the addenda;
- a date used as a pointer: "on", "since", "of", "from", "before", "until" or
  "after" followed by a date, as in "As on 2026-10-09". A date that cites a
  source, as in "interviewed 2026-09-06", stands alone;
- a link to a heading, `](#...)`;
- "this repo", "this ADR" or "this note";
- a repo file: `GLOSSARY.md`, `README`, `CHANGELOG`, `upstream.json`, or a path
  under `docs/`.

**Each amendment and the text it amends link both ways, inside the ADR.** A
section is an amendment when its heading starts with "Addendum", "Amended" or
"Current rule". Directly under its heading it has a line

```markdown
Amends: [Decision](#decision), [Addendum 2026-10-04: the baseline ratchet (v0.3.0)](#addendum-2026-10-04-the-baseline-ratchet-v030)
```

and every section it names has, directly under its own heading, a line
`Amended by:` that links back to it. Links are heading anchors as GitHub makes
them: the heading's text in lower case, every character other than a letter,
digit, `_`, `-` or space dropped, spaces turned into `-`, and `-1`, `-2` and on
added to the second and later headings with the same anchor. A link inside a
heading counts by its text. The plain form was chosen because it renders as a
working link on GitHub and in any Markdown viewer, and needs no extra anchor
markup in the history it must not rewrite. `qg-references --check` fails when:

- an amendment has no `Amends:` line;
- a link names an anchor no heading in the ADR has;
- an amendment links a section that has no `Amended by:` link back to it;
- a section's `Amended by:` link names an amendment whose `Amends:` line does
  not link back.

A line inside a code fence is an example, not a tag or a link, for both checks.
A fence opens on a line of three or more backticks or tildes indented at most
three spaces; a backtick fence's info string holds no backtick. It closes on a
line of the same character, at least as long, with nothing after it but spaces,
so a line such as ```` ```markdown ```` inside a fence does not close it. A line
indented four spaces or more is not a fence.

**A skill links the rule as `references/<name>.md` in its own folder,** from
`SKILL.md` or from a file in a subfolder (`../references/<name>.md`). A leading
`./`, a trailing `#anchor` and a quoted link title (`"The skip list"`) are
allowed. A web address that contains `references/` is not a reference link and
is left alone. Every skill
that links a rule gets its own copy, so each skill stays whole when copied.

**`qg-references` writes the reference files.** For every link it finds in a
shipped skill, it writes the tagged section to that skill's `references/`
folder under a heading, with a line naming the ADR and section it came from and
saying it is generated. It removes a reference file no skill links. Running it
twice changes nothing. `qg-references --check` exits 1 and names each problem;
the test suite runs the same check, so a commit fails when:

- a reference file differs from its tagged section, or is missing;
- a reference file exists that no skill links;
- a tag has no closing tag, a closing tag has no opening one, or a tag name is
  used twice;
- a skill links a rule no ADR tags, or a link does not reach its own skill's
  `references/` folder;
- a link contains `references/` in a form the generator cannot read.
- tagged text points outside its reference file, as listed above;
- an amendment and the text it amends do not link both ways.

**No shipped skill names a quality-gates ADR file by path.** A skill may still
mention an ADR in prose ("from ADR-002") when the same paragraph links the
reference file.

**The README links reference files instead of restating rules.** It keeps one
plain sentence saying what a rule is for. A test fails when a README paragraph
outside a table shares eight words in a row with a tagged rule.

**Every release runs `qg-references`** (README § Releasing), and `qg-skills`
copies the reference folders with their skills.

This amends ADR-002 § Writing for agents, *each meaning has one home*: the home
stays the ADR, and a skill links its generated reference file rather than the
ADR.

## Consequences

- A consumer has every rule its skills cite, at the pinned version, with no
  network access.
- A rule appears once per skill that links it. The copies are generated, so
  they cannot drift without failing the tests.
- Editing a tagged ADR sentence is a two-step change: edit, then run
  `qg-references`. The failing test names the command.
- A rule a skill restates in its own words is not caught by the drift check.
  Skills link instead of restating.
- Changing a tagged rule is three edits in its ADR: the addendum that records
  the change, a new restated section that takes the tag, and the link lines
  both ways. The check names any link that is missing.
- A reader of an ADR can follow any rule from where it was decided to its
  current wording, and back.

## Rejected

- **Leave the pointers.** No work, but every pointer names a file a consumer
  lacks, so an agent following it finds nothing.
- **Link to the ADR on GitHub at the pinned tag.** The text matches the pin,
  but the skill then needs the network and the right tag in every link, and a
  cloud session or an offline agent cannot read it.
- **Ship the whole ADRs with the skills.** Every rule arrives, but so does the
  history, the rejected options and the amended text, and an agent has to work
  out which paragraph is current.
- **Copy the rules into the skills by hand.** Fast once, and the copies drift
  the first time an addendum amends a rule: the fault the README already had.
- **Tag the rule where it already stands.** No new text, but the tag then has to
  span accepted text that leans on what came before it, so making it stand
  alone means rewriting the history.
- **HTML anchors (`<a id="...">`) as link targets.** Shorter links, but they add
  markup to every amended heading of accepted text, and GitHub's own heading
  anchors already work.
