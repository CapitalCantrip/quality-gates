# File an escape

When you fix a problem that a merged change introduced, file an escape before
you close the fix.

**Why:** A gate that never hears what it missed cannot improve. The count of
escapes by gate is the evidence for changing a gate's threshold or the order
of the gates.

**The steps:**
1. Write the issue body with the three headings of
   `.github/ISSUE_TEMPLATE/escaped.md`: what happened, how it was found (using
   the product, a review, a crash, other), and which gate should have caught
   it, answered with one of the project's gates by name, or `none could`.
2. File it in the project's tracker with the `escaped` label; on GitHub,
   `gh issue create --label escaped --title "<what broke>" --body-file <file>`.
3. Apply no other label. `tolerated-growth` and `loosening` are the builder's
   to apply, never yours.

Done when the issue exists with the `escaped` label, its third answer names one
gate or `none could`, and the fix's commit message holds its number.

**Enforced by:** nothing yet; a judgement call.

Source: quality-gates#196.
