import argparse

from quality_gates import status

DESCRIPTION = "Report on what quality-gates has installed in this project."
COMMANDS = {"status": status}


def build_parser():
    parser = argparse.ArgumentParser(prog="qg", description=DESCRIPTION)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, module in COMMANDS.items():
        commands.add_parser(name, help=module.SUMMARY, add_help=False)
    return parser


def main(argv=None):
    args, rest = build_parser().parse_known_args(argv)
    return COMMANDS[args.command].main(rest)
