"""Court and Bar Rules adapter (C20)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class CourtBarRulesAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError("Court/Bar Rules adapter requires live network access.")
register_adapter("court_bar_rules", CourtBarRulesAdapter)
