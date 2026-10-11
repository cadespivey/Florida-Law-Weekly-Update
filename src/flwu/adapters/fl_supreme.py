"""FL Supreme Court adapter (C13)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class FLSupremeAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError("FL Supreme Court adapter requires live network access.")
register_adapter("fl_supreme", FLSupremeAdapter)
