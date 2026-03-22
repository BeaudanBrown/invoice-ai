from __future__ import annotations

import argparse
import sys

from .config import RuntimeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invoice-ai",
        description="invoice-ai runtime scaffold",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_config = subparsers.add_parser(
        "show-config",
        help="Print the resolved runtime configuration as JSON.",
    )
    show_config.set_defaults(handler=handle_show_config)

    init_paths = subparsers.add_parser(
        "init-paths",
        help="Create the configured runtime directories if they do not exist.",
    )
    init_paths.set_defaults(handler=handle_init_paths)

    return parser


def handle_show_config(_args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_env()
    print(config.to_json_text())
    return 0


def handle_init_paths(_args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_env()
    config.paths.ensure()
    print(config.to_json_text())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
