import argparse
import sys

from quality_gates import explain, setup_choices, status

DESCRIPTION = "Report on what quality-gates has installed in this project."
COMMANDS = {"status": status, "setup": setup_choices, "explain": explain}


def build_parser():
    parser = argparse.ArgumentParser(prog="qg", description=DESCRIPTION)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, module in COMMANDS.items():
        commands.add_parser(name, help=module.SUMMARY, add_help=False)
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    split = next((at + 1 for at, word in enumerate(argv) if word in COMMANDS), len(argv))
    args = build_parser().parse_args(argv[:split])
    return COMMANDS[args.command].main(argv[split:])
