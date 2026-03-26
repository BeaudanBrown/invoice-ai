from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from .artifacts.models import QuotePreview
from .artifacts.pdf import QuotePreviewRenderer
from .config import RuntimeConfig
from .control_plane.models import RequestSource
from .control_plane.store import ControlPlaneStore
from .erp.schemas import ToolRequest
from .execution import execute_tool_request
from .service.http import InvoiceAIHTTPServer


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
    run_tool.add_argument(
        "--write-approval-artifacts",
        action="store_true",
        help="Persist approval artifacts when the tool result requires approval.",
    )
    run_tool.set_defaults(handler=handle_run_tool)

    render_quote = subparsers.add_parser(
        "render-quote-preview",
        help="Render a deterministic quote-preview PDF from a JSON payload.",
    )
    render_quote.add_argument(
        "--input-file",
        default="-",
        help="Path to a quote-preview JSON payload. Use - for stdin.",
    )
    render_quote.set_defaults(handler=handle_render_quote_preview)

    serve_http = subparsers.add_parser(
        "serve-http",
        help="Run the invoice-ai HTTP control-plane service.",
    )
    serve_http.set_defaults(handler=handle_serve_http)

    return parser


def handle_show_config(_args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_env()
    print(config.to_json_text())
    return 0


def handle_init_paths(_args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_env()
    config.paths.ensure()
    ControlPlaneStore.from_runtime_config(config).ensure()
    print(config.to_json_text())
    return 0


def handle_run_tool(args: argparse.Namespace) -> int:
    payload = _read_request_payload(args.request_file)
    try:
        request = ToolRequest.from_dict(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    config = RuntimeConfig.from_env()
    response = execute_tool_request(
        config=config,
        request=request,
        source=RequestSource.CLI,
        write_approval_artifacts=args.write_approval_artifacts,
    )
    print(response.to_json_text())
    return 0


def handle_render_quote_preview(args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_env()
    payload = _read_request_payload(args.input_file)
    preview = QuotePreview.from_dict(payload)
    output_path = QuotePreviewRenderer(config.paths.artifacts_dir).render(preview)
    print(
        json.dumps(
            {
                "draft_key": preview.draft_key,
                "output_path": str(output_path),
                "currency": preview.currency,
                "total": round(preview.total, 2),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def handle_serve_http(_args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_env()
    config.paths.ensure()
    ControlPlaneStore.from_runtime_config(config).ensure()
    server = InvoiceAIHTTPServer(config)
    print(
        json.dumps(
            {
                "listen_address": config.service.listen_address,
                "port": config.service.port,
                "base_url": config.service.base_url(),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _read_request_payload(path: str) -> dict[str, object]:
    if path == "-":
        payload = json.load(sys.stdin)
    else:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Request payload must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
