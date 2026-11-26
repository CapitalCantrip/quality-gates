# Coding standards

Judgement rules a reviewer checks a change against. A review checks the diff
against every rule, and each finding cites its rule's number. Each rule has its
reason and its source. A rule a script can check becomes a gate and leaves this
file.

## Releasing

1. **Every change a consumer receives has its own CHANGELOG line.**
   Reason: the `changelog` workflow only checks that `CHANGELOG.md` moved, so
   a release can ship a change no line tells the consumer about (PR #219 had
   to add lines PR #211 missed).
   Source: sprint 3 retro, finding 6 (#207, 2026-11-24).

11. **A step that tells a consumer to rename, move or split a file, or to
    change a workflow, has been run end to end through every gate that reads
    that file, `qg tolerated` included.** With no safe step to give, the
    step says to ask the builder.
    Reason: #243's fix round advised a baseline file per language; `qg
    tolerated` reads only the fixed names, so growth in the new file passed
    CI without the builder's label.
    Source: sprint 3a retro (2026-11-27).

## Writing into a consumer's project

2. **Code that writes, overwrites or deletes in a consumer's project checks
   every input it trusts before its first write, and has a test for each odd
   form:** a name that differs only in case, a path containing a folder
   separator or `..`, unreadable bytes, a file with valid syntax but the wrong
   layout, and every other way the tool names the same thing (for example an
   agent's header `name:`). A fix for a review finding gets the same tests.
   Reason: PR #238 needed two review rounds and 15 fixes, two of them data
   loss, and most round-2 findings were in round-1 fixes.
   Source: #101 retro (2026-11-25).

3. **Parse the shape, then judge the value.** A reader matches its input's
   structure as broadly as the format allows, and reports a value it does not
   recognise as an error or warning that names it.
   Reason: a file a person edits by hand is a wider format than the one our
   code writes. PR #238's second review found agent headers with a byte-order
   mark, quotes and an inline comment, and a `settings.json` that parsed but
   had the wrong layout.
   Source: AgenticOS coding standards, rule 2; #101 retro (2026-11-25).

4. **A marker counts only where it is used: outside inline code, code blocks
   and quoted examples.** Code blocks are found through `fences.py`.
   Reason: in AgenticOS, a description that quoted a marker as an example
   published a private item.
   Source: AgenticOS coding standards, rule 3.

9. **A command found in a consumer's file counts only as the command word of
   a command segment, never as a substring, and code that places something
   by such a find writes nothing unless exactly one place qualifies.** It
   prints a note saying where to put it by hand. Each reader has a test for a
   file name, an argument and a trailing comment that name the command.
   Reason: two of #234's hard review findings came from deciding "this job
   runs a gate" by a substring of the workflow text, the second in the fix
   for the first; `qg setup` now only checks for its CI step by command
   word and prints it to paste.
   Source: #234 retro (2026-11-26).

## Changing behaviour

5. **When a change replaces a component, list what the old one did that people
   can see, and test each item in the new one.**
   Reason: in AgenticOS, a replacement passed every test it had and dropped
   a feature people used for eight days.
   Source: AgenticOS coding standards, rule 1.

6. **A change that adds a file the package ships runs the tool from a built
   wheel.**
   Reason: tests run from the source tree, where every file is present. A
   shipped file missing from `package-data` in `pyproject.toml` passes them
   and reaches no consumer (PR #238 added `agents/*`).
   Source: AgenticOS coding standards, rule 6, adapted; #101 retro
   (2026-11-25).

10. **A new way to write a baseline goes through every existing baseline
    rule, and its tests run those rules through it:** unmeasured entries
    kept, entries outside what the gate checks kept, an unreadable baseline
    stops it, for every gate and every baseline a gate writes, a merged
    sibling's included. The tests loop over the ways to write, so a new way
    joins the list rather than getting hand-picked cases.
    Reason: #192 needed three review rounds with hard findings; each fix
    added a path (`--rerecord`, the refusal before `settle`) that skipped a
    rule the old path kept, and its ADR sentence described the intent, not
    the code.
    Source: #192 retro (2026-11-26).

12. **Each new or changed sentence in an ADR, compendium page, skill,
    README, GLOSSARY or CHANGELOG names, in the report, the code line or
    test that makes it true.** A sentence about what an outside tool does
    (lizard, clippy, SwiftLint, coverage.py, GitHub) names the real run that
    shows it.
    Reason: in sprint 3a, #192, #236, #244 and #255 each shipped or nearly
    shipped a sentence the code or the tool contradicted; the reviewer
    found each by a real run.
    Source: sprint 3a retro (2026-11-27).

13. **A fix that changes behaviour makes every sentence about that behaviour
    true in the same commit:** compendium, skills, README, GLOSSARY and
    CHANGELOG.
    Reason: #196's and #243's second rounds found hard findings in sentences
    a first-round fix had made false.
    Source: sprint 3a retro (2026-11-27).

## Tests

7. **A derived view is tested against its source by ID.**
   Reason: a test that matches by display text skips every renamed item and
   passes without checking it.
   Source: AgenticOS coding standards, rule 4.

8. **The hardest case to detect gets its own test.** Two cases that run
   different code are two tests, however alike their wording.
   Reason: `Reviewer.md` and `reviewer.md` read alike but are one file on
   macOS and two on Linux; PR #238 missed the case until review.
   Source: AgenticOS coding standards, rule 5; #101 retro (2026-11-25).
