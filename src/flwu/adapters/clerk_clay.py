"""Clay County Clerk adapter (C27)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class ClerkClayAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 30) -> list[dict[str, Any]]:
        raise NotImplementedError("Clay County Clerk adapter requires live network access.")
register_adapter("clerk_clay", ClerkClayAdapter)
