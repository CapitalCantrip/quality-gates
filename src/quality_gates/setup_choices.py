import argparse
import json
import sys
from dataclasses import dataclass

from quality_gates import project_files, skills_sync, status
from quality_gates.errors import TOOL_ERROR_EXIT, ToolError
from quality_gates.manifest import BROKEN_EXIT, COMPONENTS_PATH, STEP_KINDS, BrokenFileError, known_languages, load_components

SUMMARY = "propose the languages and components, and record them in quality-gates.json with --go"
REFUSED_EXIT = 1
CORE = "core"
CHOSEN = "chosen"
OFFERED = "offered"
DECLINED = status.DECLINED
NOT_APPLICABLE = status.NOT_APPLICABLE
TICKED = (CORE, CHOSEN, OFFERED)
STEP_COSTS = (("precommit_step", "commit delay"), ("ci_step", "CI time"))
OUTSIDE_TOOLS = "outside tools: "
NO_COST = "none"
LOOSENING_ISSUE = "#115"


class Refused(Exception):
    pass


@dataclass(frozen=True)
class Proposal:
    languages: tuple
    added_by_hand: tuple
    components: tuple
    choice: object


def proposed_languages(choice, detected, add, remove):
    known_languages(add, "--add-language")
    known_languages(remove, "--remove-language")
    for name in remove:
        if name in detected:
            raise Refused(f"removing {name} is refused while it still has code ({project_files.files_named(detected[name])}); "
                          f"removing a language with code is loosening, which waits on {LOOSENING_ISSUE}")
    wanted = set(choice.languages if choice else ()) | set(detected) | set(add)
    return tuple(sorted(wanted - set(remove)))


def cost_of(component):
    kinds = {part.kind for part in component.parts}
    costs = [cost for kind, cost in STEP_COSTS if kind in kinds]
    tools = [part.id for part in component.parts if part.kind == "dependency"]
    return costs + ([OUTSIDE_TOOLS + ", ".join(tools)] if tools else [])


def is_gate(component):
    return any(part.kind in STEP_KINDS for part in component.parts)


def check_component_names(manifest, names):
    for name in names:
        if manifest.component(name) is None:
            raise Refused(f"'{name}' is not a component in this release's components.json")


def check_declines(manifest, declines, has):
    for component in manifest.components:
        if component.id not in declines:
            continue
        if component.core:
            raise Refused(f"'{component.id}' is the core, and the core never switches off")
        if is_gate(component) and component.id in has:
            raise Refused(f"switching off '{component.id}', a gate this project has, is loosening; "
                          f"it is refused until recorded loosening ({LOOSENING_ISSUE}) ships")


RECORDED_CHOICES = {project_files.DECLINED: DECLINED, project_files.CHOSEN: CHOSEN, project_files.UNLISTED: OFFERED}


def previous_choice(component, choice, installed):
    if choice is None:
        return CHOSEN if component.id in installed else OFFERED
    return RECORDED_CHOICES[choice.recorded(component.id)]


def component_choice(component, used, choice, installed, flags):
    if component.core:
        return CORE
    if not component.applies_to(used):
        return NOT_APPLICABLE
    if component.id in flags.decline:
        return DECLINED
    if component.id in flags.choose:
        return CHOSEN
    return previous_choice(component, choice, installed)


def recorded_choice(root, choice, used, components):
    comment_gate_exclude = set(choice.comment_gate_exclude if choice else ()) | project_files.comment_gate_exclusions(root)
    return project_files.Choice(
        languages=used,
        chosen=tuple(sorted(c["id"] for c in components if c["choice"] in (CHOSEN, OFFERED))),
        declined=tuple(sorted(c["id"] for c in components if c["choice"] == DECLINED)),
        exclude=project_files.scope_of(root).excluded,
        commit_time_limit_seconds=choice.commit_time_limit_seconds if choice else project_files.DEFAULT_COMMIT_TIME_LIMIT_SECONDS,
        comment_gate_exclude=tuple(sorted(comment_gate_exclude)),
        conventions=choice.conventions if choice else (),
    )


def component_row(component, made):
    return {"id": component.id, "name": component.name, "description": component.description,
            "core": component.core, "cost": cost_of(component), "choice": made, "recommended": made in TICKED}


def propose(project, manifest, flags):
    root = project.root
    choice = project_files.read_choice(root)
    detected = project_files.detected_languages(root)
    used = proposed_languages(choice, detected, flags.add_language, flags.remove_language)
    check_component_names(manifest, flags.choose + flags.decline)
    installed = status.components_present(project, manifest, set(used))
    check_declines(manifest, flags.decline, installed | set(choice.chosen if choice else ()))
    rows = tuple(component_row(c, component_choice(c, set(used), choice, installed, flags)) for c in manifest.components)
    by_hand = tuple(name for name in used if name not in detected)
    return Proposal(used, by_hand, rows, recorded_choice(root, choice, used, rows))


def names_with(proposal, *made):
    return [row["id"] for row in proposal.components if row["choice"] in made]


def report_of(proposal, planned):
    return {
        "languages": list(proposal.languages),
        "languages_added_by_hand": list(proposal.added_by_hand),
        "exclude": list(proposal.choice.exclude),
        "comment_gate_exclude": list(proposal.choice.comment_gate_exclude),
        "components": list(proposal.components),
        "planned_changes": [{"file": change.name, "state": state} for change, state in planned],
    }


def row_lines(row):
    tick = "[x]" if row["recommended"] else "[ ]"
    return [f"  {tick} {row['id']:<24} {row['choice']:<18} {row['description']}",
            "        cost: " + ("; ".join(row["cost"]) or NO_COST)]


def listed(label, names):
    return [f"  {label}: " + ", ".join(names)] if names else []


def your_components(proposal):
    return (["", "Your components"]
            + listed("On", names_with(proposal, CORE, CHOSEN))
            + listed("Offered, recommended yes", names_with(proposal, OFFERED))
            + listed("Offered and declined", names_with(proposal, DECLINED))
            + listed("Not applicable", names_with(proposal, NOT_APPLICABLE))
            + listed("Languages added by hand", list(proposal.added_by_hand)))


def render(proposal, planned, written):
    lines = ["Languages: " + (", ".join(proposal.languages) or "none"), "", "Components"]
    lines += [line for row in proposal.components for line in row_lines(row)]
    lines += ["", "Excluded from detection and the gates: " + (", ".join(proposal.choice.exclude) or "nothing")]
    lines += ["Comment gate exclusions: " + (", ".join(proposal.choice.comment_gate_exclude) or "none")]
    lines += your_components(proposal)
    lines += ["", "Planned changes"] + [f"  {change.name}: {state}" for change, state in planned]
    lines += ["", "Recorded: " + ", ".join(written) if written else "Run `qg setup --go` to record these choices."]
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(prog="qg setup")
    parser.add_argument("--go", action="store_true", help="write the planned changes")
    parser.add_argument("--json", action="store_true", help="print the proposal as JSON")
    parser.add_argument("--add-language", action="append", default=[], metavar="NAME", help="record a language")
    parser.add_argument("--remove-language", action="append", default=[], metavar="NAME",
                        help="stop recording a language that has no code")
    parser.add_argument("--choose", action="append", default=[], metavar="ID", help="switch a component on")
    parser.add_argument("--decline", action="append", default=[], metavar="ID", help="decline a component")
    return parser


def failed(error, code):
    print(f"qg setup: {error}", file=sys.stderr)
    return code


def run(args, project, manifest):
    proposal = propose(project, manifest, args)
    changes = [project_files.choice_change(proposal.choice)]
    planned = [(change, project_files.planned_state(project.root, change)) for change in changes]
    written = project_files.apply_planned(project.root, changes) if args.go else []
    print(json.dumps(report_of(proposal, planned), indent=2) if args.json else render(proposal, planned, written))
    return 0


def main(argv=None, root=None, source=skills_sync.SHIPPED, hooks=project_files.HOOKS_SOURCE, manifest=None,
         components_path=COMPONENTS_PATH):
    args = build_parser().parse_args(argv)
    try:
        manifest = manifest or load_components(components_path)
        root = project_files.git_root() if root is None else root
        return run(args, status.project_at(root, source, hooks), manifest)
    except BrokenFileError as error:
        return failed(error, BROKEN_EXIT)
    except ToolError as error:
        return failed(error, TOOL_ERROR_EXIT)
    except Refused as error:
        return failed(error, REFUSED_EXIT)
