---
status: accepted
date: 2026-11-04
---

# ADR-012: A thematic compendium over an archive of decisions

## Context

Eleven ADRs had grown to about 3,600 lines. ADR-001 alone was 1,600 lines,
holding 20 dated addenda and 17 "Current rule, restated" sections, some of them
superseded by later restatements of the same rule. To learn what is true now,
an agent or the builder had to read past the history to the newest restated
section of each rule, and decisions that were never restated (ADR-005 to
ADR-011) had to be read whole. The builder found the faithful history useful as
an audit trail but not as the working reference.

ADR-004 made each rule's home its ADR's newest "Current rule, restated"
section, tagged for `qg-references`.

## Decision

**`docs/adr/` holds a compendium; `docs/adr/archive/` holds the ADRs.**

- **The archive** keeps every numbered ADR as accepted, with its addenda. New
  decisions are still numbered ADRs, or dated addenda on the one they amend,
  and go in the archive. The archive files were moved there unchanged except
  that the `rule:` tag lines, invisible when rendered, were removed from them.
- **The compendium** is one page per question a reader asks, not per module or
  per ADR: what gets scored, how complexity is counted, baselines and
  loosening, components and setup, how standards are made, and code structure.
  `docs/adr/README.md` lists each page with a "read this when" line. Each page
  states what is decided now, marks what is decided but not built, and links
  each statement to the archive section behind it.
- **Each rule has one home.** A rule that concerns two pages lives on the one a
  reader would open first; the other page points to it in one line. A
  cross-cutting decision gets a page of its own rather than a copy on each.
- **A change updates both in one pull request:** the archive ADR or addendum
  that records the decision, and the compendium page it affects. The
  compendium never states anything the archive does not back.
- **The compendium carries the tagged rules.** A rule a skill depends on is
  tagged on its compendium page, and `qg-references` reads the pages instead of
  the ADRs. Changing a tagged rule edits its page in place; the archive
  addendum records the change and why. No new "Current rule, restated" section
  is written.

This amends ADR-004: the home of a tagged rule moves from the ADR's restated
section to its compendium page. Every check ADR-004 lists still applies to
tagged text. The two-way `Amends:` and `Amended by:` link check still runs on
each archive ADR.

## Consequences

- The working reference is about a quarter of the archive's length, and an
  agent loads only the page its task needs.
- Generated reference files name the compendium page and section they came
  from, so every shipped reference file changes once, in the next release.
- Some ADR-001 addenda about coverage readers are not yet folded into a page.
  The page that would hold them lists them under *Not folded in yet*, linked,
  until they are.
- The archive is no longer kept current. A reader who opens it sees each rule
  as it stood when last restated there.
- The compendium can be reorganised at any time from the archive, because the
  archive keeps everything.

## Rejected

- **Gitignore the archive.** It would exist on one machine only: cloud
  sessions and fresh clones would lose it, and links from pull requests and
  issues would break. A line in `CLAUDE.md` keeps agents to the compendium at
  no cost.
- **One page per module or per ADR.** A decision that crosses modules would
  have to be split or copied, and copies drift.
- **One compendium file.** Every task would load all of it.
- **Repeat a rule on each page it concerns.** The copies drift; the fault
  ADR-004 was written to remove from the README.
- **Renumber the ADRs.** Links from pull requests and issues would break, for
  no gain once agents read the compendium.
