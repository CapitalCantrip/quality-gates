# Escape log

An escape is a problem that got past every gate and was found later (see
`GLOSSARY.md`). Each one is an issue on this repo's tracker with the `escaped`
label, written from `.github/ISSUE_TEMPLATE/escaped.md`: what happened, how it
was found, and which gate should have caught it. The gate named in the third
answer is the escape's kind.

An agent files one with `gh issue create --label escaped`, a title and a body
that uses the template's three headings, when it fixes a problem a merged
change introduced.

## Count by kind

The between-sprints routine's retro step (plan #232, *Between sprints*, step 2)
runs this and puts its output in the retro:

```bash
gh issue list --label escaped --state all --limit 1000 --json body --jq '"escapes: \(length)", (map(.body | (capture("(^|\n)## Which gate should have caught it[^\n]*\n\\s*(?<kind>[^\\s][^\r\n]*)") // {kind: "unanswered"}) | .kind | sub("\\s+$"; "") | ascii_downcase | if startswith("##") then "unanswered" else . end) | group_by(.) | .[] | "\(.[0]): \(length)")'
```

It prints `escapes: <total>` and then one line per kind, such as
`comment-debt: 2` or `none could: 1`; an issue with no third answer counts as
`unanswered`. With no escapes it prints `escapes: 0`. `--limit 1000` is the
cap: with more escapes than that the count is short, so raise it before then.
A kind that outnumbers the rest is the evidence for a change to that gate's
threshold or to the order of the gates ([How standards are made](../adr/how-standards-are-made.md)).
