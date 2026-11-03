import argparse
import difflib
import sys
from pathlib import Path

from quality_gates import project_files
from quality_gates.errors import TOOL_ERROR_EXIT, ToolError

TEMPLATES = Path(__file__).parent / "agent_doc_templates"
AGENT_SKILLS_HEADING = "## Agent skills"

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
        project_files.ISSUE_TRACKER_DOC: f"issue-tracker-{tracker}.md",
        project_files.TRIAGE_LABELS_DOC: "triage-labels.md",
        project_files.DOMAIN_DOC: "domain.md",
        project_files.PR_TEMPLATE: "pull-request.md",
    }


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
    base_name = project_files.template_base(name)
    have, base = project_files.read_kept(root, name), project_files.read_kept(root, base_name)
    if have is None or have == template or have == base:
        status = "created" if have is None else "already in place" if have == template else "updated to the new template; you had not edited it"
        project_files.write_kept(root, name, template)
        project_files.write_kept(root, base_name, template)
        return status, ""
    return customised(have, base, template, name.name)


def add_agent_skills_block(root, tracker):
    text = project_files.read_instruction_file(root) or ""
    lines = (text.rstrip("\n") + "\n").splitlines(keepends=True) if text else []
    if AGENT_SKILLS_HEADING + "\n" in lines:
        return add_pull_requests_section(root, lines)
    block = AGENT_SKILLS_BLOCK.format(tracker=TRACKER_SUMMARIES[tracker], pull_requests=PULL_REQUESTS_SECTION)
    project_files.write_instruction_file(root, (text.rstrip("\n") + "\n\n" if text.strip() else "") + block)
    return "added"


def block_end(lines, start):
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            return index
    return len(lines)


def add_pull_requests_section(root, lines):
    if PULL_REQUESTS_HEADING + "\n" in lines:
        return "already in place"
    end = block_end(lines, lines.index(AGENT_SKILLS_HEADING + "\n"))
    before = "".join(lines[:end]).rstrip("\n") + "\n\n"
    after = "".join(lines[end:])
    project_files.write_instruction_file(root, before + PULL_REQUESTS_SECTION + ("\n" + after if after else ""))
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
    parser.add_argument("--root", type=Path, help="default: the top of the git repository")
    return parser


def main(argv=None, templates=TEMPLATES):
    args = build_parser().parse_args(argv)
    try:
        root = args.root or project_files.git_root()
    except ToolError as error:
        print(f"qg-agent-docs: {error}", file=sys.stderr)
        sys.exit(TOOL_ERROR_EXIT)
    for name, status, detail in run(root, args.tracker, templates):
        print(f"{name}: {status}")
        if detail:
            print(detail)
    sys.exit(0)
