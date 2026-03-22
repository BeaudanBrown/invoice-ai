from __future__ import annotations

from dataclasses import dataclass
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib import error, parse, request
import uuid

from ..config import RuntimeConfig


class ERPNextClientError(RuntimeError):
    """Raised when the ERPNext API rejects a request."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


@dataclass(frozen=True)
class ERPNextCredentials:
    api_key: str
    api_secret: str

    @classmethod
    def from_file(cls, path: Path) -> "ERPNextCredentials":
        raw = path.read_text(encoding="utf-8").strip()
        if raw.startswith("{"):
            payload = json.loads(raw)
            return cls(
                api_key=str(payload["api_key"]),
                api_secret=str(payload["api_secret"]),
            )

        values: dict[str, str] = {}
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")

        api_key = (
            values.get("ERPNEXT_API_KEY")
            or values.get("API_KEY")
            or values.get("api_key")
        )
        api_secret = (
            values.get("ERPNEXT_API_SECRET")
            or values.get("API_SECRET")
            or values.get("api_secret")
        )
        if not api_key or not api_secret:
            raise ValueError(f"Unsupported ERPNext credential file format: {path}")
        return cls(api_key=api_key, api_secret=api_secret)

    def as_header(self) -> str:
        return f"token {self.api_key}:{self.api_secret}"


class ERPNextClient:
    def __init__(
        self,
        base_url: str,
        *,
        credentials: ERPNextCredentials | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "ERPNextClient":
        if config.dependencies.erpnext_url is None:
            raise ValueError("INVOICE_AI_ERPNEXT_URL must be configured")

        credentials = None
        if config.dependencies.erpnext_credentials_file is not None:
            credentials = ERPNextCredentials.from_file(
                config.dependencies.erpnext_credentials_file
            )

        return cls(config.dependencies.erpnext_url, credentials=credentials)

    def get_doc(self, doctype: str, name: str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/api/resource/{parse.quote(doctype)}/{parse.quote(name)}",
        )["data"]

    def list_docs(
        self,
        doctype: str,
        *,
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query: dict[str, str] = {"limit_page_length": str(limit)}
        if filters:
            query["filters"] = json.dumps(filters, sort_keys=True)
        if fields:
            query["fields"] = json.dumps(fields)
        if order_by:
            query["order_by"] = order_by
        payload = self._request_json(
            "GET",
            f"/api/resource/{parse.quote(doctype)}",
            query=query,
        )
        return payload.get("data", [])

    def create_doc(self, doctype: str, doc: dict[str, Any]) -> dict[str, Any]:
        payload = {"doctype": doctype}
        payload.update(doc)
        return self._request_json(
            "POST",
            f"/api/resource/{parse.quote(doctype)}",
            payload=payload,
        )["data"]

    def update_doc(
        self, doctype: str, name: str, doc: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request_json(
            "PUT",
            f"/api/resource/{parse.quote(doctype)}/{parse.quote(name)}",
            payload=doc,
        )["data"]

    def attach_file(
        self,
        *,
        target_doctype: str,
        target_name: str,
        source_path: Path,
        file_name: str,
        is_private: bool,
    ) -> dict[str, Any]:
        boundary = f"invoice-ai-{uuid.uuid4().hex}"
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        file_bytes = source_path.read_bytes()
        body = self._multipart_body(
            boundary,
            fields={
                "doctype": target_doctype,
                "docname": target_name,
                "is_private": "1" if is_private else "0",
            },
            file_field="file",
            file_name=file_name,
            file_content_type=mime_type,
            file_bytes=file_bytes,
        )
        return self._request_json(
            "POST",
            "/api/method/upload_file",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )["message"]

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"

        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        if self.credentials is not None:
            request_headers["Authorization"] = self.credentials.as_header()

        request_body = body
        if payload is not None:
            request_body = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        req = request.Request(
            url,
            data=request_body,
            headers=request_headers,
            method=method,
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload_bytes = response.read()
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            parsed = self._parse_error_body(response_body)
            message = parsed.get("message") or parsed.get("exc") or str(exc)
            raise ERPNextClientError(
                message,
                status_code=exc.code,
                body=parsed,
            ) from exc
        except error.URLError as exc:
            raise ERPNextClientError(str(exc.reason)) from exc

        if not payload_bytes:
            return {}
        return json.loads(payload_bytes.decode("utf-8"))

    @staticmethod
    def _parse_error_body(payload: str) -> dict[str, Any]:
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"message": payload}

    @staticmethod
    def _multipart_body(
        boundary: str,
        *,
        fields: dict[str, str],
        file_field: str,
        file_name: str,
        file_content_type: str,
        file_bytes: bytes,
    ) -> bytes:
        lines: list[bytes] = []
        for key, value in fields.items():
            lines.extend(
                [
                    f"--{boundary}".encode("utf-8"),
                    (
                        f'Content-Disposition: form-data; name="{key}"'
                    ).encode("utf-8"),
                    b"",
                    value.encode("utf-8"),
                ]
            )
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{file_field}"; '
                    f'filename="{file_name}"'
                ).encode("utf-8"),
                f"Content-Type: {file_content_type}".encode("utf-8"),
                b"",
                file_bytes,
                f"--{boundary}--".encode("utf-8"),
                b"",
            ]
        )
        return b"\r\n".join(lines)
