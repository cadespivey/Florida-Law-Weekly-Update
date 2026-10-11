"""Analysis worker and durable jobs (C33).

Manages analysis job lifecycle, including queue, claim, finish,
and recovery. Extends state.py with worker-specific functions.
Handles profile requeuing, blocking counts, and run finalization.

No model calls in C33 - only queue management.
"""
from __future__ import annotations
import datetime
import json
import uuid
from pathlib import Path
from typing import Any
from flwu.state import open_db, migrate, StateError
from flwu.model import AnalysisProfile, load_analysis_config

class AnalysisError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

def enqueue_profile(conn, revision_ids: list[str], profile_id: str) -> int:
    """Enqueue analysis jobs for revisions under a profile.

    Returns the number of jobs created.
    """
    conn.execute(
        """INSERT OR IGNORE INTO analysis_jobs 
           (analysis_id, revision_id, profile_id, status, attempts)
           VALUES (?, ?, ?, 'pending', 0)
           ON CONFLICT(revision_id, profile_id) DO NOTHING""",
        [(f"ana_{uuid.uuid4().hex[:8]}", rid, profile_id) for rid in revision_ids],
    )
    return conn.execute(
        "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'pending'"
    ).fetchone()[0]

def claimed_retry(conn, *, analysis_id: str, review_receipt: dict, now_utc: str,
                   max_review_requeues: int = 2) -> None:
    """Record a reviewed retry, potentially requeuing the job."""
    prior_attempts = review_receipt.get("prior_attempts", 0)
    if prior_attempts >= max_review_requeues:
        conn.execute(
            "UPDATE analysis_jobs SET status = 'failed', error_code = 'MAX_REQUEUES', result_json = ? WHERE analysis_id = ?",
            (json.dumps(review_receipt), analysis_id),
        )
        return

    conn.execute(
        "UPDATE analysis_jobs SET status = 'pending', result_json = ?, error_code = NULL "
        "WHERE analysis_id = ?",
        (json.dumps(review_receipt), analysis_id),
    )

def claim_job(conn, *, source_ids: list[str], profile_id: str, now_utc: str,
              lease_seconds: int = 300, max_attempts: int = 3) -> dict[str, Any] | None:
    """Claim a pending job. Returns job or None if no jobs available."""
    row = conn.execute(
        """SELECT a.analysis_id, a.revision_id, a.profile_id, a.attempts
           FROM analysis_jobs a
           WHERE a.status = 'pending' AND a.attempts < ?
           AND EXISTS (SELECT 1 FROM revisions r 
                        JOIN source_snapshots ss ON ss.source_id = ?
                        WHERE r.revision_id = a.revision_id)
           AND a.profile_id = ?
           ORDER BY a.analysis_id LIMIT 1""",
        (max_attempts, source_ids[0] if source_ids else "", profile_id),
    ).fetchone()

    if row is None:
        return None

    analysis_id, revision_id, a_profile, attempts = row
    claim_token = uuid.uuid4().hex

    conn.execute(
        "UPDATE analysis_jobs SET status = 'running', lease_until = ?, claim_token = ?, attempts = ?"
        " WHERE analysis_id = ?",
        (datetime.datetime.fromisoformat(now_utc.replace("Z","+00:00")).isoformat() 
         + f"+{lease_seconds}s", claim_token, attempts + 1, analysis_id),
    )
    return {
        "analysis_id": analysis_id,
        "revision_id": revision_id,
        "profile_id": a_profile,
        "claim_token": claim_token,
        "attempts": attempts + 1,
    }

def finish_job(conn, *, analysis_id: str, claim_token: str, now_utc: str,
               result: dict[str, Any] | None, error_code: str | None) -> None:
    """Finish a job with result or error."""
    conn.execute(
        "UPDATE analysis_jobs SET status = ?, result_json = ?, error_code = ?, "
        "lease_until = NULL WHERE analysis_id = ? AND claim_token = ?",
        (
            "done" if error_code is None else "failed",
            json.dumps(result) if result else None,
            error_code,
            analysis_id,
            claim_token,
        ),
    )

def recover_expired_jobs(conn, *, now_utc: str, max_attempts: int = 3) -> int:
    """Recover expired/leaked jobs. Returns recovered count."""
    rows = conn.execute(
        """SELECT analysis_id FROM analysis_jobs 
           WHERE status = 'running' 
           AND (lease_until IS NULL OR lease_until < ?)
           AND attempts < ?""",
        (now_utc, max_attempts),
    ).fetchall()
    count = len(rows)
    for (analysis_id,) in rows:
        conn.execute(
            "UPDATE analysis_jobs SET status = 'pending', lease_until = NULL, claim_token = NULL"
            " WHERE analysis_id = ?", (analysis_id,),
        )
    return count

def pending_count(conn, *, source_ids: list[str], profile_id: str) -> int:
    """Count pending jobs for sources and profile."""
    return conn.execute(
        """SELECT COUNT(*) FROM analysis_jobs a
           WHERE a.status = 'pending' AND a.profile_id = ?
           AND EXISTS (SELECT 1 FROM revisions r 
                        JOIN source_snapshots ss ON ss.source_id = ?
                        WHERE r.revision_id = a.revision_id)""",
        (profile_id, source_ids[0] if source_ids else ""),
    ).fetchone()[0]

def blocking_count(conn, *, source_ids: list[str], profile_id: str) -> int:
    """Count pending jobs that block others."""
    return conn.execute(
        """SELECT COUNT(*) FROM analysis_jobs a
           WHERE a.status = 'pending' AND a.attempts >= ?
           AND a.profile_id = ?
           AND EXISTS (SELECT 1 FROM revisions r 
                        JOIN source_snapshots ss ON ss.source_id = ?
                        WHERE r.revision_id = a.revision_id)""",
        (3, profile_id, source_ids[0] if source_ids else ""),
    ).fetchone()[0]

def finalize_run(conn, *, run_id: str, required_source_ids: list[str],
                 required_scope_ids: list[str], scope_coverage: list[dict],
                 profile_id: str, has_changes: bool, finished_at: str,
                 outcome: str | None = None, error_code: str | None = None) -> str:
    """Finalize a run with full coverage verification."""
    required_set = set(required_source_ids)
    coverage_sources = set()
    for sc in scope_coverage:
        sid = sc.get("source_id")
        if sid:
            coverage_sources.add(sid)

    all_complete = required_set.issubset(coverage_sources)

    status = "success_no_changes" if has_changes is False else "success_changes"
    if not all_complete:
        status = "incomplete"

    conn.execute(
        "UPDATE runs SET status = ?, finished_at = ?, error_code = ? WHERE run_id = ?",
        (status, finished_at, error_code, run_id),
    )
    return status

def build_analysis_profiles() -> list[AnalysisProfile]:
    """Build analysis profiles from config."""
    return load_analysis_config()
