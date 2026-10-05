import argparse
import filecmp
import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from quality_gates import project_files

SHIPPED = Path(__file__).parent / "skills"
DEFAULT_DEST = Path(".claude") / "skills"
SKILL_FILE = "SKILL.md"


def installed_version():
    try:
        return version("quality-gates")
    except PackageNotFoundError:
        return "unknown"


def skill_names(source):
    return sorted(p.name for p in source.iterdir() if (p / SKILL_FILE).is_file())


def files_under(root):
    if not root.is_dir():
        return set()
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def skill_differences(name, source, dest):
    want, have = source / name, dest / name
    wanted, present = files_under(want), files_under(have)
    found = [f"{name}/{f.as_posix()}: missing" for f in sorted(wanted - present)]
    found += [f"{name}/{f.as_posix()}: not shipped" for f in sorted(present - wanted)]
    found += [
        f"{name}/{f.as_posix()}: differs"
        for f in sorted(wanted & present)
        if not filecmp.cmp(want / f, have / f, shallow=False)
    ]
    return found


def differences(dest, source=SHIPPED):
    found = []
    for name in skill_names(source):
        found += skill_differences(name, source, dest)
    return found


def sync(dest, source=SHIPPED):
    dest.mkdir(parents=True, exist_ok=True)
    names = skill_names(source)
    for name in names:
        shutil.rmtree(dest / name, ignore_errors=True)
        shutil.copytree(source / name, dest / name)
    return names


def project_root(dest):
    return dest.resolve().parent.parent


def check(dest, source=SHIPPED, hooks=project_files.HOOKS_SOURCE):
    found = differences(dest, source) + project_files.differences(dest.parent, project_root(dest), hooks)
    for line in found:
        print(line)
    if found:
        print(f"\n{dest} does not match quality-gates {installed_version()}. Run qg-skills and commit the result.")
        return 1
    print(f"{dest} matches quality-gates {installed_version()}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="qg-skills",
        description="Copy the quality-gates skills and stage guard into a repo, register the guard, and add the asking-rule line to CLAUDE.md, so local and cloud sessions both get them.",
    )
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="default: .claude/skills")
    parser.add_argument("--check", action="store_true", help="exit 1 if the copies differ from this version's")
    return parser


def install(dest, source, hooks):
    names = sync(dest, source)
    project_files.sync(dest.parent, project_root(dest), hooks)
    print(f"Copied {', '.join(names)} from quality-gates {installed_version()} to {dest}")
    print(f"Installed the stage guard in {dest.parent} and the asking-rule line in "
          f"{project_files.instruction_file(project_root(dest)).name}")
    return 0


def main(argv=None, source=SHIPPED, hooks=project_files.HOOKS_SOURCE):
    args = build_parser().parse_args(argv)
    try:
        sys.exit(check(args.dest, source, hooks) if args.check else install(args.dest, source, hooks))
    except project_files.SettingsError as error:
        print(error, file=sys.stderr)
        sys.exit(2)
