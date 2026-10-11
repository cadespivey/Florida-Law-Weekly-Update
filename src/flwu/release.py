"""Release gates (C37).

Manages release lifecycle: staging, validation, and gating.
Both manual and automated release modes are supported.
"""
from __future__ import annotations
from typing import Any
from pathlib import Path

class ReleaseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

class ReleaseGate:
    """Release gate for manual or automated approval."""
    def __init__(self, mode="manual"):
        self.mode = mode  # "manual" or "automated"
        self.approved = False
        self.staging_path = None

    def stage(self, data_path):
        self.staging_path = data_path
        return True

    def validate(self, required_fields):
        if not self.staging_path:
            raise ReleaseError("NO_STAGING", "No staging path set")
        return True

    def approve(self):
        if self.mode == "automated":
            self.approved = True
            return True
        if self.mode == "manual":
            raise ReleaseError("APPROVAL_REQUIRED", "Manual approval required")
        return False

def create_release_manifest(issue, inventory_id, data_dir):
    manifest = {
        "schema_version": 1,
        "release_id": f"rel_{issue.get('issue_id','unknown')}",
        "data_cutoff": issue.get("cutoff_utc"),
        "issue_id": issue.get("issue_id"),
        "version": issue.get("version", 1),
        "coverage_status": issue.get("coverage_status", "incomplete"),
        "inventory_snapshot_id": inventory_id,
    }
    return manifest

def validate_release(manifest, data_dir):
    required = ["schema_version", "release_id", "data_cutoff", "issue_id",
                "coverage_status", "inventory_snapshot_id"]
    missing = [k for k in required if k not in manifest]
    if missing:
        raise ReleaseError("MISSING_FIELDS", f"Missing: {missing}")
    return True

def publish_release(manifest, data_dir, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "data" / "release.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path
