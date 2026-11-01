import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from quality_gates import project_files, skills_sync
from quality_gates.errors import TOOL_ERROR_EXIT, ToolError
from quality_gates.manifest import BROKEN_EXIT, COMPONENTS_PATH, BrokenFileError, load_components

INSTALLED = "installed"
MISSING = "missing"
DIFFERENT = "different"
UNKNOWN = "unknown"
PARTLY = "partly installed"
NOT_APPLICABLE = "not applicable"
PROVIDED = "provided by quality-gates"
DECLINED = "offered, declined"
NOT_OFFERED = "not yet offered"
FROM_CHOICE = "choice file"
FROM_DETECTION = "detection"
HAS_SOMETHING = (INSTALLED, PARTLY, DIFFERENT)

PIN_PATTERN = re.compile(r"quality-gates\s*@\s*git\+\S*?@(v[0-9][\w.\-]*)")
ASKING_RULE = "asking-rule"
PROVIDED_BY_PACKAGE = {"command", "dependency"}
PIN_VERDICTS = {
    True: "matches",
    False: "differs from the installed version",
    None: "could not tell whether it matches",
}
HOOK_STATES = {
    project_files.UNSHIPPED: UNKNOWN,
    project_files.MISSING: MISSING,
    project_files.DIFFERS: DIFFERENT,
    project_files.SAME: INSTALLED,
}
FILE_STATES = {
    project_files.MISSING: MISSING,
    project_files.READABLE: INSTALLED,
    project_files.UNREADABLE: UNKNOWN,
}
SUMMARY = "show each component, whether this project has it, and the pin"
NO_PARTS_NOTICE ="No quality-gates parts found in this folder. Run /setup-standards to add them."


@dataclass(frozen=True)
class Project:
    root: Path
    source: Path
    hooks: Path
    shipped_skills: frozenset

    @property
    def claude_dir(self):
        return project_files.claude_dir(self.root)


def project_at(root, source, hooks):
    return Project(root, source, hooks, frozenset(skills_sync.skill_names(source)))


def skill_status(project, part):
    if part.id not in project.shipped_skills:
        return UNKNOWN
    dest = project_files.skills_dir(project.root)
    if not skills_sync.files_under(dest / part.id):
        return MISSING
    return DIFFERENT if skills_sync.skill_differences(part.id, project.source, dest) else INSTALLED


def copied_hook_status(project, name):
    return HOOK_STATES[project_files.copied_hook(project_files.hooks_dir(project.claude_dir), name, project.hooks)]


def hook_status(project, part):
    found = copied_hook_status(project, part.id)
    if found != INSTALLED or part.id != project_files.STAGE_GUARD:
        return found
    try:
        registered = project_files.stage_guard_registered(project_files.settings_file(project.claude_dir))
    except (project_files.SettingsError, OSError, UnicodeDecodeError):
        return UNKNOWN
    return INSTALLED if registered else MISSING


def claude_md_line_status(project, part):
    if part.id != ASKING_RULE:
        return UNKNOWN
    try:
        return INSTALLED if project_files.has_asking_line(project.root) else MISSING
    except (OSError, UnicodeDecodeError):
        return UNKNOWN


def file_status(project, part):
    return FILE_STATES[project_files.file_state(project.root, part.id)]


def step_status(texts, marker):
    if any(text is not None and project_files.runs_command(text, marker) for text in texts):
        return INSTALLED
    return UNKNOWN if None in texts else MISSING


def ci_step_status(project, part):
    return step_status(project_files.ci_texts(project.root, part.found_in), part.marker)


def precommit_step_status(project, part):
    return step_status(project_files.pre_commit_texts(project.root), part.marker)


PART_STATUS = {
    "skill": skill_status,
    "hook": hook_status,
    "claude_md_line": claude_md_line_status,
    "baseline": file_status,
    "config": file_status,
    "ci_step": ci_step_status,
    "precommit_step": precommit_step_status,
}


def part_status(project, part):
    return PART_STATUS[part.kind](project, part)


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


def part_report(project, part, used):
    if part.kind in PROVIDED_BY_PACKAGE:
        found = PROVIDED
    elif part.applies_to(used):
        found = part_status(project, part)
    else:
        found = NOT_APPLICABLE
    return {"kind": part.kind, "id": part.id, "status": found}


def counts_toward_status(part):
    return part["status"] not in (PROVIDED, NOT_APPLICABLE)


CHOICE_STATUSES = {project_files.DECLINED: DECLINED, project_files.CHOSEN: None, project_files.UNLISTED: NOT_OFFERED}


def choice_status(component, choice, rolled):
    if choice is None or component.core:
        return None
    return CHOICE_STATUSES[project_files.standing(choice, component.id, rolled in HAS_SOMETHING)]


def component_status(component, rolled, choice):
    if rolled == NOT_APPLICABLE:
        return NOT_APPLICABLE
    return choice_status(component, choice, rolled) or rolled


def wants_attention(component, choice, rolled):
    chosen = choice is not None and choice.recorded(component.id) == project_files.CHOSEN
    return component.core or chosen or rolled in HAS_SOMETHING


def needs_attention(component, parts, choice, rolled):
    if rolled == NOT_APPLICABLE or not wants_attention(component, choice, rolled):
        return []
    return [f"{p['kind']} {p['id']}: {p['status']}" for p in parts if counts_toward_status(p) and p["status"] != INSTALLED]


def installed_state(component, parts, used):
    if not component.applies_to(used):
        return NOT_APPLICABLE
    return roll_up([p["status"] for p in parts if counts_toward_status(p)])


def component_report(project, component, used, choice=None):
    wanted = list(component.languages)
    parts = [part_report(project, p, used) for p in component.parts]
    rolled = installed_state(component, parts, used)
    return {
        "id": component.id,
        "name": component.name,
        "core": component.core,
        "status": component_status(component, rolled, choice),
        "install_status": rolled,
        "description": component.description,
        "origin": component.origin.as_dict(),
        "languages": wanted,
        "parts": parts,
        "needs_attention": needs_attention(component, parts, choice, rolled),
    }


def components_present(project, manifest, used):
    reports = (component_report(project, component, used) for component in manifest.components)
    return {report["id"] for report in reports if report["status"] in HAS_SOMETHING}


def read_pin(project):
    for text in project_files.pin_texts(project.root):
        found = PIN_PATTERN.search(text)
        if found:
            return found.group(1)
    return None


def pin_matches(pin, installed):
    if pin is None or installed == skills_sync.UNKNOWN_VERSION:
        return None
    return pin.lstrip("v") == installed


def recorded_languages(detected, choice):
    if choice is None:
        return sorted(detected), FROM_DETECTION, {}
    unrecorded = {language: files for language, files in detected.items() if language not in choice.languages}
    return list(choice.languages), FROM_CHOICE, unrecorded


def build_report(project, manifest, choice=None):
    used, used_from, unrecorded = recorded_languages(project_files.detected_languages(project.root), choice)
    pin, installed = read_pin(project), skills_sync.installed_version()
    return {
        "format_version": manifest.format_version,
        "installed_version": installed,
        "pin": pin,
        "pin_matches": pin_matches(pin, installed),
        "languages": used,
        "languages_from": used_from,
        "unrecorded_languages": unrecorded,
        "components": [component_report(project, c, set(used), choice) for c in manifest.components],
    }


def origin_text(origin):
    return f"{origin['type']}: {origin['name']}" if "name" in origin else origin["type"]


def pin_line(report):
    installed = report["installed_version"]
    if report["pin"] is None:
        return f"Pin: pin not found. Installed quality-gates: {installed}."
    return f"Pin: {report['pin']}. Installed quality-gates: {installed} ({PIN_VERDICTS[report['pin_matches']]})."


def unrecorded_lines(report):
    found = report["unrecorded_languages"]
    if not found:
        return []
    named = "; ".join(f"{language} ({project_files.files_named(files)})" for language, files in sorted(found.items()))
    return ["", f"Code in a language {project_files.CHOICE_FILE} does not record: {named}.",
            "Run `qg setup` to record it, or exclude those files in the choice file."]


def status_text(item):
    if item["status"] == DECLINED and item["install_status"] != MISSING:
        return f"{DECLINED} ({item['install_status']})"
    return item["status"]


def component_lines(item):
    lines = [f"  {item['id']:<24} {status_text(item):<18} {origin_text(item['origin'])}", f"    {item['description']}"]
    if item["needs_attention"]:
        lines.append("    Needs attention: " + "; ".join(item["needs_attention"]))
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
    applicable = where(items, lambda i: i["status"] not in (NOT_APPLICABLE, DECLINED, NOT_OFFERED))
    return bool(applicable) and all(i["status"] == MISSING for i in applicable)


def render_table(report):
    core, optional, inapplicable = grouped(report["components"])
    lines = [pin_line(report)] + unrecorded_lines(report)
    lines += section("Core components (every project has these)", core)
    lines += section("Optional components", optional)
    lines += section("Not applicable to this project", inapplicable)
    if nothing_installed(report["components"]):
        lines += ["", NO_PARTS_NOTICE]
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(prog="qg status")
    parser.add_argument("--json", action="store_true", help="print the same report as JSON")
    return parser


def main(argv=None, root=None, source=skills_sync.SHIPPED, hooks=project_files.HOOKS_SOURCE, manifest=None,
         components_path=COMPONENTS_PATH):
    args = build_parser().parse_args(argv)
    try:
        manifest = manifest or load_components(components_path)
    except BrokenFileError as error:
        print(f"qg status: {error}", file=sys.stderr)
        return BROKEN_EXIT
    try:
        root = project_files.git_root() if root is None else root
    except ToolError as error:
        print(f"qg status: {error}", file=sys.stderr)
        return TOOL_ERROR_EXIT
    try:
        choice = project_files.read_choice(root)
    except BrokenFileError as error:
        print(f"qg status: {error}", file=sys.stderr)
        return BROKEN_EXIT
    project = project_at(root, source, hooks)
    report = build_report(project, manifest, choice)
    print(json.dumps(report, indent=2) if args.json else render_table(report))
    return 0
