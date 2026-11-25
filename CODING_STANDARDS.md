# Coding standards

Judgement rules a reviewer checks a change against. Each rule has its reason
and its source. A rule a script can check becomes a gate and leaves this file.

1. **Every change a consumer receives has its own CHANGELOG line.**
   Reason: the `changelog` workflow only checks that `CHANGELOG.md` moved, so
   a release can ship a change no line tells the consumer about (PR #219 had
   to add lines PR #211 missed).
   Source: sprint 3 retro, finding 6 (#207, 2026-11-24).
