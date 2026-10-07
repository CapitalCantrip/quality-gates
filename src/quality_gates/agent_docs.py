import argparse
import difflib
import sys
from pathlib import Path

from quality_gates import project_files

TEMPLATES = Path(__file__).parent / "agent_doc_templates"
DOCS_DIR = Path("docs") / "agents"
BASE_DIR = ".base"
AGENT_SKILLS_HEADING = "## Agent skills"
PR_TEMPLATE = Path(".github") / "pull_request_template.md"

TRACKER_SUMMARIES = {
    "github": "GitHub Issues on this repo, through the `gh` CLI",
    "gitlab": "GitLab Issues on this repo, through the `glab` CLI",
    "local": "Markdown files under `.scratch/` in this repo",
}

AGENT_SKILLS_BLOCK = """## Agent skills

### Issue tracker

{tracker}. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

{pull_requests}"""

PULL_REQUESTS_HEADING = "### Pull requests"

PULL_REQUESTS_SECTION = """### Pull requests

Write every PR body with the `pr` skill: Summary, Evidence, Merge Danger. `.github/pull_request_template.md` holds the same headings.
"""


def plan(tracker):
    return {
        DOCS_DIR / "issue-tracker.md": f"issue-tracker-{tracker}.md",
        DOCS_DIR / "triage-labels.md": "triage-labels.md",
        DOCS_DIR / "domain.md": "domain.md",
        PR_TEMPLATE: "pull-request.md",
    }


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else None


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def diff(old, new, name):
    lines = difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=f"{name} (before)", tofile=f"{name} (now)",
    )
    return "".join(lines)


def customised(have, base, template, name):
    if base == template:
        return "customised by you; the template has not changed", ""
    if base is None:
        return "customised, with no record of the template it started from; your file against the current template:", diff(have, template, name)
    return "customised by you, and the template has changed since; the template's change, for you to adopt or not:", diff(base, template, name)


def reconcile(root, name, template):
    path, base_path = root / name, root / DOCS_DIR / BASE_DIR / name.name
    have, base = read(path), read(base_path)
    if have is None or have == template or have == base:
        status = "created" if have is None else "already in place" if have == template else "updated to the new template; you had not edited it"
        write(path, template)
        write(base_path, template)
        return status, ""
    return customised(have, base, template, name.name)


def add_agent_skills_block(root, tracker):
    path = project_files.instruction_file(root)
    text = read(path) or ""
    lines = (text.rstrip("\n") + "\n").splitlines(keepends=True) if text else []
    if AGENT_SKILLS_HEADING + "\n" in lines:
        return add_pull_requests_section(path, lines)
    block = AGENT_SKILLS_BLOCK.format(tracker=TRACKER_SUMMARIES[tracker], pull_requests=PULL_REQUESTS_SECTION)
    write(path, (text.rstrip("\n") + "\n\n" if text.strip() else "") + block)
    return "added"


def block_end(lines, start):
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            return index
    return len(lines)


def add_pull_requests_section(path, lines):
    if PULL_REQUESTS_HEADING + "\n" in lines:
        return "already in place"
    end = block_end(lines, lines.index(AGENT_SKILLS_HEADING + "\n"))
    before = "".join(lines[:end]).rstrip("\n") + "\n\n"
    after = "".join(lines[end:])
    write(path, before + PULL_REQUESTS_SECTION + ("\n" + after if after else ""))
    return "pull requests section added"


def run(root, tracker, templates=TEMPLATES):
    report = []
    for name, template_name in plan(tracker).items():
        template = (templates / template_name).read_text(encoding="utf-8")
        status, detail = reconcile(root, name, template)
        report.append((name.as_posix(), status, detail))
    report.append((f"{project_files.instruction_file(root).name} Agent skills block", add_agent_skills_block(root, tracker), ""))
    return report


def build_parser():
    parser = argparse.ArgumentParser(
        prog="qg-agent-docs",
        description="Write docs/agents/ from Matt Pocock's setup templates, write the PR template, and add the Agent skills "
                    "block to CLAUDE.md. Never overwrites a file you edited; shows the template's "
                    "changes instead.",
    )
    parser.add_argument("--tracker", choices=sorted(TRACKER_SUMMARIES), required=True)
    parser.add_argument("--root", type=Path, default=Path("."), help="default: the current directory")
    return parser


def main(argv=None, templates=TEMPLATES):
    args = build_parser().parse_args(argv)
    for name, status, detail in run(args.root, args.tracker, templates):
        print(f"{name}: {status}")
        if detail:
            print(detail)
    sys.exit(0)
