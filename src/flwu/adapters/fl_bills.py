"""FL Bills adapter (C12)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class FLBillsAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 50) -> list[dict[str, Any]]:
        raise NotImplementedError("FL Bills adapter requires live network access.")
register_adapter("fl_bills", FLBillsAdapter)
