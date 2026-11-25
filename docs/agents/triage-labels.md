# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Before `ready-for-agent`

The brief has a Done-when, and every command in it, and every claim the brief
makes about how the code behaves, has been run once against `main`, with the
output pasted in the brief.

When a rule from the parent issue or ADR holds only in part until a later
build, the Done-when names the exception and the issue that owns it ("gates
read no flags, except `--format` until #138"), and so does the compendium
page that states the rule.

A brief that changes how several languages are read is cut into one ticket
and one PR per language, after the skeleton ticket that adds the shared
part. A fix to one language's patterns then reverts without taking the
others with it (PR #219 carried four languages, so reverting its round 3
took out every language's fixes).
