"""Procedure inventory (C35)."""
from __future__ import annotations
from typing import Any

def build_inventory(records, *, snapshot_id, as_of, aliases):
    rows = []
    for rec in records:
        kind = rec.get("kind", "")
        category = "Statutes" if kind in ("statute", "bill") else \
                   "Case Law" if kind == "case" else \
                   "Procedural Rules" if kind in ("court_rule", "agency_rule") else "Local Rules"
        row = {
            "record_id": rec.get("document_id", ""),
            "revision_id": rec.get("revision_id", ""),
            "title": rec.get("title", ""),
            "text": (rec.get("body_text") or "")[:500],
            "category": category,
            "county_ids": rec.get("scope_ids") or [],
            "circuit_ids": [s.split(":")[1] for s in (rec.get("scope_ids") or []) if "circuit" in s.lower()],
            "judge_ids": [],
            "judge_names": [],
            "judge_aliases": [],
            "court_levels": ["county" if s.startswith("county") else "state" for s in (rec.get("scope_ids") or [])],
            "divisions": [s.split(":")[1] if ":" in s else s for s in (rec.get("scope_ids") or [])],
            "topics": rec.get("facts", {}).get("subject_tags", []),
            "citation": rec.get("document_key", ""),
            "legal_status": rec.get("legal_status", "unknown"),
            "effective_date": rec.get("effective_date"),
            "source_url": rec.get("canonical_url", ""),
            "pinpoint": None,
            "snapshot_id": snapshot_id,
            "checked_at": as_of,
            "coverage_status": "complete" if rec.get("exact_sha256") else "partial",
        }
        rows.append(row)
    return rows

def select_snapshot(catalog, *, mode, snapshot_id=None):
    if mode == "current":
        latest = catalog.get("latest_snapshot_id")
        for s in catalog.get("snapshots", []):
            if s["snapshot_id"] == latest:
                return s
        raise ValueError("No latest snapshot")
    else:
        if snapshot_id is None:
            raise ValueError("Historical mode requires snapshot_id")
        for s in catalog.get("snapshots", []):
            if s["snapshot_id"] == snapshot_id:
                return s
        raise ValueError(f"Unknown snapshot_id: {snapshot_id}")

def search_inventory(rows, *, query="", county=None, circuit=None,
                     judge_id=None, topic=None, court_level=None, division=None,
                     mode="current", as_of=""):
    results = rows[:]
    ql = query.lower()
    if ql:
        results = [r for r in results if ql in r.get("title","").lower() or ql in r.get("text","").lower()]
    if county:
        results = [r for r in results if county in r.get("county_ids", [])]
    if circuit:
        results = [r for r in results if circuit in r.get("circuit_ids", [])]
    if topic:
        results = [r for r in results if topic in r.get("topics", [])]
    return sorted(results, key=lambda r: (r.get("title",""), r.get("record_id","")))[:20]
