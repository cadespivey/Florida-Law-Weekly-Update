"""St. Johns County Clerk adapter (C26)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class ClerkStJohnsAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 30) -> list[dict[str, Any]]:
        raise NotImplementedError("St. Johns County Clerk adapter requires live network access.")
register_adapter("clerk_st_johns", ClerkStJohnsAdapter)
