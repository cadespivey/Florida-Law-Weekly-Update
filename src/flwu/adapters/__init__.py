"""Adapter interface and registry for Florida Litigator Weekly Update.

Defines SourceAdapter protocol and adapter registry.
Adapters are lazily loaded on demand to avoid circular imports.
"""
from __future__ import annotations
from typing import Any, Protocol

from flwu.fetch import FetchError

class SourceAdapter(Protocol):
    """Protocol for source adapters."""
    def acquire(self, source: dict, page_limit: int = 50) -> list[dict[str, Any]]:
        ...

_REGISTRY: dict[str, type[SourceAdapter]] = {}

def register_adapter(adapter_id: str, adapter_class: type[SourceAdapter]) -> None:
    """Register a source adapter by its adapter_id."""
    _REGISTRY[adapter_id] = adapter_class

def get_adapter(adapter_id: str) -> SourceAdapter:
    """Get a registered adapter by ID.

    Lazy-loads the adapter module on first access if not yet registered.
    """
    if adapter_id not in _REGISTRY:
        # Lazy load the adapter module
        import importlib
        module_map = {
            "fl_statutes": "flwu.adapters.fl_statutes",
            "fl_bills": "flwu.adapters.fl_bills",
            "fl_supreme": "flwu.adapters.fl_supreme",
            "dca_first": "flwu.adapters.dca_first",
            "dca_second": "flwu.adapters.dca_second",
            "dca_third": "flwu.adapters.dca_third",
            "dca_fourth": "flwu.adapters.dca_fourth",
            "dca_fifth": "flwu.adapters.dca_fifth",
            "dca_sixth": "flwu.adapters.dca_sixth",
            "court_bar_rules": "flwu.adapters.court_bar_rules",
            "agency_rules": "flwu.adapters.agency_rules",
            "circuit_fourth": "flwu.adapters.circuit_fourth",
            "circuit_seventh": "flwu.adapters.circuit_seventh",
            "circuit_eighth": "flwu.adapters.circuit_eighth",
            "clerk_duval": "flwu.adapters.clerk_duval",
            "clerk_st_johns": "flwu.adapters.clerk_st_johns",
            "clerk_clay": "flwu.adapters.clerk_clay",
            "clerk_nassau": "flwu.adapters.clerk_nassau",
            "clerk_baker": "flwu.adapters.clerk_baker",
            "clerk_union": "flwu.adapters.clerk_union",
        }
        mod_name = module_map.get(adapter_id)
        if mod_name:
            importlib.import_module(mod_name)
        else:
            raise ValueError(f"Unregistered adapter_id: {adapter_id}")

    cls = _REGISTRY.get(adapter_id)
    if cls is None:
        raise ValueError(f"Unregistered adapter_id: {adapter_id}")
    return cls()

# Registry for direct access in tests
# Note: adapters register themselves on import, but circular imports prevent
# loading at module level. Use get_adapter() which lazy-loads.

__all__ = ["SourceAdapter", "register_adapter", "get_adapter", "_REGISTRY", "FetchError"]
