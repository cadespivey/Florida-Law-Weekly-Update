"""Fixture pipeline: normalize, stamp, acquire, and diff records.

Orchestrate fixture normalization, identity stamping, and state acquisition
to produce a complete data snapshot for rendering. Uses only existing
modules from C01–C07; never accesses live network or a local model.

Stores acquisition in the SQLite database, then reads back a snapshot
and runs a semantic diff to produce issue categories.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flwu.normalize import normalize_fixture, NormalizeError
from flwu.identity import stamp_ids
from flwu.diff import compare_snapshots
from flwu.state import (
    open_db,
    migrate,
    begin_run,
    begin_attempt,
    commit_acquisition,
    get_snapshot_records,
    IncompleteSource,
    StateError,
)


class PipelineError(Exception):
    """Raised when a pipeline step fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def run_fixture(
    input_path: Path,
    state_root: Path,
    output_dir: Path,
    *,
    observed_at: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[str, Any]:
    """Run the full fixture pipeline end-to-end.

    Steps:
    1. Load and validate the synthetic fixture JSON.
    2. Normalize all records (validate, stamp, produce DocumentRecords).
    3. Open/initialize the SQLite database at state_root.
    4. Run a fixture acquisition into the database.
    5. Read back the snapshot and run a semantic diff.
    6. Build an issue dict and write it to output_dir.

    Returns the issue dict for programmatic inspection.
    """
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if window_start is None:
        window_start = "2026-01-01"
    if window_end is None:
        window_end = "2026-01-08"

    # Step 1: Load fixture
    fixture_text = input_path.read_text(encoding="utf-8")
    fixture = json.loads(fixture_text)

    # Step 2: Normalize
    normalized_records = normalize_fixture(fixture, observed_at=observed_at)

    # Step 3: Open database
    state_root.mkdir(parents=True, exist_ok=True)
    db_path = state_root / "flwu.db"
    conn = open_db(db_path)
    migrate(conn)

    try:
        # Step 4: Acquire
        run_id = "run_fixture_" + str(abs(hash(input_path.name)) % 100000)
        run_id = f"run_{run_id}"
        source_id = fixture.get("source_id", "fixture:default")
        attempt_id = f"att_{run_id[-4:]}"

        begin_run(
            conn, run_id=run_id, mode="fixture",
            window_start=window_start, window_end=window_end,
            created_at=observed_at,
        )
        conn.commit()

        begin_attempt(conn, attempt_id=attempt_id, run_id=run_id,
                      source_id=source_id, started_at=observed_at)
        conn.commit()

        # Build acquisition records with document_key and canonical_url
        acq_records = []
        for rec in normalized_records:
            acq_records.append({
                "document_id": rec["document_id"],
                "revision_id": rec["revision_id"],
                "content_sha256": rec["content_sha256"],
                "record_json": json.dumps(rec, sort_keys=True),
                "document_key": rec.get("document_key", ""),
                "canonical_url": rec.get("canonical_url", ""),
            })

        snap_id = commit_acquisition(
            conn, attempt_id=attempt_id, source_id=source_id,
            watermark_utc=observed_at,
            records=acq_records,
            coverage={"complete": True, "pages_complete": True, "freshness_verified": True},
            profile_id="default",
        )

        conn.commit()

        # Step 5: Read snapshot and diff
        snapshot_recs = get_snapshot_records(conn, source_id=source_id)

        diff_result = compare_snapshots(
            previous=[], incoming=snapshot_recs, first_run=True, inventory_complete=False
        )

        # Build source coverage
        source_coverage = [
            {
                "source_id": source_id,
                "complete": True,
                "pages_complete": True,
                "freshness_verified": True,
                "requested_start": window_start,
                "requested_end": window_end,
                "checked_at": observed_at,
                "missing_document_ids": [],
                "errors": [],
                "evidence_paths": [str(input_path)],
            }
        ]

        # Build issue categories
        categories = _categorize_records(snapshot_recs, diff_result)

        issue = {
            "issue_id": f"issue_{run_id[-4:]}",
            "version": 1,
            "mode": "fixture",
            "title": "FLWU Fixture Preview",
            "window_start": window_start,
            "window_end": window_end,
            "timezone": "America/New_York",
            "cutoff_utc": observed_at,
            "coverage_status": "complete",
            "review_status": "pending",
            "source_coverage": source_coverage,
            "correction_of": None,
            "categories": categories,
            "snapshot_id": snap_id,
        }

        # Step 6: Write issue file
        output_dir.mkdir(parents=True, exist_ok=True)
        issue_path = output_dir / f"{issue['issue_id']}" / f"v{issue['version']}" / "index.html"
        issue_path.parent.mkdir(parents=True, exist_ok=True)
        issue_path.write_text(_build_html_preview(issue, normalized_records), encoding="utf-8")

    finally:
        conn.close()

    return issue


def _categorize_records(records: list[dict], diff_result: dict) -> dict[str, list[dict]]:
    """Categorize records into issue sections."""
    categories = {"statutes": [], "case_law": [], "procedural_rules": [], "local_rules": []}

    for rec in records:
        record_data = json.loads(rec["record_json"]) if isinstance(rec["record_json"], str) else rec["record_json"]
        kind = record_data.get("kind", "")

        # Classify based on kind
        if kind in ("statute", "bill"):
            categories["statutes"].append(record_data)
        elif kind == "case":
            categories["case_law"].append(record_data)
        elif kind in ("court_rule", "agency_rule"):
            categories["procedural_rules"].append(record_data)
        else:
            # circuit_order, judge_procedure, clerk_notice, roster, assignment
            categories["local_rules"].append(record_data)

    return categories


def _build_html_preview(issue: dict, records: list[dict]) -> str:
    """Build a synthetic fixture preview HTML page."""
    title = _escape(issue.get("title", "FLWU Preview"))
    cutoff = issue.get("cutoff_utc", "N/A")
    mode = issue.get("mode", "fixture")
    window_start = issue.get("window_start", "")
    window_end = issue.get("window_end", "")
    categories = issue.get("categories", {})

    html_parts = [
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n',
        '<meta charset="utf-8">\n<title>', title, '</title>\n',
        '<style>\nbody { font-family: system-ui, sans-serif; max-width: 800px; margin: 2em auto; }\n',
        '.synthetic-warning { background: #fff3cd; padding: 1em; border-left: 4px solid #ffc107; margin-bottom: 1em; }\n',
        'h1, h2, h3, h4 { color: #333; }\n.section { margin: 1.5em 0; }\n',
        '.record { border: 1px solid #ddd; padding: 0.5em; margin: 0.5em 0; }\n',
        '</style>\n</head>\n<body>\n',
    ]

    # Synthetic warning header
    html_parts.append(
        '<h1 class="synthetic-warning">SYNTHETIC FIXTURE PREVIEW — NOT LEGAL RESEARCH</h1>\n'
    )

    # Report title and metadata
    html_parts.extend([
        f'<p><strong>Report:</strong> {title}</p>\n',
        f'<p><strong>Mode:</strong> {mode}</p>\n',
        f'<p><strong>Window:</strong> {window_start} to {window_end}</p>\n',
        f'<p><strong>Cutoff:</strong> {cutoff}</p>\n',
    ])

    # Four major headings
    section_names = [
        ("Statutes", "statutes"),
        ("Case Law", "case_law"),
        ("Procedural Rules", "procedural_rules"),
        ("Local Rules", "local_rules"),
    ]

    for section_title, section_key in section_names:
        records_in_section = categories.get(section_key, [])
        html_parts.append(f'<h2 id="{section_key}">{section_title}</h2>\n')
        html_parts.append(f'<div class="section" id="{section_key}-section">\n')

        if not records_in_section:
            html_parts.append(f'<p>No {section_title.lower()} in this fixture window.</p>\n')
        else:
            for rec in records_in_section:
                html_parts.append('<div class="record">\n')
                html_parts.append(f'<h4>{_escape(rec.get("title", "Untitled"))}</h4>\n')
                html_parts.append(f'<p><em>Kind:</em> {_escape(rec.get("kind", ""))}</p>\n')
                html_parts.append(f'<p><em>Status:</em> {_escape(rec.get("legal_status", "unknown"))}</p>\n')
                if rec.get("body_text"):
                    html_parts.append(f'<p>{_escape(rec["body_text"])}</p>\n')
                if rec.get("canonical_url"):
                    html_parts.append(
                        f'<p><a href="{_escape(rec["canonical_url"])}">'
                        f'{_escape(rec["canonical_url"])}</a></p>\n'
                    )
                html_parts.append('</div>\n')

        html_parts.append('</div>\n')

    # Footer
    html_parts.extend([
        '<hr>\n',
        '<footer><p>Generated by FLWU fixture pipeline. This is synthetic preview data.</p></footer>\n',
        '</body>\n</html>\n',
    ])

    return "".join(html_parts)


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    if not isinstance(text, str):
        text = str(text)
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;"))
