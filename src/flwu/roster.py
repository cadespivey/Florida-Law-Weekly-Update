"""Roster reconciliation (C31).

Maps judge names, aliases, and concurrent/future assignments
from verified roster records to canonical judge identifiers.
Preserves separate concurrent and future assignments.

Uses verified roster/assignment records as input only.
"""
from __future__ import annotations
from typing import Any

class RosterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

def reconcile_rosters(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconcile judge rosters from verified records.

    Args:
        records: Verified roster/assignment records.

    Returns:
        Dict mapping judge_id to assignment info including:
        - name: canonical judge name
        - aliases: list of known aliases
        - current_assignments: list of active assignments
        - future_assignments: list of future assignments (as_of determined)
    """
    judges: dict[str, dict[str, Any]] = {}
    for rec in records:
        kind = rec.get("kind", "")
        if kind not in ("roster", "assignment"):
            continue

        judge_names = rec.get("judge_names") or []
        judge_aliases = rec.get("judge_aliases") or []
        assignments = rec.get("assignments") or []

        for name in judge_names:
            # Find or create judge
            judge_id = None
            for jid, jdata in judges.items():
                if jdata.get("canonical_name") == name:
                    judge_id = jid
                    break

            if judge_id is None:
                judge_id = f"judge_{len(judges) + 1:03d}"
                judges[judge_id] = {
                    "canonical_name": name,
                    "aliases": list(set(judge_aliases)),
                    "current_assignments": [],
                    "future_assignments": [],
                }

            # Add assignments
            for assignment in assignments:
                as_of = assignment.get("as_of")
                is_future = assignment.get("is_future", False)
                entry = {
                    "circuit": assignment.get("circuit_id"),
                    "division": assignment.get("division"),
                    "court": assignment.get("court"),
                    "as_of": as_of,
                }
                if is_future:
                    judges[judge_id]["future_assignments"].append(entry)
                else:
                    judges[judge_id]["current_assignments"].append(entry)

    return {"judges": judges, "count": len(judges)}
