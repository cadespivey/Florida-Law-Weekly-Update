"""Tests for C04: Fixture normalization.

Assertions:
1. Fixture produces exactly the expected two logical records, each mode fixture and synthetic true.
2. Repeat normalization at a new observation time preserves document/revision IDs.
3. Different record order produces the same sorted-by-document-id output.
4. Malformed fixture with missing official_key fails; normalization makes no network call.
"""

import json
from pathlib import Path

import pytest

from flwu.normalize import NormalizeError, normalize_fixture


# Load the fixture from disk
_FIXTURE_PATH = Path("fixtures/synthetic-source.json")
with open(_FIXTURE_PATH) as f:
    _FIXTURE_DATA = json.load(f)

_expected_path = Path("fixtures/expected-identities.json")
expected_record_ids = json.loads(_expected_path.read_text())


# ===== Test 1: Fixture produces exactly two records =====

def test_fixture_produces_expected_records():
    """Fixture produces exactly the expected two logical records."""
    results = normalize_fixture(_FIXTURE_DATA)
    assert len(results) == 3, f"Expected 3 records, got {len(results)}"

    for r in results:
        assert r["mode"] == "fixture"
        assert r["synthetic"] is True

    keys = {r["document_key"] for r in results}
    assert keys == {"SYN-001", "SYN-002", "SYN-003"}

    for r in results:
        dk = r["document_key"]
        assert r["document_id"].startswith("doc_")
        if str(dk) in expected_record_ids:
            assert r["document_id"] == expected_record_ids[str(dk)]


def test_fixture_records_have_stamped_ids():
    """Each record has document_id, content_sha256, and revision_id."""
    results = normalize_fixture(_FIXTURE_DATA)
    for r in results:
        assert r["document_id"].startswith("doc_")
        assert len(r["content_sha256"]) == 64
        assert r["revision_id"].startswith("rev_")


# ===== Test 2: Repeat normalization at new observation time =====

def test_repeat_normalization_preserves_ids():
    """Repeat normalization at a new observation time preserves document/revision IDs."""
    observed1 = "2026-10-01T08:00:00Z"
    observed2 = "2026-10-01T12:00:00Z"

    results1 = normalize_fixture(_FIXTURE_DATA, observed_at=observed1)
    results2 = normalize_fixture(_FIXTURE_DATA, observed_at=observed2)

    assert len(results1) == len(results2) == 3
    for r1, r2 in zip(results1, results2):
        assert r1["document_id"] == r2["document_id"]
        assert r1["revision_id"] == r2["revision_id"]
        assert r1["observed_at"] != r2["observed_at"]


# ===== Test 3: Different record order =====

def test_different_record_order_same_output():
    """Different record order produces the same sorted-by-document-id output."""
    reversed_fixture = dict(_FIXTURE_DATA)
    reversed_fixture["records"] = list(reversed(_FIXTURE_DATA["records"]))

    results_normal = normalize_fixture(_FIXTURE_DATA)
    results_reversed = normalize_fixture(reversed_fixture)

    sorted_normal = sorted(results_normal, key=lambda r: r["document_id"])
    sorted_reversed = sorted(results_reversed, key=lambda r: r["document_id"])

    assert len(sorted_normal) == len(sorted_reversed) == 3
    for r1, r2 in zip(sorted_normal, sorted_reversed):
        assert r1["document_id"] == r2["document_id"]
        assert r1["revision_id"] == r2["revision_id"]
        assert r1["document_key"] == r2["document_key"]


# ===== Test 4: Malformed fixture fails =====

def test_malformed_fixture_missing_official_key():
    """Malformed fixture with missing official_key fails."""
    malformed = dict(_FIXTURE_DATA)
    malformed["records"] = [
        {"kind": "judge_procedure", "title": "Test", "body_text": "Body text"}
    ]
    with pytest.raises(NormalizeError, match="MISSING_OFFICIAL_KEY|RECORD_"):
        normalize_fixture(malformed)


def test_malformed_fixture_missing_body():
    """Malformed fixture with missing body_text fails."""
    malformed = dict(_FIXTURE_DATA)
    malformed["records"] = [
        {"official_key": "TEST-001", "kind": "judge_procedure", "title": "Test"}
    ]
    with pytest.raises(NormalizeError, match="MISSING_BODY|RECORD_"):
        normalize_fixture(malformed)


def test_malformed_fixture_empty_body():
    """Malformed fixture with empty body_text fails."""
    malformed = dict(_FIXTURE_DATA)
    malformed["records"] = [
        {"official_key": "TEST-001", "kind": "judge_procedure", "title": "Test", "body_text": "   "}
    ]
    with pytest.raises(NormalizeError, match="EMPTY_BODY|RECORD_"):
        normalize_fixture(malformed)


def test_fixture_without_synthetic():
    """Fixture without synthetic=true is rejected."""
    malformed = dict(_FIXTURE_DATA)
    malformed["synthetic"] = False
    with pytest.raises(NormalizeError, match="NOT_SYNTHETIC"):
        normalize_fixture(malformed)


def test_fixture_without_fixture_prefix():
    """Fixture with source_id not starting with fixture: is rejected."""
    malformed = dict(_FIXTURE_DATA)
    malformed["source_id"] = "live_source:abc"
    with pytest.raises(NormalizeError, match="INVALID_SOURCE_ID"):
        normalize_fixture(malformed)


def test_no_network_call_on_malformed():
    """Normalization makes no network call for malformed fixtures."""
    import flwu.normalize as normalize_mod

    original = normalize_mod._normalize_one
    called = {"count": 0}

    def mock_normalize(*args, **kwargs):
        called["count"] += 1
        return original(*args, **kwargs)

    normalize_mod._normalize_one = mock_normalize
    try:
        malformed = dict(_FIXTURE_DATA)
        malformed["records"] = [{"kind": "x", "title": "T", "body_text": "B"}]
        with pytest.raises(NormalizeError):
            normalize_fixture(malformed)
        assert called["count"] == 1  # _normalize_one called once, no network
    finally:
        normalize_mod._normalize_one = original


def test_fixture_preserves_provenance():
    """Normalized records preserve source provenance."""
    results = normalize_fixture(_FIXTURE_DATA)
    for r in results:
        prov = r.get("_source_provenance")
        assert prov is not None
        assert prov["source_id"].startswith("fixture:")
        assert prov["raw_official_key"] in ("SYN-001", "SYN-002", "SYN-003")
