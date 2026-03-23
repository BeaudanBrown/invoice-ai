from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib import error, request


class DoclingClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class DoclingClient:
    base_url: str
    timeout_seconds: int = 30

    def extract_text(self, source_path: Path) -> dict[str, Any]:
        payload = json.dumps({"source_path": str(source_path)}).encode("utf-8")
        req = request.Request(
            f"{self.base_url.rstrip('/')}/extract",
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read()
        except error.HTTPError as exc:
            raise DoclingClientError(exc.read().decode("utf-8", errors="replace")) from exc
        except error.URLError as exc:
            raise DoclingClientError(str(exc.reason)) from exc

        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            raise DoclingClientError("Docling response must be a JSON object")
        return data
