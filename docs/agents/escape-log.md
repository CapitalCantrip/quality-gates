# Escape log

An escape is a problem that got past every gate and was found later (see
`GLOSSARY.md`). Each one is an issue on this repo's tracker with the `escaped`
label, written from `.github/ISSUE_TEMPLATE/escaped.md`: what happened, how it
was found, the earliest point it could have been stopped (idea, spec, module
map, ticket brief, build, review, gate), and which gate should have caught it.
The stage named in the third answer and the gate named in the fourth are the
escape's two kinds.

An agent files one with `gh issue create --label escaped`, a title and a body
that uses the template's four headings, when it fixes a problem a merged
change introduced.

## Count by stage and by gate

The between-sprints routine's retro step (plan #232, *Between sprints*, step 2)
runs this and puts its output in the retro:

```bash
gh issue list --label escaped --state all --limit 1000 --json body --jq 'def counts($pattern): map(.body | (capture($pattern) // {kind: "unanswered"}) | .kind | sub("\\s+$"; "") | ascii_downcase | if startswith("##") then "unanswered" else . end) | group_by(.) | .[] | "  \(.[0]): \(length)"; "escapes: \(length)", (if length == 0 then empty else "by stage:", counts("(^|\n)## Earliest point it could have been stopped[^\n]*\n\\s*(?<kind>[^\\s][^\r\n]*)"), "by gate:", counts("(^|\n)## Which gate should have caught it[^\n]*\n\\s*(?<kind>[^\\s][^\r\n]*)") end)'
```

It prints `escapes: <total>`, then `by stage:` with one line per stage, such as
`build: 2`, then `by gate:` with one line per gate, such as `comment-debt: 2`
or `none could: 1`. An issue with no answer to a question counts as
`unanswered` for it, which includes every escape filed before the stage
question existed. With no escapes it prints `escapes: 0`. `--limit 1000` is the
cap: with more escapes than that the count is short, so raise it before then.
A gate that outnumbers the rest is the evidence for a change to that gate's
threshold or to the order of the gates; a stage that does is the evidence for a
change upstream of the gates ([How standards are made](../adr/how-standards-are-made.md)).
