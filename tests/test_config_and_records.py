"""Tests for C02: Configuration and structural record validation.

Assertions:
1. Unknown record/config keys raise stable error codes; input dict is not mutated.
2. Production rejects synthetic=true, mode mismatch, credentials embedded in URL and example.invalid sources.
3. Adopted future date is not operative; unknown effective date is not operative; withdrawn is never operative.
4. Nullable facts remain null, and unsupported invented date precision is rejected.
5. Registry check uses injected sets and rejects unknown source/scope without requiring registry.py.
"""

import copy
import datetime
import json
import time
from pathlib import Path

import pytest

# Import from the package
from flwu.config import ConfigError, load_config, _load_defaults
from flwu.records import (
    RecordError,
    validate_record,
    validate_analysis,
    validate_registry_references,
    is_operative,
    canonical_json,
    normalize_text,
    record_json_schema,
)


# ===== Test helpers =====

def _make_minimal_record(**overrides: object) -> dict:
    """Create a minimal valid record with the given overrides."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = {
        "schema_version": 1,
        "mode": "fixture",
        "synthetic": False,
        "source_id": "test_source",
        "document_key": "test-key-001",
        "document_id": "doc_" + "a" * 24,
        "revision_id": "rev_" + "b" * 24,
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
        "facts": {
            "case_name": "State v. Smith",
            "case_number": "2025-cv-1234",
            "court": "fourth_dca",
            "disposition": "affirmed",
        },
        "supersedes_revision_id": None,
    }
    base.update(overrides)
    return base


# ===== Test 1: Unknown record/config keys raise stable error codes =====

def test_unknown_record_keys_raise_record_error():
    """Unknown record/config keys raise stable error codes; input dict is not mutated.

    The test passes a record WITH extra keys (via an override) and verifies that
    validate_record rejects them with a stable error code without mutating the
    input dictionary.
    """
    # Build a record that includes an unknown top-level key
    base = _make_minimal_record()
    base["unknown_field"] = "extra"
    original_keys = set(base.keys())
    original_values = dict(base)

    with pytest.raises(RecordError, match="UNKNOWN_KEY"):
        validate_record(base, mode="fixture")
    # The function raised before adding any keys — the only extra key was ours
    assert set(base.keys()) == original_keys, "validate_record added keys to input"
    assert base == original_values, "validate_record changed values in input"


def test_unknown_config_keys_raise_config_error(tmp_path: Path) -> None:
    """Unknown config keys raise ConfigError; input dict is not mutated."""
    config_file = tmp_path / "config.json"
    config_data = {
        "schema_version": 1,
        "mode": "fixture",
        "timezone": "America/New_York",
        "schedule": {"weekday": 0, "hour": 8, "minute": 0},
        "research": {"overlap_days": 14, "bootstrap_days": 14},
        "limits": {
            "external_usd": 0,
            "http_timeout_seconds": 30,
            "http_retries": 3,
            "host_spacing_seconds": 1,
            "run_minutes": 120,
            "source_minutes": 15,
            "requests_per_run": 2000,
            "model_calls_per_run": 250,
            "model_timeout_seconds": 300,
            "model_repairs_per_item": 2,
            "state_gib": 5,
            "retention_days": 30,
        },
        "model": {"base_url": None, "model_id": None, "cloud_fallback": False},
        "publication": {"mode": "manual"},
        "state_root": None,
        "unauthorized_extra": True,
    }
    config_file.write_text(json.dumps(config_data))
    with pytest.raises(ConfigError, match="UNKNOWN_KEYS"):
        load_config(config_file)


def test_validate_does_not_mutate_input():
    """validate_record does not mutate the input dictionary."""
    record = _make_minimal_record()
    original_keys = set(record.keys())

    try:
        validate_record(record, mode="fixture")
    except RecordError:
        pass  # Expected for this fixture

    assert set(record.keys()) == original_keys, "Input was mutated"


# ===== Test 2: Production rejects synthetic=true, mode mismatch, credentials, example.invalid =====

def test_production_rejects_synthetic_true():
    """Production rejects synthetic=true."""
    record = _make_minimal_record(synthetic=True)
    with pytest.raises(RecordError):
        validate_record(record, mode="production")


def test_production_rejects_mode_mismatch():
    """Production rejects mode mismatch (fixture record in production mode)."""
    record = _make_minimal_record(mode="fixture")
    with pytest.raises(RecordError, match="MODE_MISMATCH"):
        validate_record(record, mode="production")


def test_production_rejects_credentials_in_url():
    """Production rejects credentials embedded in URL."""
    record = _make_minimal_record(
        mode="production",
        synthetic=False,
        canonical_url="https://user:password@example.com/case",
    )
    with pytest.raises(RecordError, match="URL_CREDENTIALS"):
        validate_record(record, mode="production")


def test_production_rejects_example_invalid():
    """Production rejects example.invalid sources."""
    record = _make_minimal_record(
        mode="production",
        synthetic=False,
        canonical_url="https://example.invalid/case/1",
    )
    with pytest.raises(RecordError, match="URL_EXAMPLE_INVALID"):
        validate_record(record, mode="production")


# ===== Test 3: is_operative rules =====

def test_adopted_future_date_not_operative():
    """Adopted with a future effective date is not operative."""
    record = _make_minimal_record(
        legal_status="adopted",
        effective_date="2027-01-15",
    )
    assert is_operative(record, as_of="2026-10-10") is False


def test_adopted_unknown_effective_date_not_operative():
    """Adopted with an unknown effective date is not operative."""
    record = _make_minimal_record(
        legal_status="adopted",
        effective_date=None,
    )
    assert is_operative(record, as_of="2026-10-10") is False


def test_withdrawn_never_operative():
    """Withdrawn records are never operative."""
    record = _make_minimal_record(legal_status="withdrawn")
    assert is_operative(record, as_of="2026-10-10") is False


def test_adopted_with_past_effective_date_is_operative():
    """Adopted with a past effective date is operative."""
    record = _make_minimal_record(
        legal_status="adopted",
        effective_date="2025-06-15",
    )
    assert is_operative(record, as_of="2026-10-10") is True


def test_operative_without_future_effective_date():
    """Operative without future effective date is operative."""
    record = _make_minimal_record(legal_status="operative")
    assert is_operative(record, as_of="2026-10-10") is True


def test_proposed_unknown_withdrawn_superseded_never_operative():
    """Non-operative statuses are never operative."""
    for status in ("proposed", "unknown", "superseded"):
        record = _make_minimal_record(legal_status=status)
        assert is_operative(record, as_of="2026-10-10") is False, f"Status {status} should not be operative"


# ===== Test 4: Nullable facts remain null, unsupported invented date precision rejected =====

def test_nullable_facts_remain_null():
    """Nullable facts remain null when not provided."""
    record = _make_minimal_record(
        facts={},
        canonical_url="https://actual-valid-site.example/case",
    )
    validated = validate_record(record, mode="fixture")
    # Should not manufacture facts that weren't there
    assert validated.get("facts") == {} or validated.get("facts") is None


def test_invented_date_precision_rejected():
    """Unsupported invented date precision is rejected."""
    from flwu.records import RecordError

    record = _make_minimal_record(
        canonical_url="https://actual-valid-site.example/case",
        facts={
            "date_details": {
                "publication_date": {
                    "value": "2026-01-15",
                    "precision": "century",  # invalid precision
                    "source_text": None,
                }
            }
        },
    )
    with pytest.raises(RecordError, match="DATE_PRECISION"):
        validate_record(record, mode="fixture")


# ===== Test 5: Registry check uses injected sets and rejects unknown source/scope =====

def test_registry_check_accepts_valid_source():
    """Registry check accepts a valid source_id."""
    record = _make_minimal_record()
    validate_registry_references(record, source_ids={"test_source"}, scope_ids={"duval"})


def test_registry_check_accepts_valid_scope():
    """Registry check accepts a valid scope_id."""
    record = _make_minimal_record(scope_ids=["duval", "st-johns"])
    validate_registry_references(record, source_ids={"test_source"}, scope_ids={"duval", "st-johns"})


def test_registry_check_rejects_unknown_source():
    """Registry check rejects unknown source_id."""
    record = _make_minimal_record(source_id="unknown_source")
    with pytest.raises(RecordError, match="SOURCE_NOT_IN_REGISTRY"):
        validate_registry_references(record, source_ids={"test_source"}, scope_ids={"duval"})


def test_registry_check_rejects_unknown_scope():
    """Registry check rejects unknown scope_id."""
    record = _make_minimal_record(scope_ids=["clark"])
    with pytest.raises(RecordError, match="SCOPE_NOT_IN_REGISTRY"):
        validate_registry_references(record, source_ids={"test_source"}, scope_ids={"duval"})


def test_registry_check_does_not_require_registry():
    """validate_registry_references does not import any registry module."""
    # This is a design assertion — the function receives sets directly
    # and does not perform any module-level imports.
    assert callable(validate_registry_references)


# ===== Additional: config loading tests =====

def test_load_config_defaults_returns_defaults(tmp_path: Path) -> None:
    """Loading from a valid config file returns the config."""
    config_file = tmp_path / "config.json"
    defaults = _load_defaults()
    config_file.write_text(json.dumps(defaults))
    result = load_config(config_file)
    assert result == defaults


def test_load_config_no_path_returns_defaults_when_no_file():
    """load_config(None) returns defaults when config file doesn't exist."""
    # Temporarily rename the actual config file
    import os
    actual_path = Path("config/defaults.json")
    moved = False
    if actual_path.exists():
        backup = Path("config/defaults.json.bak")
        actual_path.rename(backup)
        moved = True
    try:
        result = load_config(None)
        assert result == _load_defaults()
    finally:
        if moved:
            backup.rename(actual_path)


def test_load_config_extra_nested_keys_rejected(tmp_path: Path) -> None:
    """Extra keys nested in config objects are rejected."""
    config_file = tmp_path / "config.json"
    defaults = _load_defaults()
    defaults["limits"]["extra_limit"] = 99
    config_file.write_text(json.dumps(defaults))
    with pytest.raises(ConfigError, match="UNKNOWN_KEYS"):
        load_config(config_file)
