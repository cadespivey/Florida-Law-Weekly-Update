"""Search index (C35)."""
from __future__ import annotations
import json
from typing import Any
from pathlib import Path

def write_search_index(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": 1, "rows": rows}
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_search_index(path):
    return json.loads(path.read_text(encoding="utf-8"))
