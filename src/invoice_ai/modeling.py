from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict


class InvoiceAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json_text(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)
