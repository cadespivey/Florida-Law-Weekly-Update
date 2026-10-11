"""Deterministic document and revision identity for Florida Litigator Weekly Update.

Computes stable IDs from document inputs. No randomness or Python hash().
Preserves source-declared substantive status/date/assignment changes.
Deterministically sorts set-valued lists while retaining genuinely ordered
opinion text and pinpoints.

Does not turn a changed fetch timestamp, reordered roster, URL redirect,
or predecessor bookkeeping into a legal change.

All functions are pure and import from records.py for canonicalization.
"""

from __future__ import annotations

import hashlib
from typing import Any

from flwu.records import (
    RecordError,
    canonical_json,
    normalize_text,
    semantic_facts,
)


def document_id(source_id: str, document_key: str) -> str:
    """Compute a deterministic document_id.

    ``"doc_" + sha256(canonical_json(["document-v1", source_id,
    document_key])).hexdigest()[:24]``.

    Preserve identifier punctuation/case unless that source's reviewed
    identity rule explicitly normalizes it. Never key by title, current
    judge assignment, a name alone, or a retrieval time.

    Stored hash-prefix collisions with different complete inputs are errors,
    never merges.
    """
    payload = canonical_json(["document-v1", source_id, document_key])
    return "doc_" + hashlib.sha256(payload).hexdigest()[:24]


def semantic_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Build the semantic payload for SHA computation.

    Exactly normalized title, normalized body_text, kind, sorted scope_ids,
    publication_date, effective_date, status_date, legal_status, and
    semantic_facts(facts).

    Excludes supersedes_revision_id, mode/synthetic, URLs, observation/
    retrieval times, pinpoints, and hashes.

    A changed legal status with identical bytes is a new semantic revision.
    A later roster observation timestamp, reordered fact list, changed source
    note, or newly linked predecessor alone is not.
    """
    facts = record.get("facts") or {}
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


def revision_id(document_id: str, content_sha256: str) -> str:
    """Compute a revision_id.

    ``"rev_" + sha256(canonical_json(["revision-v1", document_id,
    content_sha256])).hexdigest()[:24]``.
    """
    payload = canonical_json(["revision-v1", document_id, content_sha256])
    return "rev_" + hashlib.sha256(payload).hexdigest()[:24]


def analysis_id(revision_id: str, profile_id: str) -> str:
    """Compute an analysis_id.

    ``"ana_" + sha256(canonical_json(["analysis-v1", revision_id,
    profile_id])).hexdigest()[:24]``.

    Profile ID hashes the actual model identifier/revision, prompt/schema/
    policy versions and relevant analysis settings, not a clock. A model
    alias alone is insufficient when its underlying model changes.

    New profiles enqueue eligible existing revisions. Run/attempt IDs may
    be unique per attempt; never use them as document/revision identity.

    Never use Python hash().
    """
    payload = canonical_json(["analysis-v1", revision_id, profile_id])
    return "ana_" + hashlib.sha256(payload).hexdigest()[:24]


def stamp_ids(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the record with computed document_id, content_sha256, and revision_id.

    This function computes the content_sha256 from the semantic payload,
    then computes the revision_id from the document_id and content_sha256.

    Returns a new dictionary; never mutates the input.
    """
    import copy

    result = copy.deepcopy(record)

    # Compute document_id
    source_id = result.get("source_id", "")
    document_key = result.get("document_key", "")
    result["document_id"] = document_id(source_id, document_key)

    # Compute content_sha256 from semantic payload
    payload = semantic_payload(result)
    sha_bytes = hashlib.sha256(canonical_json(payload))
    result["content_sha256"] = sha_bytes.hexdigest()

    # Compute revision_id
    result["revision_id"] = revision_id(
        result["document_id"], result["content_sha256"]
    )

    return result


# Re-export canonical_json and normalize_text for convenience
__all__ = [
    "document_id",
    "semantic_payload",
    "revision_id",
    "analysis_id",
    "stamp_ids",
    "canonical_json",
    "normalize_text",
]
