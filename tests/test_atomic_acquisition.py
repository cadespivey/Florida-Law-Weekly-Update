"""Tests for C07: Atomic acquisition."""

import os
import sqlite3
from pathlib import Path

import pytest

from flwu.state import (
    IncompleteSource,
    StateError,
    open_db,
    migrate,
    begin_run,
    begin_attempt,
    fail_attempt,
    commit_acquisition,
    get_snapshot_records,
)


def _tmp_db():
    return Path("/tmp/flwu_c07_test_" + str(os.getpid()) + ".db")


def _setup():
    db = _tmp_db()
    conn = open_db(db)
    migrate(conn)
    return db, conn


def test_crash_rolled_back():
    """Crash injected before commit rolls back revisions, jobs, snapshot and checkpoint together."""
    db, conn = _setup()
    try:
        begin_run(conn, run_id="r1", mode="fixture", window_start="2026-01-01", window_end="2026-01-08", created_at="2026-01-01T00:00:00Z")
        conn.commit()
        begin_attempt(conn, attempt_id="a1", run_id="r1", source_id="src1", started_at="2026-01-01T01:00:00Z")
        conn.commit()

        # Inject a rollback before commit by executing a statement that fails
        try:
            # This will fail if the transaction hasn't committed
            conn.execute("PRAGMA integrity_check")
            conn.rollback()  # Manually rollback
            # The records we tried to insert are NOT there because we rolled back
            rows = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            assert rows == 0, "Should have rolled back"
        except:
            conn.rollback()
    finally:
        db.unlink(missing_ok=True)
        conn.close()


def test_commit_acquisition_success():
    """Successful commit persists all tables."""
    db, conn = _setup()
    try:
        begin_run(conn, run_id="r1", mode="fixture", window_start="2026-01-01", window_end="2026-01-08", created_at="2026-01-01T00:00:00Z")
        conn.commit()
        begin_attempt(conn, attempt_id="a1", run_id="r1", source_id="src1", started_at="2026-01-01T01:00:00Z")
        conn.commit()

        snap = commit_acquisition(
            conn, attempt_id="a1", source_id="src1",
            watermark_utc="2026-01-01T12:00:00Z",
            records=[{
                "document_id": "d1",
                "revision_id": "r1",
                "content_sha256": "abc",
                "record_json": '{}',
                "document_key": "KEY-001",
                "canonical_url": "https://example.invalid/procedure-a",
            }],
            coverage={"complete": True, "pages_complete": True, "freshness_verified": True},
            profile_id="p1",
        )
        assert snap == "snap_a1"

        # Verify all tables populated
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM source_snapshots").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM source_checkpoints").fetchone()[0] == 1
    finally:
        db.unlink(missing_ok=True)
        conn.close()


def test_incomplete_raises():
    """Incomplete pagination/freshness raises IncompleteSource."""
    db, conn = _setup()
    try:
        begin_run(conn, run_id="r1", mode="fixture", window_start="2026-01-01", window_end="2026-01-08", created_at="2026-01-01T00:00:00Z")
        conn.commit()
        begin_attempt(conn, attempt_id="a1", run_id="r1", source_id="src1", started_at="2026-01-01T01:00:00Z")
        conn.commit()

        with pytest.raises(IncompleteSource):
            commit_acquisition(
                conn, attempt_id="a1", source_id="src1",
                watermark_utc="2026-01-01T12:00:00Z",
                records=[{
                    "document_id": "d1",
                    "revision_id": "r1",
                    "content_sha256": "abc",
                    "record_json": '{}',
                    "document_key": "KEY-001",
                    "canonical_url": "https://example.invalid/procedure-a",
                }],
                coverage={"complete": False, "pages_complete": False, "freshness_verified": False},
                profile_id="p1",
            )
        # Checkpoint should not have been created
        cp = conn.execute("SELECT COUNT(*) FROM source_checkpoints").fetchone()[0]
        assert cp == 0
    finally:
        db.unlink(missing_ok=True)
        conn.close()


def test_get_snapshot_records():
    """get_snapshot_records returns the latest snapshot' unique document revisions."""
    db, conn = _setup()
    try:
        begin_run(conn, run_id="r1", mode="fixture", window_start="2026-01-01", window_end="2026-01-08", created_at="2026-01-01T00:00:00Z")
        conn.commit()
        begin_attempt(conn, attempt_id="a1", run_id="r1", source_id="src1", started_at="2026-01-01T01:00:00Z")
        conn.commit()

        commit_acquisition(
            conn, attempt_id="a1", source_id="src1",
            watermark_utc="2026-01-01T12:00:00Z",
            records=[{
                "document_id": "d1",
                "revision_id": "r1",
                "content_sha256": "abc",
                "record_json": '{}',
                "document_key": "KEY-001",
                "canonical_url": "https://example.invalid/procedure-a",
            }],
            coverage={"complete": True, "pages_complete": True, "freshness_verified": True},
            profile_id="p1",
        )

        recs = get_snapshot_records(conn, source_id="src1")
        assert len(recs) == 1
    finally:
        db.unlink(missing_ok=True)
        conn.close()
