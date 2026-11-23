---
name: implement-spec
description: "Implement the result of /to-spec and /to-tickets in code."
disable-model-invocation: true
---

You have been provided a spec. This spec should have tickets associated with it, describing how to implement the spec.

The issue tracker should have been provided to you. If not, tell the user to run `/setup-matt-pocock-skills`.

The goal is the entire spec implemented on a single **integration branch**, with every ticket resolved the way the issue tracker closes work.

The tickets are not a list of steps. They are a **task graph** with blocking relationships between them. This means there is always a **frontier** of tickets which are ready to be grabbed.

Communication to and from subagents should be sparse. Communicate primarily through **context pointers**: to the spec, tickets, research notes, and previous commits. Don't duplicate information already available via pointers.

**Implementer subagents** should be run in the background where possible for maximum concurrency.

## Steps

1. Read the spec and tickets to understand the task graph.

2. (optional) Use an **exploration subagent** to conduct any exploration required by the tickets - relevant codebase files or external documentation. Ensure the exploration subagent can save files - it should save its markdown notes in a directory outside the repo, accessible by all future subagents. This lets **implementer subagents** focus on implementation rather than exploration.

3. Create the integration branch. If the issue tracker closes work through PRs, or the user asks for one, open a draft PR after the first merge in step 5 (a branch with no commits ahead of main can't open one), marked as closing the spec and tickets.

4. Use **implementer subagents** to implement each ticket, each in its own worktree on its own branch. Each implementer subagent:
   - confirms its worktree is based on the integration branch before starting, and resets onto it if not;
   - calls the Skill tool with `tdd` to build the ticket;
   - merges the integration branch tip into its own branch before reporting done

5. Once an **implementer subagent** completes, merge its work to the integration branch with a **merger subagent**.

6. If this changes the **frontier** of available tickets, kick off more **implementer subagents** to work on the new tickets. This allows for maximum concurrency.

7. Once all tickets are complete, call the Skill tool with `review-against-spec` on the integration branch, then with Claude Code's own `code-review`, args `high` and the draft PR's number (or the integration branch when there is no PR). Note the integration branch tip as the **fix base**. Fix all issues raised by both reviews in a single **implementer subagent**, as commits after the fix base.

8. **Re-check the fixes.** Call the Skill tool with `code-review`, args `high`, the range `<fix base>..<integration branch tip>`, and every finding from step 7. It checks only the fix commits: that each finding is resolved, and that the fixes brought in no new issue. When it reports a regression the fixes brought in, revert that fix round, file an issue for the finding it chased, and treat the re-check as clean. When it reports anything else, fix it in one **implementer subagent**, move the fix base to the tip before those fixes, and re-check again. Done when a re-check reports nothing. After three re-checks that still report something, stop, leave the PR in draft and put the open findings to the builder (`standards` skill, *ask the builder*).

9. Once a re-check comes back clean, mark the draft PR ready for review, if one exists. Otherwise, resolve each ticket the way the issue tracker closes work, and report the integration branch.

10. Clean up all **implementer subagent** worktrees.
