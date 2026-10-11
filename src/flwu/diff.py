"""Semantic diff for Florida Litigator Weekly Update."""
from __future__ import annotations
from typing import Any

def compare_snapshots(
    previous, incoming, *, first_run=False, inventory_complete=False
):
    result = dict(baseline=first_run, added=[], amended=[], withdrawn=[],
                  superseded=[], unchanged=[], missing_for_review=[])
    prev_by_id = {}
    for r in previous:
        did = r.get("document_id")
        if did: prev_by_id[did] = r
    seen = set()
    iby = {}
    for r in incoming:
        did = r.get("document_id")
        if did: iby.setdefault(did, []).append(r)
    for did, records in iby.items():
        if len(records) > 1:
            revs = set(r.get("revision_id") for r in records)
            if len(revs) > 1:
                raise ValueError(f"Duplicate document_id {did} conflicting revisions")
    for r in incoming:
        did = r.get("document_id")
        if not did: continue
        seen.add(did)
        if did not in prev_by_id:
            result["added"].append(did); continue
        p = prev_by_id[did]
        pr = p.get("revision_id"); ir = r.get("revision_id")
        ps = p.get("legal_status", "unknown"); iss = r.get("legal_status", "unknown")
        if pr != ir:
            if iss in ("withdrawn", "superseded"):
                result["superseded"].append(did) if ps != iss else result["withdrawn"].append(did)
            else: result["amended"].append(did)
        else:
            if ps != iss:
                if iss in ("withdrawn", "superseded"):
                    result["superseded"].append(did) if ps != iss else result["withdrawn"].append(did)
                else: result["amended"].append(did)
            else: result["unchanged"].append(did)
    if inventory_complete:
        for did in prev_by_id:
            if did not in seen: result["missing_for_review"].append(did)
    for k in ("added","amended","withdrawn","superseded","unchanged","missing_for_review"):
        result[k] = sorted(result[k])
    return result
