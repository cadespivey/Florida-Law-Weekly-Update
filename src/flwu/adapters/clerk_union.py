"""Union County Clerk adapter (C30)."""
from __future__ import annotations
from typing import Any
from flwu.adapters import SourceAdapter, register_adapter
class ClerkUnionAdapter(SourceAdapter):
    def acquire(self, source: dict, page_limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError("Union County Clerk adapter requires live network access.")
register_adapter("clerk_union", ClerkUnionAdapter)
