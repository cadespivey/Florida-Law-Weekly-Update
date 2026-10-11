"""First DCA adapter (C14)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class FirstDCAAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError("First DCA adapter requires live network access.")
register_adapter("dca_first", FirstDCAAdapter)
