from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any

from .paths import RuntimePaths


def _read_env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _read_int(name: str, default: int) -> int:
    value = _read_env(name)
    if value is None:
        return default
    return int(value)


def _read_path(name: str, default: str | None = None) -> Path | None:
    value = _read_env(name, default)
    if value is None:
        return None
    return Path(value)


@dataclass(frozen=True)
class DependencyEndpoints:
    erpnext_url: str | None
    erpnext_credentials_file: Path | None
    ollama_url: str
    docling_url: str | None
    n8n_url: str | None

    def as_json(self) -> dict[str, Any]:
        return {
            "erpnext_url": self.erpnext_url,
            "erpnext_credentials_file": (
                str(self.erpnext_credentials_file)
                if self.erpnext_credentials_file is not None
                else None
            ),
            "ollama_url": self.ollama_url,
            "docling_url": self.docling_url,
            "n8n_url": self.n8n_url,
        }


@dataclass(frozen=True)
class ServiceConfig:
    listen_address: str
    port: int
    public_url: str | None
    host_name: str | None

    def base_url(self) -> str:
        if self.public_url is not None:
            return self.public_url
        return f"http://{self.listen_address}:{self.port}"


@dataclass(frozen=True)
class RuntimeConfig:
    service: ServiceConfig
    paths: RuntimePaths
    dependencies: DependencyEndpoints

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        paths = RuntimePaths.from_env()
        return cls(
            service=ServiceConfig(
                listen_address=_read_env("INVOICE_AI_LISTEN_ADDRESS", "127.0.0.1"),
                port=_read_int("INVOICE_AI_PORT", 4310),
                public_url=_read_env("INVOICE_AI_PUBLIC_URL"),
                host_name=_read_env("INVOICE_AI_HOST_NAME"),
            ),
            paths=paths,
            dependencies=DependencyEndpoints(
                erpnext_url=_read_env("INVOICE_AI_ERPNEXT_URL"),
                erpnext_credentials_file=_read_path(
                    "INVOICE_AI_ERPNEXT_CREDENTIALS_FILE"
                ),
                ollama_url=_read_env(
                    "INVOICE_AI_OLLAMA_URL", "http://127.0.0.1:11434"
                )
                or "http://127.0.0.1:11434",
                docling_url=_read_env("INVOICE_AI_DOCLING_URL"),
                n8n_url=_read_env("INVOICE_AI_N8N_URL"),
            ),
        )

    def as_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["paths"] = self.paths.as_json()
        payload["dependencies"] = self.dependencies.as_json()
        payload["service"]["base_url"] = self.service.base_url()
        return payload

    def to_json_text(self) -> str:
        return json.dumps(self.as_json(), indent=2, sort_keys=True)
