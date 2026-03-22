from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


def _env_path(name: str, default: str) -> Path:
    value = os.environ.get(name, default).strip()
    return Path(value)


@dataclass(frozen=True)
class RuntimePaths:
    state_dir: Path
    documents_dir: Path
    memory_dir: Path
    ingest_dir: Path
    approvals_dir: Path
    revisions_dir: Path
    artifacts_dir: Path
    cache_dir: Path

    @classmethod
    def from_env(cls) -> "RuntimePaths":
        state_dir = _env_path("INVOICE_AI_STATE_DIR", "/var/lib/invoice-ai")
        return cls(
            state_dir=state_dir,
            documents_dir=_env_path(
                "INVOICE_AI_DOCUMENTS_DIR", str(state_dir / "documents")
            ),
            memory_dir=_env_path("INVOICE_AI_MEMORY_DIR", str(state_dir / "memory")),
            ingest_dir=_env_path("INVOICE_AI_INGEST_DIR", str(state_dir / "ingest")),
            approvals_dir=_env_path(
                "INVOICE_AI_APPROVALS_DIR", str(state_dir / "approvals")
            ),
            revisions_dir=_env_path(
                "INVOICE_AI_REVISIONS_DIR", str(state_dir / "revisions")
            ),
            artifacts_dir=_env_path(
                "INVOICE_AI_ARTIFACTS_DIR", str(state_dir / "artifacts")
            ),
            cache_dir=_env_path("INVOICE_AI_CACHE_DIR", str(state_dir / "cache")),
        )

    def required_directories(self) -> tuple[Path, ...]:
        return (
            self.state_dir,
            self.documents_dir,
            self.memory_dir,
            self.ingest_dir,
            self.approvals_dir,
            self.revisions_dir,
            self.artifacts_dir,
            self.cache_dir,
        )

    def ensure(self) -> None:
        for path in self.required_directories():
            path.mkdir(parents=True, exist_ok=True)

    def as_json(self) -> dict[str, Any]:
        return {
            "state_dir": str(self.state_dir),
            "documents_dir": str(self.documents_dir),
            "memory_dir": str(self.memory_dir),
            "ingest_dir": str(self.ingest_dir),
            "approvals_dir": str(self.approvals_dir),
            "revisions_dir": str(self.revisions_dir),
            "artifacts_dir": str(self.artifacts_dir),
            "cache_dir": str(self.cache_dir),
        }
