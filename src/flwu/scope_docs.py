"""Scope document generation for Florida Litigator Weekly Update.

Generates substantive scope documents from the scope blueprint.
Each known scope gets a documented intent, specification, test plan,
and list of associated source IDs.

Uses registry.py for scope definitions. Never generates judge directories
before roster verification (C31).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flwu.registry import scope_blueprint, load_sources, validate_sources


def generate_all_scope_docs(output_root: Path) -> list[Path]:
    """Generate scope documents for all known scopes.

    Writes documents to output_root/<scope_id>/.
    Returns all written file paths.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    all_paths = []

    for scope in scope_blueprint():
        scope_out = output_root / scope.get("scope_id", "unknown")
        paths = write_scope_docs(scope, output_root=scope_out)
        all_paths.extend(paths)

    return all_paths


def generate_scope_doc_for(scope_id: str, output_root: Path) -> list[Path]:
    """Generate scope documents for a single scope."""
    all_scopes = scope_blueprint()
    for scope in all_scopes:
        if scope.get("scope_id") == scope_id:
            return write_scope_docs(scope, output_root=output_root)
    raise ValueError(f"Unknown scope_id: {scope_id}")
