"""Nassau County Clerk adapter (C28)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class ClerkNassauAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError("Nassau County Clerk adapter requires live network access.")
register_adapter("clerk_nassau", ClerkNassauAdapter)
