from __future__ import annotations

import argparse
import json
import sys

from .config import RuntimeConfig
from .erp.schemas import ToolRequest
from .erp.tools import ERPToolExecutor


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

    run_tool = subparsers.add_parser(
        "run-tool",
        help="Execute one semantic ERP tool request from a JSON file or stdin.",
    )
    run_tool.add_argument(
        "--request-file",
        default="-",
        help="Path to a JSON request envelope. Use - for stdin.",
    )
    run_tool.set_defaults(handler=handle_run_tool)

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


def handle_run_tool(args: argparse.Namespace) -> int:
    payload = _read_request_payload(args.request_file)
    request = ToolRequest.from_dict(payload)
    executor = ERPToolExecutor.from_runtime_config(RuntimeConfig.from_env())
    print(executor.execute(request).to_json_text())
    return 0


def _read_request_payload(path: str) -> dict[str, object]:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
