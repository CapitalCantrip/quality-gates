# Fix root causes

When debugging, trace each symptom to its cause and fix it there, not where
it shows.

**Why:** Symptom fixes pile up. Each workaround makes the system harder to
reason about, and the real bug stays. A root-cause fix is slower once and
cheaper every time after.

**Pattern:**
- **Reproduce first.** No fix before a run that shows the failure.
- **Ask "why" until the answer is a cause, not another symptom.**
- **Add no guard that silences the failure.** A nil check that stops a crash
  hides the bug; it does not fix it.
- **A workaround that needs explaining is the wrong code.** Fix the code
  instead of writing the explanation.
- **Fix the pattern, not the instance.** Search for the same mistake and fix
  every place it occurs.
- **When stuck, measure.** Add logging or read the actual error; do not guess.
- **"Fails after restart": suspect saved state before code.** Config files,
  caches, lock files and serialised state come first. If clearing one restores
  the behaviour, validate that state as the fix.

**Stop:** a fix is not done until the run that reproduced the failure passes
and the search for the same pattern is clean.

**Enforced by:** nothing yet; a judgement call. The `diagnosing-bugs` skill
is the loop that applies it.

Source: adapted from pstack's *fix-root-causes* (Lauren Tan, MIT; LICENSE-pstack).
