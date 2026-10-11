"""Append-only research memory, isolated from the frozen operational SQLite v1.

Knowledge time is the first database capture, never a backdated publication date.
Source checks retain their actual retrieval time. Hash changes request review;
they do not establish a change in law.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def stamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("History timestamps require a timezone")
    return dt.astimezone(timezone.utc).isoformat()


def boundary(value, *, end=False):
    """Date inputs are inclusive New York dates; timestamp ends are exclusive."""
    if len(value) == 10:
        day = date.fromisoformat(value) + timedelta(days=int(end))
        return datetime.combine(day, time.min, ZoneInfo("America/New_York")).astimezone(timezone.utc).isoformat()
    return stamp(value)


def default_database():
    return Path(os.environ.get("FLWU_HISTORY_DB", "~/.local/share/flwu/research-history.sqlite")).expanduser()


SCHEMA = """
CREATE TABLE history_meta(version INTEGER NOT NULL);
INSERT INTO history_meta VALUES(1);
CREATE TABLE streams(stream TEXT PRIMARY KEY, mode TEXT NOT NULL, scope TEXT NOT NULL);
CREATE TABLE captures(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, capture_id TEXT UNIQUE NOT NULL,
    stream TEXT NOT NULL REFERENCES streams(stream), run_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX capture_stream ON captures(stream, seq);
CREATE TABLE artifacts(sha256 TEXT PRIMARY KEY, bytes BLOB NOT NULL);
CREATE TABLE finding_versions(version_id TEXT PRIMARY KEY, entity_key TEXT NOT NULL, kind TEXT NOT NULL, facts TEXT NOT NULL);
CREATE TABLE finding_observations(capture_seq INTEGER NOT NULL REFERENCES captures(seq),
    entity_key TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES finding_versions(version_id),
    citations TEXT NOT NULL, PRIMARY KEY(capture_seq,entity_key));
CREATE TABLE finalized_reports(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, stream TEXT NOT NULL REFERENCES streams(stream),
    capture_seq INTEGER NOT NULL REFERENCES captures(seq), report_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
    finalized_at TEXT NOT NULL, review TEXT NOT NULL, UNIQUE(stream, capture_seq, report_sha256));
"""


@contextmanager
def database(path=None):
    path = Path(path or default_database())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if names and "history_meta" not in names:
            raise ValueError("Not a research-history database; the legacy schema is frozen")
        if not names:
            conn.executescript(SCHEMA)
        if conn.execute("SELECT version FROM history_meta").fetchone()[0] != 1:
            raise ValueError("Unsupported research-history schema")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
    finally:
        conn.close()


def record(conn, *, stream, mode, scope, run_id, payload, artifacts, recorded_at=None):
    """Atomic immutable checkpoint. Repeat identical checkpoint is idempotent.

    payload: status, contract, checks[{id,status,checked_at,hashes}],
    findings[{key,kind,facts,citations}], drafts (unvalidated receipts).
    Only adapter-validated findings belong in findings; drafts never enter context.
    """
    if mode not in ("manual_research", "synthetic_replay"):
        raise ValueError("Unsupported history mode")
    if payload["status"] not in ("incomplete", "ready_for_review"):
        raise ValueError("Invalid history status")
    for collection, key in ((payload["checks"], "id"), (payload["findings"], "key")):
        if len({x[key] for x in collection}) != len(collection):
            raise ValueError("Duplicate history identity")
    for finding in payload["findings"]:
        if not finding.get("citations"):
            raise ValueError("History finding requires evidence")
    for check in payload["checks"]:
        if check["status"] not in ("verified", "incomplete"):
            raise ValueError("Invalid check status")
        if check["status"] == "verified":
            stamp(check["checked_at"])
    for key, data in artifacts.items():
        if sha(data) != key:
            raise ValueError("History artifact checksum mismatch")
    captured = stamp(recorded_at or now())
    identity = sha([stream, run_id, payload])
    with conn:
        conn.execute("INSERT OR IGNORE INTO streams VALUES(?,?,?)", (stream, mode, canonical(scope)))
        stored = conn.execute("SELECT mode,scope FROM streams WHERE stream=?", (stream,)).fetchone()
        if tuple(stored) != (mode, canonical(scope)):
            raise ValueError("Stream mode/scope conflict; use a separate stream")
        for key, data in artifacts.items():
            conn.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?)", (key, data))
        conn.execute("INSERT OR IGNORE INTO captures(capture_id,stream,run_id,recorded_at,payload) VALUES(?,?,?,?,?)",
                     (identity, stream, run_id, captured, canonical(payload)))
        seq = conn.execute("SELECT seq FROM captures WHERE capture_id=?", (identity,)).fetchone()[0]
        for item in payload["findings"]:
            version = sha([stream, item["key"], item["kind"], item["facts"]])
            conn.execute("INSERT OR IGNORE INTO finding_versions VALUES(?,?,?,?)",
                         (version, item["key"], item["kind"], canonical(item["facts"])))
            conn.execute("INSERT OR IGNORE INTO finding_observations VALUES(?,?,?,?)",
                         (seq, item["key"], version, canonical(item["citations"])))
    return dict(conn.execute("SELECT seq,capture_id,stream,recorded_at FROM captures WHERE capture_id=?", (identity,)).fetchone())


def finalize(conn, capture_id, report: Path, review):
    """Explicit local approval marker, not publication or an automated legal review."""
    if not review.strip():
        raise ValueError("Name reviewer and record legal/visual review in --review")
    row = conn.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown capture")
    payload = json.loads(row["payload"])
    if payload["status"] != "ready_for_review" or not payload["checks"] or any(c["status"] != "verified" for c in payload["checks"]):
        raise ValueError("Incomplete research cannot become the finalized baseline")
    latest = conn.execute("SELECT max(seq) FROM captures WHERE stream=?", (row["stream"],)).fetchone()[0]
    if latest != row["seq"]:
        raise ValueError("Finalize the latest captured state; older state cannot advance the baseline")
    data = report.read_bytes()
    if not data:
        raise ValueError("Empty report")
    with conn:
        conn.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?)", (sha(data), data))
        conn.execute("INSERT OR IGNORE INTO finalized_reports(stream,capture_seq,report_sha256,finalized_at,review) VALUES(?,?,?,?,?)",
                     (row["stream"], row["seq"], sha(data), now(), review))
    return {"stream": row["stream"], "capture_id": capture_id, "report_sha256": sha(data), "publication_performed": False}


def compare(conn, stream, *, start=None, end=None, entity=None):
    """All observed transitions, not just net difference; missing is never deletion."""
    upper = boundary(end, end=True) if end else now()
    lower = boundary(start) if start else None
    if lower and lower >= upper:
        raise ValueError("Start must precede end")
    rows = conn.execute("SELECT * FROM captures WHERE stream=? AND recorded_at<? ORDER BY seq", (stream, upper)).fetchall()
    final = None
    if start is None:
        final = conn.execute("SELECT f.*,c.recorded_at FROM finalized_reports f JOIN captures c ON c.seq=f.capture_seq WHERE f.stream=? AND f.finalized_at<? ORDER BY f.seq DESC LIMIT 1", (stream, upper)).fetchone()
        if final:
            lower = final["recorded_at"]
    facts, checks, good_checks, events = {}, {}, {}, []
    latest_status = "incomplete"
    draft_count = 0
    baseline_known = False
    for row in rows:
        payload = json.loads(row["payload"])
        latest_status = payload["status"]
        draft_count = len(payload.get("drafts", []))
        is_baseline = row["seq"] <= final["capture_seq"] if final else bool(lower and row["recorded_at"] < lower)
        if is_baseline:
            baseline_known = True
        for check in payload["checks"]:
            old = good_checks.get(check["id"])
            if old and check["status"] == "verified" and stamp(check["checked_at"]) < stamp(old["checked_at"]):
                # Importing an older run preserves evidence without rolling back
                # the latest successfully checked source state.
                continue
            if not is_baseline and old and old["status"] == check["status"] == "verified" and old["hashes"] != check["hashes"]:
                events.append({"type": "source_changed", "source": check["id"], "recorded_at": row["recorded_at"], "before": old, "after": check})
            checks[check["id"]] = check
            if check["status"] == "verified":
                good_checks[check["id"]] = check
        for item in payload["findings"]:
            old = facts.get(item["key"])
            def last_retrieved(finding):
                return max((stamp(c["retrieved_at"]) for c in finding["citations"] if c.get("retrieved_at")), default="")
            historical = old is not None and last_retrieved(item) < last_retrieved(old)
            if historical:
                if not is_baseline and old["facts"] != item["facts"]:
                    events.append({"type": "historical_observation", "entity": item["key"],
                                   "recorded_at": row["recorded_at"], "historical_finding": item,
                                   "current_finding": old, "requires_review": True})
                continue
            if not is_baseline and (old is None or old["facts"] != item["facts"]):
                events.append({"type": "first_observed" if old is None else "finding_changed", "entity": item["key"],
                               "recorded_at": row["recorded_at"], "capture_id": row["capture_id"],
                               "before": old, "after": item, "requires_review": True})
            facts[item["key"]] = item
    # A known future effective date can matter even when source bytes are unchanged.
    if lower:
        for key, item in facts.items():
            def dates(value):
                if isinstance(value, dict):
                    if value.get("effective_date") and value.get("legal_status") != "withdrawn":
                        yield value["effective_date"]
                    for v in value.values():
                        yield from dates(v)
                elif isinstance(value, list):
                    for v in value:
                        yield from dates(v)
            for effective in set(dates(item["facts"])):
                try:
                    effective_boundary = boundary(effective)
                except (ValueError, TypeError):
                    events.append({"type": "unresolved_effective_date", "entity": key, "after": item, "requires_review": True})
                    continue
                if lower <= effective_boundary < upper:
                    events.append({"type": "effective_date_reached", "entity": key, "effective_date": effective,
                                   "after": item, "requires_review": True})
    gaps = [c for c in checks.values() if c["status"] != "verified"]
    stale = [c["id"] for c in checks.values() if c["status"] == "verified" and (not lower or stamp(c["checked_at"]) <= lower)]
    coverage_summary = {"required_checks": len(checks), "incomplete_checks": len(gaps), "not_rechecked": len(stale)}
    unknown_entity = bool(entity and entity not in facts)
    if entity:
        related = {entity, entity.split(":", 1)[0]}
        versions = [facts[entity]] if entity in facts else []
        for event in events:
            if event.get("entity") == entity:
                versions.extend(v for v in (event.get("before"), event.get("after")) if v)
        related.update(ref["endpoint"] for v in versions for ref in v["citations"] if "endpoint" in ref)
        events = [e for e in events if e.get("entity") == entity or (e["type"] == "source_changed" and e["source"] in related)]
        facts = {k: v for k, v in facts.items() if k == entity}
        checks = {k: v for k, v in checks.items() if k in related}
    return {"stream": stream, "baseline": "explicit_start" if start else "last_finalized_report",
            "baseline_known": baseline_known, "start_utc": lower, "end_exclusive_utc": upper,
            "knowledge_time": "database capture time; publication/effective/retrieval dates remain separate",
            "events": events, "current_findings": facts, "coverage_gaps": gaps,
            "not_rechecked_since_baseline": stale, "source_checks": checks,
            "history_begins_at": rows[0]["recorded_at"] if rows else None,
            "latest_capture_at": rows[-1]["recorded_at"] if rows else None,
            "latest_research_status": latest_status, "unvalidated_receipts": draft_count,
            "unknown_entity": unknown_entity, "global_coverage_summary": coverage_summary,
            "assessment": "review_required" if events else "insufficient_coverage" if (not baseline_known or gaps or stale or not checks or unknown_entity or latest_status != "ready_for_review") else "no_observed_change",
            "caution": "No observed change is limited to recorded checks. It does not prove continuous coverage or legal equivalence. Never infer removal from absence."}
