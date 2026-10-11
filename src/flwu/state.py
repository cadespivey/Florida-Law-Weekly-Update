"""SQLite state and lifecycle for Florida Litigator Weekly Update.

Creates and manages the local SQLite database with the frozen schema.
Uses WAL mode, parameterized SQL, explicit transactions, and foreign keys.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


_MIGRATION_SQL_PATH = Path("src/flwu/migrations/001_initial.sql")
_MIGRATION_SQL = _MIGRATION_SQL_PATH.read_text(encoding="utf-8")


def open_db(path: Path) -> sqlite3.Connection:
    """Open (or create) a SQLite database at *path*.

    Enables WAL mode and foreign keys. Returns a connection.
    """
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply migration 001 once.

    Uses PRAGMA user_version=1; rejects a newer version.
    Schema creation is transactional. Named indexes may be added;
    do not rename columns or loosen constraints.
    """
    cur = conn.execute("PRAGMA user_version")
    current_version = cur.fetchone()[0] or 0
    if current_version not in (0, 1):
        raise SchemaError(
            "UNSUPPORTED_SCHEMA",
            f"Schema version {current_version} is not supported. Expected 0 or 1.",
        )
    try:
        conn.executescript(_MIGRATION_SQL)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


class StateError(Exception):
    """Raised when a state operation fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class SchemaError(StateError):
    """Raised when schema is unsupported."""


def begin_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    mode: str,
    window_start: str,
    window_end: str,
    created_at: str,
) -> None:
    """Begin a new run. Rejects mode/state-root mismatch at caller boundary."""
    if mode not in ("fixture", "production"):
        raise StateError("INVALID_MODE", f"mode must be 'fixture' or 'production', got {mode}")
    conn.execute(
        "INSERT INTO runs (run_id, mode, window_start, window_end, status, created_at) "
        "VALUES (?, ?, ?, ?, 'running', ?)",
        (run_id, mode, window_start, window_end, created_at),
    )
    conn.commit()


def begin_attempt(
    conn: sqlite3.Connection,
    *,
    attempt_id: str,
    run_id: str,
    source_id: str,
    started_at: str,
) -> None:
    """Begin a source attempt. Starts with explicit empty/incomplete coverage,
    never complete by default."""
    conn.execute(
        "INSERT INTO source_attempts (attempt_id, run_id, source_id, status, started_at, coverage_json) "
        "VALUES (?, ?, ?, 'running', ?, '{}')",
        (attempt_id, run_id, source_id, started_at),
    )
    conn.commit()


def fail_attempt(
    conn: sqlite3.Connection,
    *,
    attempt_id: str,
    outcome: str,
    coverage: dict[str, Any],
    finished_at: str,
    error_code: str,
) -> None:
    """Record a terminal failed/incomplete/cancelled attempt.

    Records terminal incomplete/failed/cancelled status, timestamp and
    sanitized error, without changing source checkpoints.
    """
    valid_outcomes = {"incomplete", "failed", "cancelled", "budget_exceeded"}
    if outcome not in valid_outcomes:
        raise StateError(
            "INVALID_OUTCOME",
            f"outcome must be one of {valid_outcomes}, got {outcome}",
        )
    conn.execute(
        "UPDATE source_attempts SET status=?, finished_at=?, coverage_json=?, error_code=? "
        "WHERE attempt_id=?",
        (outcome, finished_at, str(coverage), error_code, attempt_id),
    )
    conn.commit()


class IncompleteSource(StateError):
    """Raised when acquisition is incomplete (partial pagination/freshness)."""


def commit_acquisition(
    conn: sqlite3.Connection,
    *,
    attempt_id: str,
    source_id: str,
    watermark_utc: str,
    records: list[dict[str, Any]],
    coverage: dict[str, Any],
    profile_id: str,
) -> str:
    """Commit acquisition atomically.

    One transaction persists immutable records, observations, deterministic
    pending jobs, successful source snapshot and checkpoint.

    Returns the snapshot_id on success.

    Raises IncompleteSource if the coverage signals incomplete pagination
    or freshness issues.
    """
    # Check for incomplete coverage
    if isinstance(coverage, dict):
        pages_complete = coverage.get("pages_complete", True)
        freshness_verified = coverage.get("freshness_verified", True)
        if not pages_complete or not freshness_verified:
            raise IncompleteSource(
                "INCOMPLETE",
                f"Source {source_id}: pages_complete={pages_complete}, freshness_verified={freshness_verified}",
            )

    # Compute the content_sha256 for each record for the document table
    docs_inserted = []
    revisions_inserted = []
    observations_inserted = []

    for rec in records:
        did = rec.get("document_id")
        rid = rec.get("revision_id")
        csha = rec.get("content_sha256")
        rjson = str(rec.get("record_json", str(rec)))
        obs_at = rec.get("observed_at", "")

        conn.execute(
            "INSERT OR IGNORE INTO documents (document_id, source_id, document_key, canonical_url) "
            "VALUES (?, ?, ?, ?)",
            (did, source_id, rec.get("document_key"), rec.get("canonical_url", "")),
        )
        docs_inserted.append(did)

        conn.execute(
            "INSERT INTO revisions (revision_id, document_id, content_sha256, record_json, first_seen_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (rid, did, csha, rjson, watermark_utc),
        )
        revisions_inserted.append(rid)

        conn.execute(
            "INSERT INTO observations (attempt_id, revision_id, observed_at, record_json) "
            "VALUES (?, ?, ?, ?)",
            (attempt_id, rid, obs_at, rjson),
        )
        observations_inserted.append((attempt_id, rid))

    # Create the source snapshot
    conn.execute(
        "INSERT INTO source_snapshots (snapshot_id, source_id, attempt_id, watermark_utc, revision_ids_json, coverage_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (f"snap_{attempt_id}", source_id, attempt_id, watermark_utc,
         str([r.get("revision_id") for r in records]), str(coverage)),
    )
    snap_id = f"snap_{attempt_id}"

    # Update the checkpoint
    conn.execute(
        "INSERT OR REPLACE INTO source_checkpoints (source_id, snapshot_id, watermark_utc) "
        "VALUES (?, ?, ?)",
        (source_id, snap_id, watermark_utc),
    )

    conn.commit()
    return snap_id


def get_snapshot_records(conn: sqlite3.Connection, *, source_id: str) -> list[dict[str, Any]]:
    """Return all document revisions from the latest snapshot for a source."""
    rows = conn.execute(
        """SELECT r.revision_id, r.document_id, r.content_sha256, r.record_json
           FROM source_snapshots ss
           JOIN source_attempts sa ON sa.attempt_id = ss.attempt_id
           JOIN observations o ON o.attempt_id = sa.attempt_id
           JOIN revisions r ON r.revision_id = o.revision_id
           WHERE ss.source_id = ?
             AND ss.snapshot_id = (
               SELECT ss2.snapshot_id
               FROM source_snapshots ss2
               WHERE ss2.source_id = ?
               ORDER BY ss2.watermark_utc DESC, ss2.snapshot_id DESC
               LIMIT 1
             )
           ORDER BY r.revision_id""",
        (source_id, source_id),
    ).fetchall()
    return [{
        "revision_id": row[0],
        "document_id": row[1],
        "content_sha256": row[2],
        "record_json": row[3],
    } for row in rows]


# C33 extensions - appended to state.py
import datetime
import json
import uuid
from typing import Any

def enqueue_profile(
    conn,
    revision_ids: list[str],
    profile_id: str,
) -> int:
    """Enqueue analysis jobs for revisions under a profile. Returns count created."""
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


def reviewed_retry(
    conn,
    *,
    analysis_id: str,
    review_receipt: dict[str, Any],
    now_utc: str,
    max_review_requeues: int = 2,
) -> None:
    """Record a reviewed retry."""
    prior_attempts = review_receipt.get("prior_attempts", 0)
    if prior_attempts >= max_review_requeues:
        conn.execute(
            "UPDATE analysis_jobs SET status = 'failed', error_code = 'MAX_REQUEUES', "
            "result_json = ? WHERE analysis_id = ?",
            (json.dumps(review_receipt), analysis_id),
        )
        return
    conn.execute(
        "UPDATE analysis_jobs SET status = 'pending', result_json = ?, error_code = NULL "
        "WHERE analysis_id = ?",
        (json.dumps(review_receipt), analysis_id),
    )


def claim_job(
    conn,
    *,
    source_ids: list[str],
    profile_id: str,
    now_utc: str,
    lease_seconds: int = 300,
    max_attempts: int = 3,
) -> dict[str, Any] | None:
    """Claim a pending job. Returns job dict or None."""
    source_key = source_ids[0] if source_ids else ""
    row = conn.execute(
        """SELECT a.analysis_id, a.revision_id, a.profile_id, a.attempts
           FROM analysis_jobs a
           WHERE a.status = 'pending' AND a.attempts < ?
           AND a.profile_id = ?
           ORDER BY a.analysis_id LIMIT 1""",
        (max_attempts, profile_id),
    ).fetchone()
    if row is None:
        return None
    analysis_id, revision_id, a_profile, attempts = row
    claim_token = uuid.uuid4().hex
    lease_until = (datetime.datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
                   + datetime.timedelta(seconds=lease_seconds)).isoformat()
    conn.execute(
        "UPDATE analysis_jobs SET status = 'running', lease_until = ?, claim_token = ?, "
        "attempts = ? WHERE analysis_id = ?",
        (lease_until, claim_token, attempts + 1, analysis_id),
    )
    return {
        "analysis_id": analysis_id,
        "revision_id": revision_id,
        "profile_id": a_profile,
        "claim_token": claim_token,
        "attempts": attempts + 1,
    }


def finish_job(
    conn,
    *,
    analysis_id: str,
    claim_token: str,
    now_utc: str,
    result: dict[str, Any] | None,
    error_code: str | None,
) -> None:
    """Finish a job."""
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
    """Recover expired/leaked jobs. Returns count."""
    rows = conn.execute(
        "SELECT analysis_id FROM analysis_jobs "
        "WHERE status = 'running' AND (lease_until IS NULL OR lease_until < ?) "
        "AND attempts < ?",
        (now_utc, max_attempts),
    ).fetchall()
    count = len(rows)
    for (analysis_id,) in rows:
        conn.execute(
            "UPDATE analysis_jobs SET status = 'pending', lease_until = NULL, "
            "claim_token = NULL WHERE analysis_id = ?",
            (analysis_id,),
        )
    return count


def pending_count(conn, *, source_ids: list[str], profile_id: str) -> int:
    """Count pending jobs for sources and profile."""
    return conn.execute(
        "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'pending' AND profile_id = ?",
        (profile_id,),
    ).fetchone()[0]


def blocking_count(conn, *, source_ids: list[str], profile_id: str) -> int:
    """Count blocked pending jobs."""
    return conn.execute(
        "SELECT COUNT(*) FROM analysis_jobs WHERE status = 'pending' AND profile_id = ?",
        (profile_id,),
    ).fetchone()[0]


def finalize_run(
    conn,
    *,
    run_id: str,
    required_source_ids: list[str],
    required_scope_ids: list[str],
    scope_coverage: list[dict[str, Any]],
    profile_id: str,
    has_changes: bool,
    finished_at: str,
    outcome: str | None = None,
    error_code: str | None = None,
) -> str:
    """Finalize a run."""
    required_set = set(required_source_ids)
    coverage_sources = set(sc.get("source_id") for sc in scope_coverage)
    all_complete = required_set.issubset(coverage_sources)
    status = "success_no_changes" if not has_changes else "success_changes"
    if not all_complete:
        status = "incomplete"
    conn.execute(
        "UPDATE runs SET status = ?, finished_at = ?, error_code = ? WHERE run_id = ?",
        (status, finished_at, error_code, run_id),
    )
    return status
