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
   Reason: both hard review findings on #234 came from deciding "this job
   runs a gate" by a substring of the workflow text, the second in the fix
   for the first.
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
