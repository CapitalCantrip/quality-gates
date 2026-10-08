# quality-gates

The engineering standards that projects built with AI coding agents, by people
who are not software engineers, pin and are held to.

## People and projects

**Builder**:
The person who directs coding agents and judges whether the result works, but
does not review the code.
_Avoid_: user, developer, operator

**Consumer**:
A project that pins a tag of this repo and is held to its standards.
_Avoid_: client, downstream project

**Pin**:
The release tag a consumer installs; a fix reaches a consumer only when its pin
is bumped.
_Avoid_: version, dependency

**Upstream**:
A published body of work this repo adapts text from: Matt Pocock's skills or
Lauren Tan's pstack.
_Avoid_: vendor, source

## The three layers

**Workflow**:
The order of work, chosen by the size of the work.

**Size rule**:
The table that maps the size of the work to the skill it starts at.
_Avoid_: routing, triage

**Principle**:
A named, one-rule standard for judging a step, applied by the agent reading it.
_Avoid_: rule, guideline, value

**Lesson**:
A correction recorded in one project; it becomes a principle or a gate only
when it has recurred and would recur elsewhere.
_Avoid_: learning, retro item

**Gate**:
A command that fails the commit or the build when a standard is broken, needing
no one's cooperation.
_Avoid_: linter, check, rule

**Function**:
What a complexity gate scores: a function, a method, a closure, or a method of
a nested class, each scored on its own. A class is never scored.
_Avoid_: block, unit

**Asking rule**:
When and how an agent puts a decision to the builder: plain stakes, two or
three options, a recommendation.

**Stage guard**:
The gate that refuses an agent's bulk staging of changed files.
_Avoid_: git guardrail, commit guard

## Debt

**Debt**:
Violations of a gate that existed when the gate was adopted.

**Baseline**:
The committed record of a gate's debt; the gate fails only on what is new or
worse, and on paid debt not yet recorded.
_Avoid_: allowlist, ignore file, suppression
