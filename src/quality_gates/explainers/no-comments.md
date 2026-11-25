# No code comments

## What it catches

New comments in the code: notes written beside the code rather than in it. It reads Python, Rust, TypeScript (and JavaScript), Swift and shell, and each language is its own row in setup, switched on only when you choose it: `no-comments` for Python, `no-comments-rust`, `no-comments-typescript`, `no-comments-swift` and `no-comments-shell` for the others. Every comment counts, once per line, including the documentation comments some languages use. Text that only looks like a comment, inside a string for example, does not count. Short markers a tool reads, such as one that tells a linter to skip a line, are allowed, as long as they carry no explanation. The exception is a marker that switches off one of our own gates, such as Python's `# pragma: no cover`, which hides code from the coverage score: it is a silencer, recorded in `silencer-baseline.json`, and a new one fails. It is found on the line wherever it sits, a string included, because coverage.py reads the line the same way.

A few comment forms are ones a language's own community requires. These are the recognised conventions, each off until the project switches it on. Today there is one: `rust-safety`, Rust's `// SAFETY:` note directly above `unsafe` code, which says why that code is safe. With it on, those notes do not count.

## Why it matters

A comment is not checked by anything. When the code changes and the comment does not, the comment says something false, and nothing notices. Agents also read a comment that excuses a shortcut as permission to take the same shortcut elsewhere. Knowledge kept in a test, a clear name, a decision record or an issue fails or shows when it stops being true.

## What it asks of you

Before a language is switched on, setup shows the comments it already has: the total, where they are, and the files with the most. `comment-debt --report <language>` prints the same report at any time, followed by every file that has comments. You then choose one of two:

- **Record as debt.** Every comment already there is written down in `comment-debt.json`, and only new ones fail.
- **Clean first.** You pick part of the code to clear now, by folder, file or kind of comment. The agent moves those comments' knowledge somewhere better without changing what the code does, and reruns the report until that part no longer shows. If you ask, it opens an issue listing every file left. Then choosing the language records the rest as debt.

Either way the language is switched on only once its comments are recorded, so no commit is blocked by comments that were already there. From then on, a file that gains a comment fails, and a file that loses one fails until the lower count is recorded, so cleared comments cannot come back.

If the project's Rust code has `// SAFETY:` notes, setup asks whether to switch `rust-safety` on and recommends yes. It switches it on before choosing Rust, or those notes are recorded as debt.

## Want to go deeper?

- [Safety comments policy, Rust standard library developers guide](https://std-dev-guide.rust-lang.org/policy/safety-comments.html): why Rust asks for a `SAFETY:` note above `unsafe` code, the one convention the gate knows today. Checked 2026-11-25.
