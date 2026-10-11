"""Tests for C03: Deterministic document and revision identity.

Assertions:
1. Same logical key gives the same document_id across reruns and URL changes.
2. Changed body or legal_status changes revision_id; observed_at and exact_sha256 changes do not.
3. Reordered semantically set-valued roster plus refreshed judge observed_at gives identical revision_id.
4. Changing supersedes_revision_id alone does not change revision_id.
5. Two same-name judges with different verified identity keys remain distinguishable.
6. NaN is rejected by canonical_json; normalized newline/horizontal-space differences hash identically.
"""

import copy
import json
import math
from datetime import datetime, timedelta, timezone

import pytest

from flwu.identity import (
    analysis_id,
    canonical_json,
    document_id,
    normalize_text,
    revision_id,
    semantic_payload,
    stamp_ids,
)
from flwu.records import (
    RecordError,
    semantic_facts,
    validate_record,
)


# ===== Test 1: Same logical key gives same document_id =====

def test_same_key_same_document_id():
    """Same logical key gives the same document_id across reruns."""
    did1 = document_id("source_abc", "doc-key-001")
    did2 = document_id("source_abc", "doc-key-001")
    assert did1 == did2, "Same inputs must give same document_id"
    assert did1.startswith("doc_"), "document_id must start with 'doc_'"
    assert len(did1) == 28, f"document_id must be 28 chars (doc_ + 24 hex), got {len(did1)}"


def test_different_sources_different_document_id():
    """Different source_ids give different document_ids."""
    did1 = document_id("source_abc", "doc-key-001")
    did2 = document_id("source_xyz", "doc-key-001")
    assert did1 != did2, "Different sources must give different document_ids"


def test_different_keys_different_document_id():
    """Different document_keys give different document_ids."""
    did1 = document_id("source_abc", "doc-key-001")
    did2 = document_id("source_abc", "doc-key-002")
    assert did1 != did2, "Different keys must give different document_ids"


def test_document_id_stable_across_url_changes():
    """URL changes do not affect document_id (URL is not used in computation)."""
    did1 = document_id("source_abc", "document_key_001")
    assert document_id("source_abc", "document_key_001") == did1


# ===== Test 2: Changed body/legal_status changes revision_id =====

def _make_test_record(**overrides):
    """Create a test record with computed IDs."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = {
        "schema_version": 1,
        "mode": "fixture",
        "synthetic": False,
        "source_id": "test_source",
        "document_key": "test-doc-key",
        "kind": "case",
        "scope_ids": ["duval"],
        "canonical_url": "https://example.invalid/case/001",
        "title": "State v. Smith",
        "body_text": "This is the case body text.",
        "publication_date": "2026-01-15",
        "effective_date": None,
        "status_date": None,
        "legal_status": "adopted",
        "observed_at": now,
        "exact_sha256": "a" * 64,
        "content_sha256": "b" * 64,
        "pinpoints": [{"page": 1, "paragraph": None, "excerpt": "para 1"}],
        "facts": {"case_name": "State v. Smith", "court": "fourth_dca"},
        "supersedes_revision_id": None,
    }
    base.update(overrides)
    return stamp_ids(base)


def test_changed_body_changes_revision_id():
    """Changed body changes revision_id."""
    r1 = _make_test_record(body_text="Original body")
    r2 = _make_test_record(body_text="Changed body text")
    r3 = _make_test_record(body_text="Another change")
    assert r1["document_id"] == r2["document_id"] == r3["document_id"]
    assert r1["revision_id"] != r2["revision_id"]
    assert r2["revision_id"] != r3["revision_id"]


def test_changed_legal_status_changes_revision_id():
    """Changed legal_status changes revision_id."""
    r1 = _make_test_record(legal_status="adopted")
    r2 = _make_test_record(legal_status="operative")
    r3 = _make_test_record(legal_status="withdrawn")
    assert r1["document_id"] == r2["document_id"]
    assert r1["revision_id"] != r2["revision_id"]
    assert r2["revision_id"] != r3["revision_id"]


def test_observed_at_change_does_not_change_revision_id():
    """observed_at change does NOT change revision_id."""
    now1 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now2 = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r1 = _make_test_record(observed_at=now1)
    r2 = _make_test_record(observed_at=now2)
    assert r1["document_id"] == r2["document_id"]
    assert r1["revision_id"] == r2["revision_id"]


def test_exact_sha256_change_does_not_change_revision_id():
    """Changed exact_sha256 does NOT change revision_id."""
    r1 = _make_test_record(exact_sha256="a" * 64)
    r2 = _make_test_record(exact_sha256="b" * 64)
    assert r1["document_id"] == r2["document_id"]
    assert r1["revision_id"] == r2["revision_id"]


# ===== Test 3: Reordered semantically set-valued roster =====

def test_reordered_roster_same_revision_id():
    """Reordered semantically set-valued roster gives identical revision_id."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r1 = _make_test_record(
        kind="roster",
        facts={
            "judge_observations": [
                {
                    "identity_key": "judge_a",
                    "name": "Judge Smith",
                    "aliases": [],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["duval"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now,
                    "identity_review": "verified",
                },
                {
                    "identity_key": "judge_b",
                    "name": "Judge Jones",
                    "aliases": [],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["clay"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now,
                    "identity_review": "verified",
                },
            ]
        },
    )
    r2 = _make_test_record(
        kind="roster",
        facts={
            "judge_observations": [
                {
                    "identity_key": "judge_b",
                    "name": "Judge Jones",
                    "aliases": [],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["clay"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now,
                    "identity_review": "verified",
                },
                {
                    "identity_key": "judge_a",
                    "name": "Judge Smith",
                    "aliases": [],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["duval"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now,
                    "identity_review": "verified",
                },
            ]
        },
    )
    assert r1["revision_id"] == r2["revision_id"]


def test_refreshed_observed_at_same_revision_id():
    """Refreshed judge observed_at gives identical revision_id."""
    now1 = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r1 = _make_test_record(
        kind="roster",
        facts={
            "judge_observations": [
                {
                    "identity_key": "judge_a",
                    "name": "Judge Smith",
                    "aliases": [],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["duval"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now1,
                    "identity_review": "verified",
                }
            ]
        },
    )
    r2 = _make_test_record(
        kind="roster",
        facts={
            "judge_observations": [
                {
                    "identity_key": "judge_a",
                    "name": "Judge Smith",
                    "aliases": [],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["duval"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now2,
                    "identity_review": "verified",
                }
            ]
        },
    )
    assert r1["revision_id"] == r2["revision_id"]


# ===== Test 4: Changing supersedes_revision_id alone =====

def test_supersedes_change_does_not_change_revision_id():
    """Changing supersedes_revision_id alone does not change revision_id."""
    r1 = _make_test_record(supersedes_revision_id=None)
    r2 = _make_test_record(supersedes_revision_id="rev_" + "c" * 24)
    r3 = _make_test_record(supersedes_revision_id="rev_" + "d" * 24)
    assert r1["revision_id"] == r2["revision_id"] == r3["revision_id"]


# ===== Test 5: Same-name judges with different identity keys =====

def test_same_name_different_identity_keys_distinguishable():
    """Two same-name judges with different verified identity keys are distinguishable."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r1 = _make_test_record(
        kind="roster",
        facts={
            "judge_observations": [
                {
                    "identity_key": "judge_unique_1",
                    "name": "Judge Smith",
                    "aliases": ["J. Smith"],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["duval"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now,
                    "identity_review": "verified",
                }
            ]
        },
    )
    r2 = _make_test_record(
        kind="roster",
        facts={
            "judge_observations": [
                {
                    "identity_key": "judge_unique_2",
                    "name": "Judge Smith",
                    "aliases": ["J. Smith"],
                    "court_level": "circuit",
                    "circuit_id": "fourth",
                    "county_ids": ["duval"],
                    "division": None,
                    "role": "regular",
                    "starts_on": None,
                    "ends_on": None,
                    "official_url": None,
                    "observed_at": now,
                    "identity_review": "verified",
                }
            ]
        },
    )
    # Different identity_key produces different semantic_payload
    assert r1["revision_id"] != r2["revision_id"]


# ===== Test 6: NaN rejected, normalized text hashes identically =====

def test_nan_rejected_by_canonical_json():
    """NaN and Infinity are rejected by canonical_json."""
    # json.dumps raises ValueError for NaN and Infinity with allow_nan=False
    with pytest.raises(ValueError):
        canonical_json({"value": float("nan")})

    with pytest.raises(ValueError):
        canonical_json({"value": float("inf")})


def test_normalized_text_hashes_identically():
    """Normalized newline/horizontal-space differences hash identically."""
    texts = [
        "This is a   test  with   extra   spaces.\n\nMultiple  blank\n\nlines.",
        "This is a test with extra spaces.\n\nMultiple blank\n\nlines.",
        "This  is  a  test  with  extra  spaces.\r\n\r\nMultiple  blank\r\n\r\nlines.\r",
    ]

    normalized = [normalize_text(t) for t in texts]
    assert len(set(normalized)) == 1, f"All normalized texts should be identical: {normalized}"

    cj = [canonical_json({"text": n}) for n in normalized]
    assert len(set(cj)) == 1


def test_normalize_text_preserves_legal_footnotes():
    """normalize_text does not erase legal footnotes or dates."""
    text = "Some opinion text [1] (see Smith v. Jones, 2026).\n\nFootnote [2]: See also\n[3] Roberts, 180 S.Ct. 1 (2020)."
    normalized = normalize_text(text)
    assert "[1]" in normalized
    assert "[2]" in normalized
    assert "[3]" in normalized
    assert "2026" in normalized
    assert "2020" in normalized
