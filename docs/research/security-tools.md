# Secret scanning and dependency audit across four ecosystems

Research for ticket #25, a child of the wayfinder map #22. Run on 2026-10-08 on macOS (arm64).

The question: which tools would the security gates wrap, and how does each install for a builder who has only `uv` and the project's own toolchain?

## How to read this

- **Measured**: I ran the tool on a small sample and the result is given. Versions: gitleaks 8.30.1, osv-scanner 2.6.0, pip-audit (latest via `uvx`, 2026-10-08).
- **Read**: taken from the tool's documentation or README. I did not run it. All trufflehog, `npm audit`, `cargo audit` and SwiftPM claims are read.

## Answer in one table

| | Secrets | Vulnerable dependencies |
|---|---|---|
| Recommended tool | gitleaks | osv-scanner, for all four ecosystems |
| Speed | 0.2 s for staged changes, full history or the working tree of this repo (measured) | about 1 s plus network per lockfile (measured); needs `api.osv.dev` unless run offline |
| Allowing a false positive | `.gitleaksignore` fingerprint, `gitleaks:allow` trailing comment, or a config allowlist | `[[IgnoredVulns]]` in `osv-scanner.toml` with `ignoreUntil` and `reason` |
| Baseline | `--baseline-path report.json`: only findings absent from the report fail (measured) | none built in; the ignore file with expiry dates is the baseline |
| One-off history scan at setup | yes, `gitleaks git .` scans every commit (measured) | not applicable |
| Install | pinned GitHub release plus `checksums.txt`, verified with `shasum -a 256 -c` (measured) | pinned GitHub release plus `osv-scanner_SHA256SUMS` (measured) |

## Secrets: gitleaks against trufflehog

Sample: a git repo with a GitHub token, an AWS key id with AWS's documented example secret, and a token marked `# gitleaks:allow`.

| | gitleaks | trufflehog |
|---|---|---|
| Found | the GitHub token and the AWS key id (measured); the `gitleaks:allow` line was skipped (measured); the example secret ending `EXAMPLEKEY` was not flagged, by its built-in allowlist | read: 800+ detectors, and it calls each provider to check whether a secret is live |
| Pre-commit speed | `gitleaks git --staged .` in 0.18 s (measured) | read: `trufflehog git file://. --since-commit HEAD`; verification makes network calls, so it is slower and needs the network |
| False positives | `.gitleaksignore` (one fingerprint per line), `gitleaks:allow` on the line, `[allowlist]` regexes or paths in `.gitleaks.toml` | `trufflehog:ignore` on the line, `--exclude-paths`, `--results=verified` to report only live secrets |
| Baseline | `gitleaks git -r base.json .` then `--baseline-path base.json`; a new secret still failed while the old ones passed (measured) | none read |
| History at setup | `gitleaks git .`: this repo's history in 0.23 s (measured, 24 commits in this worktree's view) | yes, its default mode |
| Exit code | 1 when leaks are found (measured) | `--fail` gives 183 (read) |

gitleaks wins for a gate: offline, deterministic, fast, and it has a baseline. trufflehog's live-secret check is its strength but makes the result depend on the network and on third-party APIs.

## Vulnerable dependencies: osv-scanner against the per-ecosystem tools

Sample: `requirements.txt` with `requests==2.19.0`, then the same plus a package that does not exist on PyPI.

| | osv-scanner | pip-audit | npm audit | cargo audit |
|---|---|---|---|---|
| Ecosystems | PyPI, npm, crates.io, SwiftPM (`Package.resolved`) and more (SwiftPM read) | PyPI | npm | crates.io |
| Found on the sample | 5 advisories on `requests`, and resolved `requirements.txt` transitively to also report `urllib3` (measured) | the `requests` advisories (measured) | read | read |
| No fixed version | the FIXED VERSION column shows `--`, and the summary counts only fixable ones (read; every sample advisory had a fix) | empty Fix Versions column (read) | "No fix available" (read) | "No fixed upgrade is available!" (read) |
| Ignore list with expiry | yes: `ignoreUntil` and `reason`. A live entry filtered its advisory; an expired one was not applied and was reported as unused (measured) | `--ignore-vuln ID`, no expiry (read) | none (read) | `ignore = [...]` in `.cargo/audit.toml`, no expiry (read) |
| Exit codes | 1 vulnerabilities, 127 general error, 128 no packages found (1 measured, 127 seen on an unrecognised file name) | 1 on findings (measured) | non-zero at or above `--audit-level` (read) | 1 on findings (read) |
| Install | Go binary | `uvx pip-audit`; `-r` needs a venv, `--no-deps --disable-pip` avoids it (measured) | ships with npm | `cargo install cargo-audit` (read) |

One tool for four ecosystems, with expiring ignores, settles it: osv-scanner. Its only gap against `npm audit` and `cargo audit` is source: it reads the same advisory databases (GitHub, PyPA, RustSec) through OSV (read).

## Invented and look-alike packages

None of these tools checks for a typo of a popular name. For a name that does not exist:

- pip-audit lists it under "Skip Reason: Dependency not found on PyPI" but does not fail on that alone (measured: the exit was 1 because of `requests`).
- osv-scanner prints "failed resolution ... not found" on stderr while resolving `requirements.txt`, then carries on (measured). It is a side effect, not a check, and does not apply to lockfiles.
- OSV includes `MAL-` advisories for known malicious packages from the OpenSSF malicious-packages feed, so a registered typosquat that has been reported does fail (read).

A registry lookup is cheap (measured, one request each, no auth):

| Registry | URL | Exists | Missing |
|---|---|---|---|
| PyPI | `https://pypi.org/pypi/<name>/json` | 200, 0.25 s | 404, 0.33 s |
| npm | `https://registry.npmjs.org/<name>` | 200, 0.26 s | 404, 0.29 s |
| crates.io | `https://index.crates.io/<prefix>/<name>` (sparse index) | 200, 0.19 s | 404, 0.59 s |

SwiftPM has no central registry: dependencies are git URLs, so "does it exist" is a `git ls-remote`, and look-alikes are look-alike URLs. A look-alike check needs a list of popular names per registry and an edit-distance test; that is a new check of our own, and the map already marks it as unspecified.

## Install without Homebrew

Both Go binaries publish a checksum file beside each release asset. I downloaded gitleaks 8.30.1 (`gitleaks_8.30.1_darwin_arm64.tar.gz` plus `gitleaks_8.30.1_checksums.txt`) and osv-scanner 2.6.0 (`osv-scanner_darwin_arm64` plus `osv-scanner_SHA256SUMS`) with `curl`, and both passed `shasum -a 256 -c` (measured). So `qg` can pin a version and the expected SHA-256 per platform in its own source, download into a cache, and refuse a mismatch. Asset names differ between the projects: gitleaks uses `linux_x64`, osv-scanner `linux_amd64`. trufflehog also signs its checksums (`.sig`, `.pem`, cosign).

Cloud sessions: the same `curl` from `github.com` release URLs works wherever the session's network policy allows GitHub (read, not run in a cloud session). osv-scanner also needs `api.osv.dev`; where that is blocked, `--offline-vulnerabilities --download-offline-databases` still needs one download, so the gate must report "could not check" rather than pass. The binaries are 21 MB and 55 MB, so the download belongs in the cloud SessionStart hook added in v0.5.2, not in each commit.

## Recommendation

| Language | Secrets | Dependencies | Invented packages |
|---|---|---|---|
| Python | gitleaks | osv-scanner on `uv.lock` / `requirements.txt` | PyPI JSON lookup on new names |
| TypeScript | gitleaks | osv-scanner on `package-lock.json` | npm registry lookup |
| Rust | gitleaks | osv-scanner on `Cargo.lock` | crates.io sparse-index lookup |
| Swift | gitleaks | osv-scanner on `Package.resolved` (read only; no sample run) | `git ls-remote` on new URLs; no typo check possible |

gitleaks runs on staged changes in the pre-commit hook, with a full-history scan once at setup that writes the baseline. osv-scanner runs in CI and at ticket end, not on each commit, since it needs the network. `qg` fetches both as pinned, checksummed releases; Homebrew is not required.

## Notes for Stage 3 (#29 to #31)

- **`comment-debt` conflict, secrets:** `# gitleaks:allow` is a trailing comment, and `comment-debt`'s `PRAGMA` in `src/quality_gates/comment_debt.py` exempts only `noqa`, `type: ignore`, `pragma: no cover/branch` and `fmt:`. So the marker is counted as comment debt, which makes an allowed secret visible. Prefer `.gitleaksignore` fingerprints, which keep the decision out of the code and are countable by line. Decide whether `gitleaks:allow` is banned outright.
- **`comment-debt` conflict, dependencies:** none. osv-scanner's ignores live in `osv-scanner.toml`, not in code.
- **Baselines:** gitleaks has a real one (`--baseline-path`). osv-scanner has none; its `ignoreUntil` entries act as an expiring baseline, which fits the ratchet rule better than a permanent one, since an expired entry fails again.
- **ADR-002 "standard is an exit code":** gitleaks exits 1; osv-scanner exits 1 on findings but 127 on a parse error and 128 on no packages, which a wrapper must not treat as a pass.
- **Not covered by this ticket:** a look-alike check needs its own design (map's "Not yet specified").
