"""Fixture normalization for Florida Litigator Weekly Update.

Converts a synthetic source fixture into validated DocumentRecord objects.
Supports only the explicitly synthetic JSON fixture shape supplied in the pack.

Maps source fields to DocumentRecord, normalizes substantive text, stamps IDs
and validates in fixture mode. Preserves input provenance.

Rejects a fixture without synthetic=true or source_id prefixed fixture:.
Does not add live HTML parsing. Uses observation time supplied by caller,
never hidden now() in normalization. Empty malformed text is a validation
failure rather than a no-change record.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from flwu.records import (
    RecordError,
    VALID_KINDS,
    _deduplicate_sorted_list,
    _remove_nulls,
    canonical_json,
    normalize_text,
    semantic_facts,
    validate_record,
)
from flwu.identity import stamp_ids


class NormalizeError(Exception):
    """Raised when a fixture fails normalization."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def normalize_fixture(value: dict[str, Any], *, observed_at: str | None = None) -> list[dict[str, Any]]:
    """Normalize a synthetic source fixture into DocumentRecord objects.

    Args:
        value: The fixture dict with schema_version, synthetic, source_id, records.
        observed_at: ISO observation time string. Defaults to current UTC now if None.

    Returns:
        A list of validated DocumentRecord dicts, stamped with document_id,
        content_sha256, and revision_id.

    Raises:
        NormalizeError: If the fixture is invalid (missing synthetic, source_id
            without 'fixture:' prefix, malformed records, etc.).
    """
    if observed_at is None:
        now = datetime.now(timezone.utc)
        observed_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    if not isinstance(value, dict):
        raise NormalizeError("NOT_DICT", "Fixture must be a dictionary")

    # Must have synthetic=true
    if not value.get("synthetic"):
        raise NormalizeError("NOT_SYNTHETIC", "Fixture must have synthetic=true")

    # source_id must be prefixed with "fixture:"
    source_id = value.get("source_id")
    if not isinstance(source_id, str) or not source_id.startswith("fixture:"):
        raise NormalizeError("INVALID_SOURCE_ID", "source_id must start with 'fixture:'")

    records = value.get("records")
    if not isinstance(records, list):
        raise NormalizeError("MISSING_RECORDS", "Fixture must have a 'records' list")

    if len(records) == 0:
        raise NormalizeError("EMPTY_RECORDS", "Fixture must have at least one record")

    result = []
    for idx, raw_record in enumerate(records):
        try:
            normalized = _normalize_one(raw_record, source_id, observed_at, record_idx=idx)
            result.append(normalized)
        except RecordError as e:
            raise NormalizeError(
                f"RECORD_{idx}_ERROR",
                f"Record {idx} failed validation: {e.message}",
            ) from e

    return result


def _normalize_one(
    raw: dict[str, Any], source_id: str, observed_at: str, *, record_idx: int = 0
) -> dict[str, Any]:
    """Normalize a single raw fixture record into a DocumentRecord."""
    if not isinstance(raw, dict):
        raise RecordError("RECORD_TYPE", f"Record {record_idx} must be an object")

    # Must have official_key
    official_key = raw.get("official_key")
    if not official_key or not isinstance(official_key, str):
        raise RecordError("MISSING_OFFICIAL_KEY", f"Record {record_idx} missing official_key")

    kind = raw.get("kind")
    if kind not in VALID_KINDS:
        raise RecordError("INVALID_KIND", f"Record {record_idx}: kind must be one of {VALID_KINDS}")

    title = raw.get("title")
    if not title or not isinstance(title, str):
        raise RecordError("MISSING_TITLE", f"Record {record_idx}: title is required")

    body_text = raw.get("body_text")
    if not body_text or not isinstance(body_text, str):
        raise RecordError("MISSING_BODY", f"Record {record_idx}: body_text is required")
    if len(body_text.strip()) == 0:
        raise RecordError("EMPTY_BODY", f"Record {record_idx}: empty body_text is a validation failure")

    # Scope IDs: parse prefixes like "county:duval" -> "duval"
    raw_scope_ids = raw.get("scope_ids")
    if not isinstance(raw_scope_ids, list):
        scope_ids = []
    else:
        scope_ids = []
        for sid in raw_scope_ids:
            if isinstance(sid, str) and ":" in sid:
                scope_ids.append(sid.split(":", 1)[1])
            elif isinstance(sid, str):
                scope_ids.append(sid.strip())

    # Dates
    pub_date = raw.get("publication_date")
    eff_date = raw.get("effective_date")
    stat_date = raw.get("status_date")
    legal_status = raw.get("legal_status", "unknown")

    # Build a copy of the raw record's canonical JSON for exact_sha256
    raw_canonical = canonical_json(
        {
            "official_key": official_key,
            "kind": kind,
            "title": title,
            "body_text": body_text,
            "canonical_url": raw.get("canonical_url"),
            "scope_ids": raw.get("scope_ids"),
            "publication_date": pub_date,
            "effective_date": eff_date,
            "status_date": stat_date,
            "legal_status": legal_status,
            "facts": raw.get("facts"),
        }
    )
    exact_sha = hashlib.sha256(raw_canonical).hexdigest()

    # Build the DocumentRecord dict (pre-stamping)
    record: dict[str, Any] = {
        "schema_version": 1,
        "mode": "fixture",
        "synthetic": True,
        "source_id": source_id,
        "document_key": official_key,
        "kind": kind,
        "scope_ids": sorted(set(scope_ids)),
        "canonical_url": raw.get("canonical_url") or "",
        "title": normalize_text(title),
        "body_text": normalize_text(body_text),
        "publication_date": pub_date,
        "effective_date": eff_date,
        "status_date": stat_date,
        "legal_status": legal_status,
        "observed_at": observed_at,
        "exact_sha256": exact_sha,
        "pinpoints": [{"page": None, "paragraph": "fixture:1", "excerpt": normalize_text(body_text)}],
        "facts": raw.get("facts") or {},
        "supersedes_revision_id": None,
    }

    # Stamp IDs (document_id, content_sha256, revision_id)
    stamped = stamp_ids(record)

    # Validate in fixture mode
    validated = validate_record(stamped, mode="fixture")

    # Add provenance info
    validated["_source_provenance"] = {
        "source_id": source_id,
        "raw_official_key": official_key,
        "record_index": record_idx,
    }

    return validated
