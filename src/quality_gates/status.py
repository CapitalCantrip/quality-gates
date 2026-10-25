import argparse
import filecmp
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from quality_gates import complexity_scan, languages, project_files, skills_sync

MANIFEST_PATH = Path(__file__).parent / "components.json"

INSTALLED = "installed"
MISSING = "missing"
DIFFERENT = "different"
UNKNOWN = "unknown"
PARTLY = "partly installed"
NOT_APPLICABLE = "not applicable"
PROVIDED = "provided by quality-gates"

BUILD_OUTPUT_FOLDERS = {"target", "Pods", "DerivedData", "site-packages"}
HIDDEN_PREFIX = "."
PROJECT_MARKERS = {
    "python": ("pyproject.toml", "setup.py"),
    "swift": ("Package.swift",),
    "rust": ("Cargo.toml",),
    "typescript": ("package.json",),
}
XCODE_PROJECT_SUFFIX = ".xcodeproj"
WORKFLOW_SUFFIXES = (".yml", ".yaml")
PIN_PATTERN = re.compile(r"quality-gates\s*@\s*git\+\S*?@(v[0-9][\w.\-]*)")
ASKING_RULE = "asking-rule"
PROVIDED_BY_PACKAGE = {"command", "dependency"}
NO_PARTS_NOTICE = "No quality-gates parts found in this folder. Run /setup-standards to add them."


@dataclass(frozen=True)
class Project:
    root: Path
    source: Path
    hooks: Path

    @property
    def claude_dir(self):
        return self.root / ".claude"

    def workflows(self):
        folder = self.root / ".github" / "workflows"
        if not folder.is_dir():
            return []
        return sorted(p for p in folder.iterdir() if p.suffix in WORKFLOW_SUFFIXES)


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def skill_status(project, part):
    if part["id"] not in skills_sync.skill_names(project.source):
        return UNKNOWN
    dest = project.claude_dir / "skills"
    if not skills_sync.files_under(dest / part["id"]):
        return MISSING
    return DIFFERENT if skills_sync.skill_differences(part["id"], project.source, dest) else INSTALLED


def copied_hook_status(project, name):
    shipped, copy = project.hooks / name, project.claude_dir / "hooks" / name
    if not shipped.is_file():
        return UNKNOWN
    if not copy.is_file():
        return MISSING
    return INSTALLED if filecmp.cmp(shipped, copy, shallow=False) else DIFFERENT


def hook_status(project, part):
    found = copied_hook_status(project, part["id"])
    if found != INSTALLED or part["id"] != project_files.STAGE_GUARD:
        return found
    try:
        registered = project_files.stage_guard_registered(project.claude_dir / "settings.json")
    except (project_files.SettingsError, OSError, UnicodeDecodeError):
        return UNKNOWN
    return INSTALLED if registered else MISSING


def claude_md_line_status(project, part):
    if part["id"] != ASKING_RULE:
        return UNKNOWN
    try:
        return INSTALLED if project_files.has_asking_line(project.root) else MISSING
    except (OSError, UnicodeDecodeError):
        return UNKNOWN


def baseline_status(project, part):
    path = project.root / part["id"]
    if not path.exists():
        return MISSING
    return INSTALLED if path.is_file() and os.access(path, os.R_OK) else UNKNOWN


def runs_command(text, command):
    return re.search(rf"(?<![\w-]){re.escape(command)}(?![\w-])", text) is not None


def ci_step_files(project, part):
    if "found_in" not in part:
        return project.workflows()
    path = project.root / part["found_in"]
    return [path] if path.is_file() else []


def ci_step_status(project, part):
    unreadable = False
    for path in ci_step_files(project, part):
        try:
            if runs_command(path.read_text(encoding="utf-8"), part["marker"]):
                return INSTALLED
        except (OSError, UnicodeDecodeError):
            unreadable = True
    return UNKNOWN if unreadable else MISSING


PART_STATUS = {
    "skill": skill_status,
    "hook": hook_status,
    "claude_md_line": claude_md_line_status,
    "baseline": baseline_status,
    "ci_step": ci_step_status,
}


def part_status(project, part):
    reader = PART_STATUS.get(part["kind"])
    return reader(project, part) if reader else UNKNOWN


def roll_up(statuses):
    found = set(statuses)
    if not found:
        return MISSING
    for outcome in (DIFFERENT, UNKNOWN):
        if outcome in found:
            return outcome
    if found == {INSTALLED}:
        return INSTALLED
    return MISSING if found == {MISSING} else PARTLY


def marker_languages(root):
    return {name for name, markers in PROJECT_MARKERS.items() if any((root / marker).exists() for marker in markers)}


def is_detection_skipped(folder):
    name = folder.name
    return name.startswith(HIDDEN_PREFIX) or name in BUILD_OUTPUT_FOLDERS or complexity_scan.is_skipped(folder)


def used_languages(root):
    suffixes = {suffix: name for name, language in languages.LANGUAGES.items() for suffix in language.suffixes}
    found = marker_languages(root)
    for folder, directories, files in os.walk(root):
        if found >= set(languages.LANGUAGES):
            break
        directories[:] = [d for d in directories if not is_detection_skipped(Path(folder) / d)]
        found |= project_suffix_languages(directories, files, suffixes)
    return found


def project_suffix_languages(directories, files, suffixes):
    found = {suffixes[Path(f).suffix] for f in files if Path(f).suffix in suffixes}
    if any(d.endswith(XCODE_PROJECT_SUFFIX) for d in directories):
        found.add("swift")
    return found


def applies(languages_wanted, used):
    return not languages_wanted or bool(set(languages_wanted) & used)


def part_report(project, part, used):
    if part["kind"] in PROVIDED_BY_PACKAGE:
        found = PROVIDED
    elif applies(part.get("languages"), used):
        found = part_status(project, part)
    else:
        found = NOT_APPLICABLE
    return {"kind": part["kind"], "id": part["id"], "status": found}


def counts_toward_status(part):
    return part["status"] not in (PROVIDED, NOT_APPLICABLE)


def component_report(project, component, used):
    wanted = component["languages"]
    parts = [part_report(project, p, used) for p in component["parts"]]
    applicable = applies(wanted, used)
    return {
        "id": component["id"],
        "name": component["name"],
        "core": component["core"],
        "status": roll_up([p["status"] for p in parts if counts_toward_status(p)]) if applicable else NOT_APPLICABLE,
        "description": component["description"],
        "origin": component["origin"],
        "languages": wanted,
        "parts": parts,
    }


def read_pin(project):
    candidates = [project.root / "pyproject.toml"] + project.workflows()
    for path in candidates:
        try:
            found = PIN_PATTERN.search(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if found:
            return found.group(1)
    return None


def build_report(project, manifest):
    used = used_languages(project.root)
    pin, installed = read_pin(project), skills_sync.installed_version()
    return {
        "format_version": manifest["format_version"],
        "installed_version": installed,
        "pin": pin,
        "pin_matches": None if pin is None else pin.lstrip("v") == installed,
        "components": [component_report(project, c, used) for c in manifest["components"]],
    }


def origin_text(origin):
    return f"{origin['type']}: {origin['name']}" if "name" in origin else origin["type"]


def pin_line(report):
    installed = report["installed_version"]
    if report["pin"] is None:
        return f"Pin: pin not found. Installed quality-gates: {installed}."
    verdict = "matches" if report["pin_matches"] else "differs from the installed version"
    return f"Pin: {report['pin']}. Installed quality-gates: {installed} ({verdict})."


def component_lines(item):
    lines = [f"  {item['id']:<24} {item['status']:<18} {origin_text(item['origin'])}", f"    {item['description']}"]
    needs = [f"{p['kind']} {p['id']}: {p['status']}" for p in item["parts"] if counts_toward_status(p) and p["status"] != INSTALLED]
    if is_applicable(item) and needs:
        lines.append("    Needs attention: " + "; ".join(needs))
    return lines


def section(title, items):
    if not items:
        return []
    return ["", title] + [line for item in items for line in component_lines(item)]


def is_applicable(item):
    return item["status"] != NOT_APPLICABLE


def where(items, test):
    return [item for item in items if test(item)]


def grouped(items):
    applicable = where(items, is_applicable)
    core = where(applicable, lambda i: i["core"])
    return core, where(applicable, lambda i: not i["core"]), where(items, lambda i: not is_applicable(i))


def nothing_installed(items):
    applicable = where(items, is_applicable)
    return bool(applicable) and all(i["status"] == MISSING for i in applicable)


def render_table(report):
    core, optional, inapplicable = grouped(report["components"])
    lines = [pin_line(report)]
    lines += section("Core components (every project has these)", core)
    lines += section("Optional components", optional)
    lines += section("Not applicable to this project", inapplicable)
    if nothing_installed(report["components"]):
        lines += ["", NO_PARTS_NOTICE]
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(prog="qg", description="Report on what quality-gates has installed in this project.")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("status", help="show each component, whether this project has it, and the pin")
    report.add_argument("--json", action="store_true", help="print the same report as JSON")
    return parser


def main(argv=None, root=None, source=skills_sync.SHIPPED, hooks=project_files.HOOKS_SOURCE, manifest=None):
    args = build_parser().parse_args(argv)
    project = Project(Path.cwd() if root is None else root, source, hooks)
    report = build_report(project, manifest or load_manifest())
    print(json.dumps(report, indent=2) if args.json else render_table(report))
    return 0
