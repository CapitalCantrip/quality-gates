# Lint rules that catch swallowed errors

Research for ticket #24, a child of the wayfinder map #22. Run on 2026-10-08 on macOS.

The question: which existing lint rules catch an error that is caught and then ignored, in Python, TypeScript, Rust and Swift, and can a project turn them on with a baseline for the cases it already has?

## How to read this

- **Measured**: I ran the linter on a small sample and the result is given. Versions: ruff 0.16.10, SwiftLint 0.65.1, clippy 0.1.98.
- **Read**: taken from the rule's documentation or source. I did not run it. All TypeScript claims are read; ESLint was not run.

"Fires wrongly" means flagging code a careful reviewer would accept as it stands.

## Answer in one table

| | Python | TypeScript | Rust | Swift |
|---|---|---|---|---|
| Core rule set | ruff `S110`, `S112`, `E722`, `BLE001` | ESLint `no-empty`, `@typescript-eslint/no-floating-promises`, `@typescript-eslint/no-empty-function` | rustc `unused_must_use`, clippy `let_underscore_must_use`, `unused_result_ok` | compiler warning on unused `try?`, SwiftLint `no_empty_block` |
| Catches the main shape | yes | yes | yes | empty `catch` only; `_ = try?` is missed by everything |
| Wrong-fire rate | low for `S110`/`S112`/`E722`, medium for `BLE001` | low for `no-empty`, medium for `no-floating-promises` | medium for `let_underscore_must_use` | high for `no_empty_block` outside `catch` |
| Built-in baseline | no (`--add-noqa` writes suppressions) | yes, bulk suppressions file (ESLint 9.24+) | no | yes, `--baseline` / `--write-baseline` |
| Per-line suppression | `# noqa: S110` | `// eslint-disable-next-line rule` | `#[allow(...)]` / `#[expect(...)]` attribute | `// swiftlint:disable:next rule` |
| Suppression countable | yes, by regex | yes, by regex | yes, by regex on attributes | yes, by regex |

## Python (ruff)

Sample: bare `except: pass`, `except Exception: pass`, `except ValueError: pass`, `except Exception as e: log(e)`, `except Exception: ...`, `except OSError: return None`, `contextlib.suppress(Exception)`, `except Exception: raise`, `except ValueError: continue` in a loop.

| Rule | Catches (measured) | Misses (measured) | Wrong fires |
|---|---|---|---|
| `S110` try-except-pass | `pass` body after bare `except` or `except Exception` | `...` body; `return None`; narrow types unless `check-typed-exception = true` (read) | low: a body of only `pass` is the definition of the smell |
| `S112` try-except-continue | same, with `continue` (read) | narrow `except ValueError: continue` (measured, not flagged at default) | low |
| `E722` bare-except | `except:` | everything typed | low |
| `BLE001` blind-except | `except Exception` / `BaseException` whose body does not re-raise or log via `logging.exception` (read); fired on the `log(e)` case because `log` is not `logging` | narrow types | medium: top-level handlers in CLIs and workers catch `Exception` on purpose |
| `SIM105` suppressible-exception | every `try`/`except`/`pass`, including `...` | — | **it is not a swallowed-error rule.** It recommends `contextlib.suppress`, which hides the same swallow from `S110`. Do not use it as a gate |
| `TRY203` useless-try-except | `except Exception: raise` | — | not relevant to swallowing |

Gaps: nothing flags `contextlib.suppress(Exception)` (measured), and nothing flags `except SomeError: return None` or `return default`. A tight gate needs `S110` with `lint.flake8-bandit.check-typed-exception = true`, plus a tiny custom count of `contextlib.suppress(` with `Exception`/`BaseException`.

Baseline: ruff has none. `ruff check --add-noqa` writes a `# noqa: <code>` on each existing hit, which is a baseline in the code.

**Conflict with `comment-debt`:** its `PRAGMA` pattern in `src/quality_gates/comment_debt.py` exempts `# noqa: CODES`. A `# noqa: S110` is therefore invisible to `comment-debt`, so an agent can swallow an error and silence the gate for free. A ratchet must count `noqa` for these codes itself, or the exemption must exclude them (a standard change, needs an ADR).

## TypeScript (ESLint, typescript-eslint) — read only

| Rule | Catches | Misses | Wrong fires |
|---|---|---|---|
| `no-empty` (core) | empty block, including `catch {}`; `allowEmptyCatch` turns the catch case off | a block holding only a comment is not empty, so `catch { /* ignore */ }` passes | low |
| `@typescript-eslint/no-empty-function` | `.catch(() => {})` and empty arrow callbacks | `.catch(() => undefined)`, `.catch(noop)` | medium: empty default callbacks are common |
| `@typescript-eslint/no-floating-promises` | a promise not awaited, returned, or given a rejection handler; `void p` is an allowed opt-out (`ignoreVoid`) | `.catch(() => {})` counts as handled | medium; needs type information, which slows the lint |
| `@typescript-eslint/no-misused-promises` | promises passed where a void callback is expected | — | medium |

Gaps: `catch (e) { return null }` and `catch { /* ok */ }`. `sonarjs/no-ignored-exceptions` (read) also flags a catch whose body ignores the error, but adds a plugin.

Baseline: ESLint 9.24 added bulk suppressions (`--suppress-all`, `--suppress-rule`, file `eslint-suppressions.json`) with per-file, per-rule counts that only go down. That is the ratchet shape `comment-debt` uses.

## Rust (rustc, clippy)

Sample: `let _ = r();`, `r().ok();`, `r();`, `let _x = r();`, `let _ = std::fs::remove_file("x");`, `r().unwrap_or_default();`.

| Lint | Catches (measured) | Misses (measured) | Wrong fires |
|---|---|---|---|
| rustc `unused_must_use` (warn by default) | bare `r();` | anything bound or chained | none worth naming |
| clippy `let_underscore_must_use` (restriction) | `let _ = r();` | `let _x = r();` | medium: `let _ = fs::remove_file(...)` in clean-up code is idiomatic, and it flagged it |
| clippy `unused_result_ok` (restriction) | `r().ok();` | — | low |
| clippy `let_underscore_untyped` (restriction) | every `let _ =` without a type | — | high; noisy, not a swallowed-error rule |
| rustc `let_underscore_drop` (allow by default) | `let _ =` on a type with a destructor | — | high; about drop timing, not errors |

Gaps: `let _x = r();`, `.unwrap_or_default()`, `.unwrap_or(..)` on a `Result`, and `if let Ok(..)` with no `else` all discard the error and no lint flags them.

Baseline: clippy has none. The suppression is an attribute, `#[allow(clippy::let_underscore_must_use)]` or `#[expect(...)]`, not a comment, so `comment-debt` never sees it and a ratchet can count it by regex. `#[expect]` (stable since Rust 1.81) also fails when the suppressed case is gone, which keeps the count honest.

## Swift (compiler, SwiftLint)

Sample: `do {...} catch {}`, `catch { }`, `_ = try? g()`, `try? g()` with the result dropped, `let x = try? g()`.

| Rule | Catches (measured) | Misses (measured) | Wrong fires |
|---|---|---|---|
| Swift compiler warning "result of 'try?' is unused" (read) | `try? g()` as a statement with a non-Void result | `_ = try? g()`; `try?` on a Void call (the common case) | none |
| SwiftLint `no_empty_block` (opt-in) | empty `catch {}` | `catch { _ = error }`, `catch { return nil }` | high: also flags every empty function, initializer and closure; configurable per block kind (`disabled_block_types`), but not to catch only |
| SwiftLint `empty_count` and others | — | — | not related |

There is no SwiftLint rule for `try?` whose result is dropped. SwiftLint supports `custom_rules` with a regex, so `_\s*=\s*try\?` and `^\s*try\?` can be a custom rule. It is a regex, so it will miss a split line.

Baseline: SwiftLint 0.55+ has `--write-baseline` and `--baseline`, which ignore existing violations. Suppression is `// swiftlint:disable:next <rule>`, which a ratchet can count, and which `comment-debt` would count as a comment once #3 brings Swift in, unless it is exempted.

## What each answer means for the map

- **A ratchet on suppressions is feasible in all four languages.** Every suppression is one line with a fixed shape and the rule code in it, so one counter per file can count them, the way `comment-debt` does.
- **Two native baselines exist** (ESLint bulk suppressions, SwiftLint `--baseline`); ruff and clippy have none. A per-file count of new hits against a stored count, owned by quality-gates, is the one shape that works everywhere.
- **The `noqa` exemption is a hole.** `comment-debt` exempts `# noqa` today. For the swallowed-error gate, a `# noqa: S110` must count. The same question will arise for `// eslint-disable` and `// swiftlint:disable` under #3.
- **Every tool misses "return a default in the handler".** No rule finds `except X: return None`, `catch { return null }`, `.unwrap_or_default()` or `catch { return nil }`. That is the shape agents favour. A gate built on these rules covers the empty handler only; the ADR must name the gap.

## Recommendation per language

- **Python:** gate on ruff `S110`, `S112`, `E722`, with `check-typed-exception = true`. Leave `BLE001` as a report entry, not a gate. Do not use `SIM105`. Count `# noqa` for those codes as debt.
- **TypeScript:** gate on `no-empty` (with `allowEmptyCatch: false`) and `@typescript-eslint/no-floating-promises`, baselined with ESLint bulk suppressions. Add `no-empty-function` for `.catch(() => {})` only if the trial shows low noise.
- **Rust:** keep `unused_must_use` at deny and add clippy `let_underscore_must_use` and `unused_result_ok`. Require `#[expect]` over `#[allow]` for exceptions and count them.
- **Swift:** the weakest. Gate on a SwiftLint custom regex rule for `_ = try?` and an empty `catch`, not on `no_empty_block`, using SwiftLint's `--baseline`. Treat it as provisional until a maintained Swift project tries it.

## What was not measured

- ESLint and typescript-eslint were not run; every TypeScript row is read.
- The Swift compiler's unused-`try?` warning was not compiled here; SwiftLint was run, the compiler was not.
- Wrong-fire rates are judgement from the samples and rule docs, not counts over a real codebase.
