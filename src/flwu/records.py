"""Record and analysis result validation for Florida Litigator Weekly Update.

Implements dictionary-shaped JSON records with explicit validators. Unknown keys
are rejected. Functions return new dictionaries, never mutate inputs.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from typing import Any

# stdlib-only ISO date parsing

# Pre-compiled regexes
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_REV_ID_RE = re.compile(r"^rev_[0-9a-f]{24}$")
_DOC_ID_RE = re.compile(r"^doc_[0-9a-f]{24}$")
_ANA_ID_RE = re.compile(r"^ana_[0-9a-f]{24}$")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_CREDENTIALS_RE = re.compile(
    r"(password|token|secret|key)\s*[=:]", re.IGNORECASE
)
_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}$"
)
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_YEAR_RE = re.compile(r"^\d{4}$")


class RecordError(Exception):
    """Raised when a record fails structural or type validation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ----- Enums -----

VALID_RECORD_MODES = frozenset({"fixture", "production"})
VALID_KINDS = frozenset({
    "statute", "bill", "case", "court_rule", "agency_rule",
    "circuit_order", "judge_procedure", "clerk_notice", "roster", "assignment",
})
VALID_STATUSES = frozenset({
    "proposed", "adopted", "operative", "withdrawn", "superseded", "unknown"
})
VALID_AUTHORITIES = frozenset({
    "binding_rule", "binding_order", "advisory_preference",
    "clerk_operation", "proposal", "unknown",
})
VALID_ROLES = frozenset({
    "regular", "senior", "visiting", "temporary", "administrative",
})
VALID_LEVELS = frozenset({"circuit", "county"})
VALID_COURTS = frozenset({
    "florida_supreme_court", "first_dca", "second_dca", "third_dca",
    "fourth_dca", "fifth_dca", "sixth_dca",
})
VALID_LEGISLATIVE_STAGES = frozenset({
    "filed", "committee_substitute", "passed", "enrolled",
    "governor_action", "chaptered", "unknown",
})
VALID_OPINION_TYPES = frozenset({
    "majority", "concurrence", "dissent", "per_curiam", "pca", "pcd", "unknown",
})
VALID_IDENTITY_REVIEWS = frozenset({"verified", "needs_review"})
VALID_PRECISIONS = frozenset({"day", "month", "year", "unknown"})
VALID_CHARACTERIZATIONS = frozenset({
    "source_fact", "inference", "holding", "dicta", "concurrence", "dissent",
})
VALID_ANALYSIS_STATUSES = frozenset({"done", "needs_review"})


# ----- Validation helpers -----

def _validate_date(value: Any) -> str | None:
    """Validate a date string. Returns it if valid, else raises."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordError("DATE_TYPE", "date must be string or null")
    m = _DATE_RE.match(value)
    if not m:
        raise RecordError("DATE_FORMAT", f"Invalid date format: {value!r}")
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise RecordError("DATE_INVALID", f"Date not calendar-valid: {value}")
    return value


def _validate_month(value: Any) -> str | None:
    """Validate a month string."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordError("MONTH_TYPE", "month must be string or null")
    if not _MONTH_RE.match(value):
        raise RecordError("MONTH_FORMAT", f"Invalid month: {value!r}")
    return value


def _validate_year(value: Any) -> str | None:
    """Validate a year string."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordError("YEAR_TYPE", "year must be string or null")
    if not _YEAR_RE.match(value):
        raise RecordError("YEAR_FORMAT", f"Invalid year: {value!r}")
    return value


def _validate_nonempty_string(value: Any, field: str) -> str:
    """Validate a non-empty string field."""
    if value is None:
        raise RecordError(f"{field.upper()}_NULL", f"Field '{field}' must be non-empty")
    if not isinstance(value, str):
        raise RecordError(f"{field.upper()}_TYPE", f"Field '{field}' must be a string")
    if len(value.strip()) == 0:
        raise RecordError(f"{field.upper()}_EMPTY", f"Field '{field}' must not be empty")
    return value


def _validate_url(value: Any, *, allow_example_invalid: bool = False) -> str:
    """Validate an HTTPS/HTTP URL."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RecordError("URL_TYPE", "URL must be string or null")
    if not _URL_RE.match(value):
        raise RecordError("URL_FORMAT", f"URL must be absolute HTTPS/HTTP: {value!r}")
    # Check for credentials
    if "://" in value:
        rest = value.split("://", 1)[1]
        if "@" in rest:
            raise RecordError("URL_CREDENTIALS", "URL must not contain credentials")
    # In production mode, example.invalid is not allowed
    if allow_example_invalid:
        pass  # fixture mode allows it
    else:
        # Production: example.invalid is not allowed
        if "example.invalid" in value:
            raise RecordError("URL_EXAMPLE_INVALID", "example.invalid is fixture-only")
    return value


def _validate_boolean(value: Any) -> bool:
    """Validate a boolean — NOT an integer."""
    if not isinstance(value, bool):
        raise RecordError("BOOLEAN_TYPE", "must be boolean, not integer")
    return value


def _validate_list_of_strings(value: Any, field: str) -> list[str]:
    """Validate a list of strings."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise RecordError(f"{field}_TYPE", f"{field} must be list or null")
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise RecordError(f"{field}_ITEM_TYPE", f"{field}[{i}] must be string")
    return value


def _validate_sorted_unique_strings(value: Any, field: str) -> list[str]:
    """Validate a sorted, unique list of nonempty strings."""
    result = _validate_list_of_strings(value, field)
    if len(result) == 0:
        return result
    stripped = [s.strip() for s in result]
    for i, s in enumerate(stripped):
        if len(s) == 0:
            raise RecordError(f"{field}_EMPTY", f"{field} contains empty string at index {i}")
    if stripped != sorted(stripped):
        raise RecordError(f"{field}_SORTED", f"{field} must be sorted")
    if len(stripped) != len(set(stripped)):
        raise RecordError(f"{field}_UNIQUE", f"{field} must be unique")
    return stripped


def _validate_sha256(value: Any, field: str) -> str:
    """Validate a 64-hex-character SHA-256 hash."""
    if value is None:
        raise RecordError(f"{field}_NULL", f"{field} must not be null")
    if not isinstance(value, str):
        raise RecordError(f"{field}_TYPE", f"{field} must be string")
    if not _HASH_RE.match(value):
        raise RecordError(f"{field}_FORMAT", f"Invalid {field}: must be 64 lowercase hex chars")
    return value


def _validate_observations(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate judge_observations (list of JudgeObservation objects)."""
    if not isinstance(value, list):
        raise RecordError("OBSERVATIONS_TYPE", "judge_observations must be a list")
    result = []
    for obs in value:
        if not isinstance(obs, dict):
            raise RecordError("OBSERVATION_TYPE", "each observation must be an object")
        required_fields = {"identity_key", "name", "aliases", "court_level",
                          "circuit_id", "county_ids", "division", "role",
                          "starts_on", "ends_on", "official_url", "observed_at",
                          "identity_review"}
        extra_fields = set(obs.keys()) - required_fields
        if extra_fields:
            raise RecordError("OBSERVATION_UNKNOWN_KEY",
                              f"Unknown observation fields: {sorted(extra_fields)}")
        # Validate individual fields
        identity_key = obs.get("identity_key")
        if identity_key is not None and not isinstance(identity_key, str):
            raise RecordError("OBS_IDENTITY_KEY_TYPE", "identity_key must be string or null")

        name = obs.get("name")
        if not isinstance(name, str) or len(name.strip()) == 0:
            raise RecordError("OBS_NAME", "name must be non-empty string")

        aliases = _validate_list_of_strings(obs.get("aliases"), "aliases")

        court_level = obs.get("court_level")
        if court_level not in VALID_LEVELS:
            raise RecordError("OBS_COURT_LEVEL", f"court_level must be one of {VALID_LEVELS}")

        circuit_id = obs.get("circuit_id")
        if circuit_id is not None and circuit_id not in {"fourth", "seventh", "eighth"}:
            raise RecordError("OBS_CIRCUIT_ID", "circuit_id must be fourth/seventh/eighth or null")

        county_ids = _validate_list_of_strings(obs.get("county_ids"), "county_ids")
        valid_counties = {"duval", "st-johns", "clay", "nassau", "baker", "union"}
        for cid in county_ids:
            if cid not in valid_counties:
                raise RecordError("OBS_COUNTY_ID", f"county_id must be one of {valid_counties}")

        division = obs.get("division")
        if division is not None and not isinstance(division, str):
            raise RecordError("OBS_DIVISION_TYPE", "division must be string or null")

        role = obs.get("role")
        if role not in VALID_ROLES:
            raise RecordError("OBS_ROLE", f"role must be one of {VALID_ROLES}")

        starts_on = obs.get("starts_on")
        ends_on = obs.get("ends_on")
        if starts_on is not None:
            _validate_date(starts_on)
        if ends_on is not None:
            _validate_date(ends_on)

        official_url = obs.get("official_url")
        if official_url is not None:
            _validate_url(official_url)

        observed_at = obs.get("observed_at")
        if not isinstance(observed_at, str):
            raise RecordError("OBS_OBSERVED_TYPE", "observed_at must be a string")
        if not observed_at.endswith("Z"):
            raise RecordError("OBS_OBSERVED_TZ", "observed_at must be timezone-aware UTC ending with Z")

        identity_review = obs.get("identity_review")
        if identity_review not in VALID_IDENTITY_REVIEWS:
            raise RecordError("OBS_IDENTITY_REVIEW",
                              f"identity_review must be one of {VALID_IDENTITY_REVIEWS}")

        result.append(obs)
    return result


# ----- Top-level record validation -----

_REQUIRED_TOP_LEVEL = frozenset({
    "schema_version", "mode", "synthetic", "source_id", "document_key",
    "document_id", "revision_id", "kind", "scope_ids", "canonical_url",
    "title", "body_text", "publication_date", "effective_date", "status_date",
    "legal_status", "observed_at", "exact_sha256", "content_sha256",
    "pinpoints", "facts", "supersedes_revision_id",
})


def _validate_record_top_level(value: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Validate the top-level fields of a DocumentRecord."""
    result: dict[str, Any] = {}
    extra_keys = set(value.keys()) - _REQUIRED_TOP_LEVEL
    if extra_keys:
        raise RecordError("UNKNOWN_KEY", f"Unknown top-level keys: {sorted(extra_keys)}")

    # schema_version: integer, exactly 1
    sv = value.get("schema_version")
    if not isinstance(sv, int) or isinstance(sv, bool):
        raise RecordError("SCHEMA_VERSION_TYPE", "schema_version must be integer")
    if sv != 1:
        raise RecordError("SCHEMA_VERSION_VALUE", "schema_version must be exactly 1")
    result["schema_version"] = sv

    # mode
    mode_val = value.get("mode")
    if mode_val not in VALID_RECORD_MODES:
        raise RecordError("MODE_INVALID", f"mode must be 'fixture' or 'production'")
    if mode_val != mode:
        raise RecordError("MODE_MISMATCH", f"mode must equal caller's mode '{mode}'")
    result["mode"] = mode_val

    # synthetic: boolean
    synthetic = value.get("synthetic")
    if not isinstance(synthetic, bool):
        raise RecordError("SYNTHETIC_TYPE", "synthetic must be boolean")
    result["synthetic"] = synthetic

    # source_id: nonempty string
    source_id = _validate_nonempty_string(value.get("source_id"), "source_id")
    result["source_id"] = source_id

    # document_key: nonempty string
    document_key = _validate_nonempty_string(value.get("document_key"), "document_key")
    result["document_key"] = document_key

    # document_id: computed string (not random)
    doc_id = value.get("document_id")
    if not isinstance(doc_id, str) or not _DOC_ID_RE.match(doc_id):
        raise RecordError("DOCUMENT_ID_FORMAT", "document_id must match '^doc_[0-9a-f]{24}$'")
    result["document_id"] = doc_id

    # revision_id: computed string (not random)
    rev_id = value.get("revision_id")
    if not isinstance(rev_id, str) or not _REV_ID_RE.match(rev_id):
        raise RecordError("REVISION_ID_FORMAT", "revision_id must match '^rev_[0-9a-f]{24}$'")
    result["revision_id"] = rev_id

    # kind
    kind = value.get("kind")
    if kind not in VALID_KINDS:
        raise RecordError("KIND_INVALID", f"kind must be one of {VALID_KINDS}")
    result["kind"] = kind

    # scope_ids: sorted unique nonempty list
    scope_ids = _validate_sorted_unique_strings(value.get("scope_ids"), "scope_ids")
    if len(scope_ids) == 0:
        raise RecordError("SCOPE_IDS_EMPTY", "scope_ids must be nonempty")
    result["scope_ids"] = scope_ids

    # canonical_url
    canonical_url = _validate_url(
            value.get("canonical_url"),
            allow_example_invalid=(mode == "fixture"),
        )
    result["canonical_url"] = canonical_url

    # title: nonempty string
    title = _validate_nonempty_string(value.get("title"), "title")
    result["title"] = title

    # body_text
    body_text = value.get("body_text")
    if body_text is not None and not isinstance(body_text, str):
        raise RecordError("BODY_TYPE", "body_text must be string or null")
    if body_text is not None and len(body_text.strip()) == 0:
        facts = value.get("facts", {})
        if isinstance(facts, dict):
            extraction_error = facts.get("extraction_error")
            if extraction_error is None:
                raise RecordError("BODY_EMPTY", "body_text empty without facts.extraction_error")
    result["body_text"] = body_text if body_text is not None else ""

    # publication_date
    pub_date = _validate_date(value.get("publication_date"))
    result["publication_date"] = pub_date

    # effective_date
    eff_date = _validate_date(value.get("effective_date"))
    result["effective_date"] = eff_date

    # status_date
    stat_date = _validate_date(value.get("status_date"))
    result["status_date"] = stat_date

    # legal_status
    legal_status = value.get("legal_status")
    if legal_status not in VALID_STATUSES:
        raise RecordError("LEGAL_STATUS_INVALID", f"legal_status must be one of {VALID_STATUSES}")
    result["legal_status"] = legal_status

    # observed_at: timezone-aware UTC ISO string ending Z
    observed_at = value.get("observed_at")
    if not isinstance(observed_at, str):
        raise RecordError("OBSERVED_TYPE", "observed_at must be a string")
    if not observed_at.endswith("Z"):
        raise RecordError("OBSERVED_TZ", "observed_at must be timezone-aware UTC ending with Z")
    # Parse to validate
    try:
        dt_str = observed_at[:-1] + "+00:00" if observed_at.endswith("Z") else observed_at
        dt = datetime.datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        raise RecordError("OBSERVED_PARSE", f"Could not parse observed_at: {observed_at!r}")
    result["observed_at"] = observed_at

    # exact_sha256: 64 lowercase hex
    exact_sha = _validate_sha256(value.get("exact_sha256"), "exact_sha256")
    result["exact_sha256"] = exact_sha

    # content_sha256: 64 lowercase hex
    content_sha = _validate_sha256(value.get("content_sha256"), "content_sha256")
    result["content_sha256"] = content_sha

    # pinpoints: list of objects with page, paragraph, excerpt
    raw_pinpoints = value.get("pinpoints")
    if raw_pinpoints is None:
        result["pinpoints"] = []
    elif not isinstance(raw_pinpoints, list):
        raise RecordError("PINPOINT_TYPE", "pinpoints must be list or null")
    else:
        parsed_pins = []
        for i, pin in enumerate(raw_pinpoints):
            if not isinstance(pin, dict):
                raise RecordError(f"PINPOINT_{i}_TYPE", f"pinpoint[{i}] must be object")
            pin_extra = set(pin.keys()) - {"page", "paragraph", "excerpt"}
            if pin_extra:
                raise RecordError(f"PINPOINT_{i}_UNKNOWN", f"Unknown pinpoint keys: {sorted(pin_extra)}")
            page = pin.get("page")
            paragraph = pin.get("paragraph")
            excerpt = pin.get("excerpt")
            if page is not None and not isinstance(page, int):
                raise RecordError(f"PINPOINT_{i}_PAGE", "page must be integer >= 1 or null")
            if page is not None and page < 1:
                raise RecordError(f"PINPOINT_{i}_PAGE", "page must be >= 1")
            if paragraph is not None and not isinstance(paragraph, str):
                raise RecordError(f"PINPOINT_{i}_PARAGRAPH", "paragraph must be string or null")
            if excerpt is not None and not isinstance(excerpt, str):
                raise RecordError(f"PINPOINT_{i}_EXCERPT", "excerpt must be string")
            # page or paragraph must identify a location
            if page is None and paragraph is None:
                raise RecordError(f"PINPOINT_{i}_LOCATION", "page or paragraph must identify a location")
            parsed_pins.append({"page": page, "paragraph": paragraph, "excerpt": excerpt})
        result["pinpoints"] = parsed_pins

    # facts: validated per kind
    result["facts"] = _validate_facts(value.get("facts"), kind)

    # supersedes_revision_id: string or null
    supersedes = value.get("supersedes_revision_id")
    if supersedes is not None and not isinstance(supersedes, str):
        raise RecordError("SUPERSEDES_TYPE", "supersedes_revision_id must be string or null")
    result["supersedes_revision_id"] = supersedes

    return result


def _validate_facts(value: Any, kind: str) -> dict[str, Any]:
    """Validate facts dictionary based on kind."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RecordError("FACTS_TYPE", "facts must be object or null")

    # Common optional facts for all kinds
    result: dict[str, Any] = {}

    if "extraction_error" in value:
        e = value.get("extraction_error")
        if e is not None and not isinstance(e, str):
            raise RecordError("EXTRACTION_ERROR_TYPE", "extraction_error must be string or null")
        result["extraction_error"] = e

    if "source_notes" in value:
        result["source_notes"] = _validate_list_of_strings(value["source_notes"], "source_notes")

    if "official_number" in value:
        val = value["official_number"]
        if val is not None and not isinstance(val, str):
            raise RecordError("OFFICIAL_NUMBER_TYPE", "official_number must be string or null")
        result["official_number"] = val

    if "subject_tags" in value:
        result["subject_tags"] = _validate_list_of_strings(value["subject_tags"], "subject_tags")

    if "applicability_notes" in value:
        val = value["applicability_notes"]
        if val is not None and not isinstance(val, str):
            raise RecordError("APPLICABILITY_TYPE", "applicability_notes must be string or null")
        result["applicability_notes"] = val

    if "date_details" in value:
        result["date_details"] = _validate_date_details(value["date_details"])

    if "status_detail" in value:
        val = value["status_detail"]
        if val is not None and not isinstance(val, str):
            raise RecordError("STATUS_DETAIL_TYPE", "status_detail must be string or null")
        result["status_detail"] = val

    # Kind-specific facts
    if kind in ("statute", "bill"):
        _validate_statute_facts(value, result)
    elif kind == "case":
        _validate_case_facts(value, result)
    elif kind in ("court_rule", "agency_rule", "circuit_order", "judge_procedure", "clerk_notice"):
        _validate_procedure_facts(value, result)
    elif kind in ("roster", "assignment"):
        _validate_roster_facts(value, result)

    return result


def _validate_date_details(value: dict[str, Any]) -> dict[str, Any]:
    """Validate date_details object."""
    valid_keys = {
        "publication_date", "effective_date", "status_date",
        "action_date", "adoption_date", "applicability_date", "revision_date",
    }
    extra = set(value.keys()) - valid_keys
    if extra:
        raise RecordError("DATE_DETAILS_UNKNOWN", f"Unknown date_detail keys: {sorted(extra)}")
    result = {}
    for key in valid_keys:
        if key in value:
            val = value[key]
            result[key] = _validate_date_value(val)
    return result


def _validate_date_value(value: Any) -> dict[str, Any]:
    """Validate a DateValue object."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RecordError("DATE_VALUE_TYPE", "DateValue must be object")
    valid_keys = {"value", "precision", "source_text"}
    extra = set(value.keys()) - valid_keys
    if extra:
        raise RecordError("DATE_VALUE_UNKNOWN", f"Unknown DateValue keys: {sorted(extra)}")

    result: dict[str, Any] = {}
    val = value.get("value")
    if val is not None and not isinstance(val, str):
        raise RecordError("DATE_VALUE_STR", "DateValue.value must be string or null")
    result["value"] = val

    precision = value.get("precision")
    if precision not in VALID_PRECISIONS:
        raise RecordError("DATE_PRECISION", f"precision must be one of {VALID_PRECISIONS}")
    result["precision"] = precision

    source_text = value.get("source_text")
    if source_text is not None and not isinstance(source_text, str):
        raise RecordError("DATE_SOURCE_TYPE", "source_text must be string or null")
    result["source_text"] = source_text

    return result


def _validate_statute_facts(value: dict[str, Any], result: dict[str, Any]) -> None:
    """Validate statute/bill specific facts."""
    statute_year = value.get("statute_year")
    if statute_year is not None:
        if not isinstance(statute_year, int):
            raise RecordError("STATUTE_YEAR_TYPE", "statute_year must be integer or null")
        result["statute_year"] = statute_year

    session_year = value.get("session_year")
    if session_year is not None:
        if not isinstance(session_year, int):
            raise RecordError("SESSION_YEAR_TYPE", "session_year must be integer or null")
        result["session_year"] = session_year

    if "session_name" in value:
        val = value["session_name"]
        if val is not None and not isinstance(val, str):
            raise RecordError("SESSION_NAME_TYPE", "session_name must be string or null")
        result["session_name"] = val

    if "bill_number" in value:
        val = value["bill_number"]
        if val is not None and not isinstance(val, str):
            raise RecordError("BILL_NUMBER_TYPE", "bill_number must be string or null")
        result["bill_number"] = val

    if "bill_version" in value:
        val = value["bill_version"]
        if val is not None and not isinstance(val, str):
            raise RecordError("BILL_VERSION_TYPE", "bill_version must be string or null")
        result["bill_version"] = val

    legislative_stage = value.get("legislative_stage")
    if legislative_stage not in VALID_LEGISLATIVE_STAGES:
        if legislative_stage is not None:
            raise RecordError("LEGISLATIVE_STAGE", f"must be one of {VALID_LEGISLATIVE_STAGES}")
    if legislative_stage is not None:
        result["legislative_stage"] = legislative_stage

    if "amendment_ids" in value:
        result["amendment_ids"] = _validate_list_of_strings(value["amendment_ids"], "amendment_ids")

    if "chapter_law" in value:
        val = value["chapter_law"]
        if val is not None and not isinstance(val, str):
            raise RecordError("CHAPTER_LAW_TYPE", "chapter_law must be string or null")
        result["chapter_law"] = val

    if "affected_sections" in value:
        result["affected_sections"] = _validate_list_of_strings(value["affected_sections"], "affected_sections")

    if "legislative_events" in value:
        result["legislative_events"] = _validate_legislative_events(value["legislative_events"])


def _validate_legislative_events(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate a list of LegislativeEvent objects."""
    if not isinstance(value, list):
        raise RecordError("LEG_EVENTS_TYPE", "legislative_events must be list")
    result = []
    for i, evt in enumerate(value):
        if not isinstance(evt, dict):
            raise RecordError(f"LEG_EVT_{i}_TYPE", f"legislative_events[{i}] must be object")
        valid_keys = {"event_id", "stage", "action_date", "description", "effective_date", "applicability"}
        extra = set(evt.keys()) - valid_keys
        if extra:
            raise RecordError(f"LEG_EVT_{i}_UNKNOWN", f"Unknown keys: {sorted(extra)}")

        result.append({
            "event_id": _validate_nonempty_string(evt.get("event_id"), f"legislative_events[{i}].event_id"),
            "stage": evt.get("stage"),
            "action_date": _validate_date_value(evt.get("action_date")),
            "description": evt.get("description"),
            "effective_date": _validate_date_value(evt.get("effective_date")),
            "applicability": evt.get("applicability"),
        })
    return result


def _validate_case_facts(value: dict[str, Any], result: dict[str, Any]) -> None:
    """Validate case specific facts."""
    for field in ("case_name", "case_number", "court", "disposition", "author",
                  "reporter_citation", "review_status"):
        val = value.get(field)
        if val is not None and not isinstance(val, str):
            raise RecordError(f"CASE_{field}_TYPE", f"{field} must be string or null")
        if val is not None:
            result[field] = val

    district = value.get("district")
    if district is not None:
        if not isinstance(district, int):
            raise RecordError("CASE_DISTRICT_TYPE", "district must be integer 1-6 or null")
        if district < 1 or district > 6:
            raise RecordError("CASE_DISTRICT_RANGE", "district must be 1-6")
        result["district"] = district

    for list_field in ("panel", "concurrence", "dissent"):
        if list_field in value:
            result[list_field] = _validate_list_of_strings(value[list_field], list_field)

    en_banc = value.get("en_banc")
    if en_banc is not None and not isinstance(en_banc, bool):
        raise RecordError("CASE_EN_BANC", "en_banc must be boolean or null")
    if en_banc is not None:
        result["en_banc"] = en_banc

    for list_field in ("certified_questions", "certified_conflicts"):
        if list_field in value:
            result[list_field] = _validate_list_of_strings(value[list_field], list_field)

    opinion_type = value.get("opinion_type")
    if opinion_type not in VALID_OPINION_TYPES:
        if opinion_type is not None:
            raise RecordError("CASE_OPINION_TYPE", f"opinion_type must be one of {VALID_OPINION_TYPES}")
    if opinion_type is not None:
        result["opinion_type"] = opinion_type

    # Check court validity
    court = result.get("court")
    if court is not None and court not in VALID_COURTS:
        raise RecordError("CASE_COURT", f"court must be one of {VALID_COURTS}")


def _validate_procedure_facts(value: dict[str, Any], result: dict[str, Any]) -> None:
    """Validate court_rule/agency_rule/circuit_order/judge_procedure/clerk_notice facts."""
    for field in ("agency", "circuit_id", "division"):
        val = value.get(field)
        if val is not None and not isinstance(val, str):
            raise RecordError(f"PROC_{field}_TYPE", f"{field} must be string or null")
        if val is not None:
            result[field] = val

    for list_field in ("county_ids", "judge_ids"):
        if list_field in value:
            result[list_field] = _validate_list_of_strings(value[list_field], list_field)

    authority_type = value.get("authority_type")
    if authority_type not in VALID_AUTHORITIES:
        if authority_type is not None:
            raise RecordError("PROC_AUTHORITY", f"authority_type must be one of {VALID_AUTHORITIES}")
    if authority_type is not None:
        result["authority_type"] = authority_type


def _validate_roster_facts(value: dict[str, Any], result: dict[str, Any]) -> None:
    """Validate roster/assignment facts including judge_observations."""
    if "judge_observations" in value:
        result["judge_observations"] = _validate_observations(value["judge_observations"])


# ----- Validate functions exported at module level -----

def validate_record(value: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Validate a DocumentRecord.

    Performs structural/type/date/hash validation and returns a copy or raises
    RecordError(code, message). No registry-module import or hidden global registry.
    """
    if not isinstance(value, dict):
        raise RecordError("NOT_DICT", "value must be a dictionary")
    return _validate_record_top_level(value, mode=mode)


def validate_analysis(value: dict[str, Any]) -> dict[str, Any]:
    """Validate an AnalysisResult object."""
    if not isinstance(value, dict):
        raise RecordError("NOT_DICT", "value must be a dictionary")

    valid_keys = {
        "schema_version", "analysis_id", "revision_id", "profile_id",
        "status", "relevance", "summary", "irac", "practice_action",
        "claims", "warnings",
    }
    extra = set(value.keys()) - valid_keys
    if extra:
        raise RecordError("UNKNOWN_KEY", f"Unknown AnalysisResult keys: {sorted(extra)}")

    result: dict[str, Any] = {}

    sv = value.get("schema_version")
    if not isinstance(sv, int) or isinstance(sv, bool):
        raise RecordError("ANALYSIS_SCHEMA_TYPE", "schema_version must be integer")
    if sv != 1:
        raise RecordError("ANALYSIS_SCHEMA_VALUE", "schema_version must be 1")
    result["schema_version"] = sv

    aid = value.get("analysis_id")
    if not isinstance(aid, str) or not _ANA_ID_RE.match(aid):
        raise RecordError("ANALYSIS_ID_FORMAT", "analysis_id must match '^ana_[0-9a-f]{24}$'")
    result["analysis_id"] = aid

    rid = value.get("revision_id")
    if not isinstance(rid, str) or not _REV_ID_RE.match(rid):
        raise RecordError("REV_ID_FORMAT", "revision_id must match '^rev_[0-9a-f]{24}$'")
    result["revision_id"] = rid

    pid = value.get("profile_id")
    if not isinstance(pid, str):
        raise RecordError("PROFILE_TYPE", "profile_id must be string")
    result["profile_id"] = pid

    status = value.get("status")
    if status not in VALID_ANALYSIS_STATUSES:
        raise RecordError("ANALYSIS_STATUS", f"status must be one of {VALID_ANALYSIS_STATUSES}")
    result["status"] = status

    rel = value.get("relevance")
    if not isinstance(rel, bool):
        raise RecordError("REL_TYPE", "relevance must be boolean")
    result["relevance"] = rel

    summary = value.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise RecordError("SUMMARY_TYPE", "summary must be string or null")
    result["summary"] = summary

    irac = value.get("irac")
    if irac is not None:
        if not isinstance(irac, dict):
            raise RecordError("IRAC_TYPE", "irac must be object or null")
        result["irac"] = irac
    else:
        result["irac"] = None

    pa = value.get("practice_action")
    if pa is not None and not isinstance(pa, str):
        raise RecordError("PA_TYPE", "practice_action must be string or null")
    result["practice_action"] = pa

    claims = value.get("claims")
    if claims is not None:
        result["claims"] = _validate_claims(claims)
    else:
        result["claims"] = []

    warnings = value.get("warnings")
    if warnings is not None:
        result["warnings"] = _validate_list_of_strings(warnings, "warnings")
    else:
        result["warnings"] = []

    return result


def _validate_claims(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate a list of Claim objects."""
    if not isinstance(value, list):
        raise RecordError("CLAIMS_TYPE", "claims must be list")
    result = []
    for i, claim in enumerate(value):
        if not isinstance(claim, dict):
            raise RecordError(f"CLAIM_{i}_TYPE", f"claims[{i}] must be object")
        valid_keys = {"claim_id", "text", "evidence_revision_id", "pinpoint_index", "characterization"}
        extra = set(claim.keys()) - valid_keys
        if extra:
            raise RecordError(f"CLAIM_{i}_UNKNOWN", f"Unknown keys: {sorted(extra)}")

        cid = claim.get("claim_id")
        if not isinstance(cid, str):
            raise RecordError(f"CLAIM_{i}_ID", "claim_id must be string")

        txt = claim.get("text")
        if not isinstance(txt, str):
            raise RecordError(f"CLAIM_{i}_TEXT", "text must be string")

        evid = claim.get("evidence_revision_id")
        if not isinstance(evid, str) or not _REV_ID_RE.match(evid):
            raise RecordError(f"CLAIM_{i}_EVID", "evidence_revision_id must match '^rev_[0-9a-f]{24}$'")

        pidx = claim.get("pinpoint_index")
        if not isinstance(pidx, int) or pidx < 0:
            raise RecordError(f"CLAIM_{i}_PIN", "pinpoint_index must be integer >= 0")

        char = claim.get("characterization")
        if char not in VALID_CHARACTERIZATIONS:
            raise RecordError(f"CLAIM_{i}_CHAR", f"characterization must be one of {VALID_CHARACTERIZATIONS}")

        result.append(claim)
    return result


def validate_registry_references(record: dict[str, Any], *, source_ids: set[str], scope_ids: set[str]) -> None:
    """Separately check membership against injected, validated registry IDs.

    Registry-aware callers must perform both checks before acquisition commit.
    """
    source_id = record.get("source_id")
    if source_id not in source_ids:
        raise RecordError("SOURCE_NOT_IN_REGISTRY", f"source_id '{source_id}' not in registry")

    scope_ids_val = record.get("scope_ids")
    if isinstance(scope_ids_val, list):
        for sid in scope_ids_val:
            if sid not in scope_ids:
                raise RecordError("SCOPE_NOT_IN_REGISTRY", f"scope_id '{sid}' not in registry")


def is_operative(record: dict[str, Any], *, as_of: str) -> bool:
    """Determine if a record is operative as of the given date.

    operative with no future effective date, or adopted with a known
    day-precision effective date <= as_of; never proposed/unknown/withdrawn/superseded.
    A future dated operative label is withheld and flagged as inconsistent.
    Partial/unknown date evidence cannot establish an adopted record's operative date.
    """
    legal_status = record.get("legal_status")
    if legal_status in ("proposed", "unknown", "withdrawn", "superseded"):
        return False

    effective_date = record.get("effective_date")
    publication_date = record.get("publication_date")

    # If operative, no future effective date
    if legal_status == "operative":
        if effective_date is not None:
            # Check effective date <= as_of
            try:
                eff_dt = datetime.date.fromisoformat(effective_date)
                as_dt = datetime.date.fromisoformat(as_of)
                if eff_dt > as_dt:
                    return False
            except ValueError:
                return False
        return True

    # Adopted with unknown effective date is uncertain
    if legal_status == "adopted" and effective_date is None:
        return False

    # Adopted with a known day-precision effective date
    if legal_status == "adopted" and effective_date is not None:
        try:
            eff_dt = datetime.date.fromisoformat(effective_date)
            as_dt = datetime.date.fromisoformat(as_of)
            if eff_dt <= as_dt:
                return True
        except ValueError:
            return False

    return False


# ----- Canonicalization functions (used by C03) -----

def canonical_json(value: Any) -> bytes:
    """Canonical JSON serialization: UTF-8 json.dumps with sort_keys, compact separators."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def normalize_text(text: str) -> str:
    """Normalize text: Unicode NFC, CRLF/CR to LF, trim line-end spaces,
    collapse horizontal whitespace within lines, trim leading/trailing blank lines."""
    import unicodedata
    text = unicodedata.normalize("NFC", text)
    # CRLF/CR to LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse horizontal whitespace within lines
    lines = text.split("\n")
    collapsed = []
    for line in lines:
        # Collapse horizontal whitespace (tabs, multiple spaces) but preserve legal footnotes/dates
        import re
        collapsed.append(re.sub(r"[ \t]+", " ", line))
    text = "\n".join(collapsed)
    # Trim leading/trailing blank lines
    text = text.strip("\n")
    return text


# Stub — document_id, semantic_facts, semantic_payload, content_sha256,
# revision_id, and analysis_id are imported by C03 identity.py.


def _compute_document_id(source_id: str, document_key: str) -> str:
    """Compute a deterministic document_id."""
    payload = canonical_json(["document-v1", source_id, document_key])
    return "doc_" + hashlib.sha256(payload).hexdigest()[:24]


def _compute_content_sha256(record: dict[str, Any]) -> str:
    """Compute the content_sha256 from the semantic payload."""
    payload = _semantic_payload(record)
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _semantic_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Build the semantic payload for SHA computation.

    Exactly normalized title, normalized body_text, kind, sorted scope_ids,
    publication_date, effective_date, status_date, legal_status, and
    semantic_facts(facts). Exclude supersedes_revision_id, mode/synthetic,
    URLs, observation/retrieval times, pinpoints and hashes.
    """
    facts = record.get("facts", {}) or {}
    semantic_facts_val = semantic_facts(facts)
    return {
        "title": normalize_text(record.get("title", "")),
        "body_text": normalize_text(record.get("body_text", "") or ""),
        "kind": record.get("kind"),
        "scope_ids": record.get("scope_ids"),
        "publication_date": record.get("publication_date"),
        "effective_date": record.get("effective_date"),
        "status_date": record.get("status_date"),
        "legal_status": record.get("legal_status"),
        "facts": semantic_facts_val,
    }


def semantic_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Remove reserved observational keys from ALL nested dicts and canonicalize.

    Reserved keys (observed_at, identity_review, official_url, etc.) are
    stripped from every dict at every nesting level, including inside
    judge_observations lists.
    """
    reserved = frozenset({
        "source_notes", "extraction_error", "observed_at", "checked_at",
        "retrieved_at", "official_url", "canonical_url", "retrieved_url",
        "evidence_paths", "local_reference", "exact_sha256", "identity_review",
    })

    def _strip_reserved_from(obj: Any) -> Any:
        """Strip reserved keys from all nested dicts and handle lists."""
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            for k, v in obj.items():
                if k in reserved:
                    continue
                result[k] = _strip_reserved_from(v)
            _remove_nulls(result)
            return result
        elif isinstance(obj, list):
            return [_strip_reserved_from(item) for item in obj]
        else:
            return obj

    result: dict[str, Any] = {}
    for key, val in facts.items():
        if key in reserved:
            continue
        if isinstance(val, dict):
            result[key] = _strip_reserved_from(val)
        elif isinstance(val, list):
            stripped = [_strip_reserved_from(item) for item in val]
            result[key] = _deduplicate_sorted_list(stripped)
        else:
            result[key] = val
    return result


def _deduplicate_sorted_list(items: list[Any]) -> list[Any]:
    """Deduplicate a list by canonical JSON and sort by canonical JSON bytes."""
    seen: dict[str, Any] = {}
    for item in items:
        cj = canonical_json(item).decode("utf-8")
        if cj not in seen:
            seen[cj] = item
    return sorted(seen.values(), key=lambda x: canonical_json(x))


def _remove_nulls(obj: Any) -> None:
    """Recursively remove null optional object members."""
    if isinstance(obj, dict):
        null_keys = [k for k, v in obj.items() if v is None]
        for k in null_keys:
            del obj[k]
        for v in obj.values():
            _remove_nulls(v)
    elif isinstance(obj, list):
        for v in obj:
            _remove_nulls(v)


def _compute_revision_id(document_id: str, content_sha256: str) -> str:
    """Compute a revision_id."""
    payload = canonical_json(["revision-v1", document_id, content_sha256])
    return "rev_" + hashlib.sha256(payload).hexdigest()[:24]


def _compute_analysis_id(revision_id: str, profile_id: str) -> str:
    """Compute an analysis_id."""
    payload = canonical_json(["analysis-v1", revision_id, profile_id])
    return "ana_" + hashlib.sha256(payload).hexdigest()[:24]


# Record JSON Schema export (stub — full schema generated from spec in C02 docs)
def record_json_schema() -> dict[str, Any]:
    """Export the frozen DocumentRecord JSON Schema."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "DocumentRecord",
        "type": "object",
        "required": [
            "schema_version", "mode", "synthetic", "source_id", "document_key",
            "document_id", "revision_id", "kind", "scope_ids", "canonical_url",
            "title", "body_text", "publication_date", "effective_date",
            "status_date", "legal_status", "observed_at", "exact_sha256",
            "content_sha256", "pinpoints", "facts", "supersedes_revision_id",
        ],
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "mode": {"type": "string", "enum": ["fixture", "production"]},
            "synthetic": {"type": "boolean"},
            "source_id": {"type": "string", "minLength": 1},
            "document_key": {"type": "string", "minLength": 1},
            "document_id": {"type": "string", "pattern": "^doc_[0-9a-f]{24}$"},
            "revision_id": {"type": "string", "pattern": "^rev_[0-9a-f]{24}$"},
            "kind": {"type": "string", "enum": sorted(VALID_KINDS)},
            "scope_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "canonical_url": {"type": ["string", "null"]},
            "title": {"type": "string", "minLength": 1},
            "body_text": {"type": "string"},
            "publication_date": {"type": ["string", "null"], "format": "date"},
            "effective_date": {"type": ["string", "null"], "format": "date"},
            "status_date": {"type": ["string", "null"], "format": "date"},
            "legal_status": {"type": "string", "enum": sorted(VALID_STATUSES)},
            "observed_at": {"type": "string", "pattern": ".*Z$"},
            "exact_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "pinpoints": {"type": "array"},
            "facts": {"type": "object"},
            "supersedes_revision_id": {"type": ["string", "null"]},
        },
    }
