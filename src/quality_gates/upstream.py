import argparse
import datetime
import difflib
import os
import sys
import urllib.error
import urllib.request

from quality_gates.manifest import BROKEN_EXIT, COMPONENTS_PATH, UPSTREAM_PATH, ManifestError, load_components, load_sources

RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"
HEAD = "https://api.github.com/repos/{repo}/commits/HEAD"
NOT_FOUND = 404
SHORT_SHA = 7
QUIET_AFTER_DAYS = 365
DAYS_PER_MONTH = 30

ADOPT = (
    "To adopt a change: carry it into the local file (verbatim copies are replaced, adapted ones "
    "are edited by hand, redoing each change `docs/upstream-adaptations.md` lists for them), set `commit` for that source in `src/quality_gates/upstream.json` to the "
    "new head, and release it through a PR. To decline it, move `commit` to the new head in a PR "
    "that says why, so the next run stops reporting it."
)

RENEW = (
    "This check reads the `last_release` recorded in `components.json`; it does not ask the source. A source "
    "listed here may have released since the record was written. To keep a source: look up its real newest "
    "release on its repo or package index, confirm its licence and practice still hold, then set `last_release` "
    "for it in `src/quality_gates/components.json` to that date. If it needs no releases, mark it stable "
    "with the reason instead. To drop it, remove its parts and its admission."
)


class FetchError(Exception):
    pass


def github_fetch(url, accept="application/vnd.github.raw"):
    headers = {"Accept": accept, "User-Agent": "qg-upstream"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as reply:
            return reply.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        if error.code == NOT_FOUND:
            return None
        raise FetchError(f"{url}: HTTP {error.code}")
    except urllib.error.URLError as error:
        raise FetchError(f"{url}: {error.reason}")


def head_commit(repo, fetch):
    sha = fetch(HEAD.format(repo=repo), "application/vnd.github.sha")
    if not sha:
        raise FetchError(f"{repo}: no HEAD commit")
    return sha.strip()


def file_change(repo, path, old_ref, new_ref, fetch):
    old = fetch(RAW.format(repo=repo, ref=old_ref, path=path))
    new = fetch(RAW.format(repo=repo, ref=new_ref, path=path))
    if old == new:
        return None
    if new is None:
        return "removed upstream"
    lines = difflib.unified_diff(
        (old or "").splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=f"{path}@{old_ref[:SHORT_SHA]}", tofile=f"{path}@{new_ref[:SHORT_SHA]}",
    )
    return "".join(lines)


def source_changes(source, fetch):
    head = head_commit(source.repo, fetch)
    if head == source.commit:
        return head, []
    changes = []
    for path, local in source.files.items():
        change = file_change(source.repo, path, source.commit, head, fetch)
        if change:
            changes.append((path, local, change))
    return head, changes


def section(source, head, changes):
    repo, old = source.repo, source.commit[:SHORT_SHA]
    lines = [f"## {repo}: {len(changes)} watched file(s) changed, {old} → {head[:SHORT_SHA]}", ""]
    lines.append(f"Our copy is {source.copied}.")
    for path, local, change in changes:
        lines += ["", f"### `{path}` → `{local}`", "", "```diff", change.rstrip("\n"), "```"]
    return "\n".join(lines)


def report(sources, fetch):
    sections = []
    for source in sources:
        head, changes = source_changes(source, fetch)
        if changes:
            sections.append(section(source, head, changes))
    return sections


def quiet_sources(admissions, today):
    quiet = []
    for admission in admissions:
        if admission.last_release is None:
            continue
        age = (today - admission.last_release).days
        if age > QUIET_AFTER_DAYS:
            quiet.append((admission, age // DAYS_PER_MONTH))
    return quiet


def upkeep_section(admission, months):
    return f"## {admission.name}: no release recorded since {admission.last_release.isoformat()} ({months} months)"


def upkeep(components_path, today):
    try:
        quiet = quiet_sources(load_components(components_path).admissions, today)
    except ManifestError as error:
        print(f"qg-upstream: {error}", file=sys.stderr)
        sys.exit(BROKEN_EXIT)
    if not quiet:
        print("No outside source has gone quiet.")
        sys.exit(0)
    print("\n\n".join([upkeep_section(a, months) for a, months in quiet] + [RENEW]))
    sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="qg-upstream",
        description="Report what changed upstream (Matt Pocock's skills, pstack) in the files this "
                    "repo copies or adapts, since the commits recorded in upstream.json. Exit 0: "
                    "nothing changed. Exit 1: changes, printed as Markdown. Exit 2: GitHub unreachable. "
                    "Exit 3: upstream.json is missing or malformed.",
    )
    parser.add_argument("--upkeep", action="store_true",
                        help="instead, report each outside source in components.json whose recorded last_release "
                             "is over 12 months old and that is not marked stable (exit 1 when there is one)")
    return parser


def main(argv=None, record_path=UPSTREAM_PATH, fetch=github_fetch, components_path=COMPONENTS_PATH, today=None):
    arguments = build_parser().parse_args(argv)
    if arguments.upkeep:
        upkeep(components_path, today or datetime.date.today())
    try:
        sources = load_sources(record_path)
    except ManifestError as error:
        print(f"qg-upstream: {error}", file=sys.stderr)
        sys.exit(BROKEN_EXIT)
    try:
        sections = report(sources, fetch)
    except FetchError as error:
        print(f"qg-upstream: {error}", file=sys.stderr)
        sys.exit(2)
    if not sections:
        print("No watched upstream file has changed.")
        sys.exit(0)
    print("\n\n".join(sections + [ADOPT]))
    sys.exit(1)
