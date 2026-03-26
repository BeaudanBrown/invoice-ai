from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
from urllib import request

from fastapi import FastAPI
import uvicorn

from ..config import DependencyEndpoints, RuntimeConfig, ServiceConfig
from ..paths import RuntimePaths
from ..service.http import create_app
from .fixtures import DEV_OPERATOR_ID, DEV_OPERATOR_TOKEN, DevFixturePaths, dev_turn_defaults, prepare_dev_fixtures
from .mock_services import create_mock_docling_app, create_mock_erp_app


@dataclass(frozen=True)
class DevStackInfo:
    fixture_paths: DevFixturePaths
    service_url: str
    operator_id: str
    operator_token: str
    erp_url: str
    docling_url: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture_paths": {
                "root": str(self.fixture_paths.root),
                "state_dir": str(self.fixture_paths.state_dir),
                "operators_file": str(self.fixture_paths.operators_file),
                "sample_supplier_invoice_pdf": str(
                    self.fixture_paths.sample_supplier_invoice_pdf
                ),
            },
            "service_url": self.service_url,
            "operator_id": self.operator_id,
            "operator_token": self.operator_token,
            "erp_url": self.erp_url,
            "docling_url": self.docling_url,
        }


class UvicornThread:
    def __init__(self, app: FastAPI, *, host: str = "127.0.0.1", port: int) -> None:
        self.host = host
        self.port = port
        self.server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="warning")
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self) -> None:
        self.thread.start()
        _wait_for_port(self.host, self.port)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


class DevStack:
    def __init__(self, *, root: Path | None = None, service_port: int | None = None) -> None:
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None
        if root is None:
            self._tempdir = tempfile.TemporaryDirectory(prefix="invoice-ai-dev-")
            root = Path(self._tempdir.name)
        self.root = root
        self.fixture_paths = prepare_dev_fixtures(root)
        self.service_port = service_port or _find_free_port()
        self.erp_port = _find_free_port()
        self.docling_port = _find_free_port()
        self._servers: list[UvicornThread] = []

    def __enter__(self) -> DevStackInfo:
        erp_server = UvicornThread(create_mock_erp_app(), port=self.erp_port)
        docling_server = UvicornThread(create_mock_docling_app(), port=self.docling_port)
        config = RuntimeConfig(
            service=ServiceConfig(
                listen_address="127.0.0.1",
                port=self.service_port,
                public_url=None,
                host_name=None,
                operator_tokens_file=self.fixture_paths.operators_file,
            ),
            paths=RuntimePaths(
                state_dir=self.fixture_paths.state_dir,
                control_plane_db_path=self.fixture_paths.state_dir / "control-plane.sqlite3",
                documents_dir=self.fixture_paths.state_dir / "documents",
                memory_dir=self.fixture_paths.state_dir / "memory",
                ingest_dir=self.fixture_paths.state_dir / "ingest",
                approvals_dir=self.fixture_paths.state_dir / "approvals",
                revisions_dir=self.fixture_paths.state_dir / "revisions",
                artifacts_dir=self.fixture_paths.state_dir / "artifacts",
                cache_dir=self.fixture_paths.state_dir / "cache",
            ),
            dependencies=DependencyEndpoints(
                erpnext_url=f"http://127.0.0.1:{self.erp_port}",
                erpnext_credentials_file=None,
                ollama_url="http://127.0.0.1:11434",
                docling_url=f"http://127.0.0.1:{self.docling_port}",
                n8n_url=None,
            ),
        )
        service_server = UvicornThread(create_app(config), port=self.service_port)
        self._servers = [erp_server, docling_server, service_server]
        for server in self._servers:
            server.start()
        return DevStackInfo(
            fixture_paths=self.fixture_paths,
            service_url=f"http://127.0.0.1:{self.service_port}",
            operator_id=DEV_OPERATOR_ID,
            operator_token=DEV_OPERATOR_TOKEN,
            erp_url=f"http://127.0.0.1:{self.erp_port}",
            docling_url=f"http://127.0.0.1:{self.docling_port}",
        )

    def __exit__(self, exc_type, exc, tb) -> None:
        for server in reversed(self._servers):
            server.stop()
        self._servers.clear()
        if self._tempdir is not None:
            self._tempdir.cleanup()


def serve_dev_stack(*, root: Path | None = None, service_port: int | None = None) -> int:
    with DevStack(root=root, service_port=service_port) as info:
        print(json.dumps(info.as_dict(), indent=2, sort_keys=True), flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0


def run_dev_smoke_test(*, root: Path | None = None, service_port: int | None = None) -> dict[str, Any]:
    with DevStack(root=root, service_port=service_port) as info:
        headers = {"Authorization": f"Bearer {info.operator_token}"}
        _http_text("GET", f"{info.service_url}/")
        _http_json("GET", f"{info.service_url}/manifest.webmanifest", headers={})
        runtime = _http_json("GET", f"{info.service_url}/api/runtime", headers=headers)
        quote = _http_json(
            "POST",
            f"{info.service_url}/api/ui/turn",
            headers=headers,
            payload={
                "request_id": "dev-quote-1",
                "message": "Quote Acme for 2 hours and travel",
                "defaults": dev_turn_defaults(),
            },
        )
        active_quote = quote.get("conversation_state", {}).get("active_quote", {})
        invoice = _http_json(
            "POST",
            f"{info.service_url}/api/ui/turn",
            headers=headers,
            payload={
                "request_id": "dev-invoice-1",
                "message": f"Invoice from quote {active_quote.get('quotation', '')}",
                "defaults": dev_turn_defaults(),
                "conversation_context": {"active_quote": active_quote},
            },
        )
        supplier = _http_json(
            "POST",
            f"{info.service_url}/api/ui/turn",
            headers=headers,
            payload={
                "request_id": "dev-supplier-1",
                "message": "Process this supplier invoice",
                "defaults": dev_turn_defaults(),
                "attachments": [
                    {
                        "kind": "supplier_invoice",
                        "document_path": str(
                            info.fixture_paths.sample_supplier_invoice_pdf
                        ),
                        "attach_source_file": True,
                    }
                ],
            },
        )
        current_artifact_url = quote.get("current_artifact", {}).get("url")
        if current_artifact_url:
            _http_bytes(
                "GET",
                f"{info.service_url}{current_artifact_url}",
                headers=headers,
            )
        requests_index = _http_json(
            "GET",
            f"{info.service_url}/api/requests",
            headers=headers,
        )
        return {
            "service_url": info.service_url,
            "fixture_paths": info.as_dict()["fixture_paths"],
            "runtime": runtime,
            "quote_status": quote.get("status"),
            "quote_stage": quote.get("stage"),
            "quote_ref": quote.get("erp_refs", []),
            "invoice_status": invoice.get("status"),
            "invoice_stage": invoice.get("stage"),
            "invoice_ref": invoice.get("erp_refs", []),
            "supplier_status": supplier.get("status"),
            "supplier_stage": supplier.get("stage"),
            "supplier_ref": supplier.get("erp_refs", []),
            "request_count": len(requests_index.get("requests", [])),
        }


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(host: str, port: int, *, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for {host}:{port}")


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_headers = {"Accept": "application/json", **headers}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, headers=request_headers, method=method)
    with request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_bytes(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
) -> bytes:
    req = request.Request(url, headers=headers, method=method)
    with request.urlopen(req, timeout=15) as response:
        return response.read()


def _http_text(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> str:
    req = request.Request(url, headers=headers or {}, method=method)
    with request.urlopen(req, timeout=15) as response:
        return response.read().decode("utf-8")
