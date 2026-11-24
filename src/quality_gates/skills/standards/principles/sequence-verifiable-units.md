# Sequence verifiable units

Order work as small units that each end in a state you can check, and do not
start the next until the current one passes.

**Why:** A break caught at the unit that caused it is cheap to find. A break
caught after a batch is buried, and more work already rests on it. The same
units, delivered in order, let a reviewer watch the work go red, then green,
instead of taking it on trust.

**Pattern:**
- **Run each unit as a bracket:** a known-good state, one change, the check,
  then the next unit. In a sweep or migration, check every change, even when a
  script made it (*build the lever*).
- **Start from a clean base.** Rebase onto the main branch first, so each
  check measures against the real baseline.
- **Order commits to prove the work.** The failing test first, then the fix.
  Other orders that prove: the removal before the reshape, the baseline before
  the change, the scaffold before the feature. Each commit stands on its own.

**Stop:** when a unit's check fails, fix that unit before writing the next.

**Enforced by:** nothing yet; a judgement call. Each check must be real
(*prove it works*).

Source: adapted from pstack's *sequence-verifiable-units* (Lauren Tan, MIT; LICENSE-pstack).
