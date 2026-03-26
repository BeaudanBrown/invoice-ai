from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from pydantic import Field

from ..modeling import InvoiceAIModel


class OperatorTokenRecord(InvoiceAIModel):
    operator_id: str
    token: str = Field(min_length=1)


class OperatorTokenFile(InvoiceAIModel):
    operators: tuple[OperatorTokenRecord, ...] = Field(default_factory=tuple)


@dataclass(frozen=True)
class OperatorIdentity:
    operator_id: str


class OperatorAuthenticator:
    def __init__(self, *, tokens_file: Path | None) -> None:
        self.tokens_file = tokens_file

    def is_configured(self) -> bool:
        return self.tokens_file is not None and self.tokens_file.exists()

    def authenticate_bearer_token(self, token: str | None) -> OperatorIdentity | None:
        if token is None or not token.strip():
            return None
        for record in self._token_file().operators:
            if record.token == token:
                return OperatorIdentity(operator_id=record.operator_id)
        return None

    def _token_file(self) -> OperatorTokenFile:
        if self.tokens_file is None:
            raise ValueError("INVOICE_AI_OPERATOR_TOKENS_FILE is not configured")
        path = self.tokens_file
        if not path.exists():
            raise ValueError(
                f"Configured operator token file does not exist: {path}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        return OperatorTokenFile.model_validate(payload)
