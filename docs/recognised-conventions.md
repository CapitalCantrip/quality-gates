# Recognised conventions

Comment forms a language's own community requires, which a project may switch
on in its choice file as an ordinary choice (ADR-010 § Recognised conventions).
Each entry gives its full case. An entry without one does not belong here, and
any form not listed is a loosening (ADR-009).

## Rust: `// SAFETY:` above `unsafe`

**Allowed form.** A `//` line comment starting `// SAFETY:` on the line
directly above an `unsafe` block or `unsafe impl`, and the `//` lines directly
following it, up to that line. The same text anywhere else counts as an
ordinary comment.

**What it is for.** It says why one `unsafe` block cannot break memory safety:
which conditions the code relies on and why they hold there. The compiler
cannot check that reasoning, and none of the usual replacements for a comment
can carry it: a name or a test cannot say why a pointer is valid at that point.

**For.**

- The Rust standard library's own rule: "each `unsafe` block should have a
  `SAFETY:` comment explaining why the block is safe" (std-dev-guide).
- The Linux kernel's Rust guidelines require one before every `unsafe` block.
- Clippy's `undocumented_unsafe_blocks` lint enforces it. The lint is in the
  restriction group, so it is off unless a project switches it on.
- LocalBar already relies on it: 8 `unsafe` blocks, each with its `SAFETY:`
  comment, exempted by its own checker.

**Against.**

- It is free text, so an agent could write `// SAFETY: workaround for now` and
  slip an ordinary comment through. Allowing it only directly above `unsafe`
  limits that to the place the reasoning belongs.
- It opens the comment gate a little. Projects with no `unsafe` code gain
  nothing, which is why it is off by default.

**Impact.** A Rust project with `unsafe` code switches it on once. `qg status`
lists it among the project's choices; it shows no warning.

**Sources.**

- [std-dev-guide: Safety comments](https://std-dev-guide.rust-lang.org/policy/safety-comments.html)
- [Linux kernel Rust coding guidelines](https://git.zx2c4.com/linux-dev/tree/Documentation/rust/coding-guidelines.rst)
- [Clippy: `undocumented_unsafe_blocks`](https://github.com/rust-lang/rust-clippy/blob/master/clippy_lints/src/undocumented_unsafe_blocks.rs)

## Considered, not admitted

**Rust: `/// # Safety` on a public `unsafe fn`.** Clippy's `missing_safety_doc`
is in its style group and warns by default, and the std-dev-guide passes an
`unsafe fn`'s requirements to callers through a `# Safety` doc section, so a
project running `clippy -D warnings` cannot satisfy both Clippy and this gate.
Not admitted on 2026-11-01: no consumer has a public `unsafe fn`, and the entry
would open doc comments on a conflict nobody has met. A project that meets it
records a loosening until this entry is written in full.
([Clippy: `missing_safety_doc`](https://github.com/rust-lang/rust-clippy/blob/master/clippy_lints/src/doc/mod.rs))
