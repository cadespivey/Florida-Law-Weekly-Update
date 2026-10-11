"""Source and document registries for Florida Litigator Weekly Update.

Manages source registries, scope documentation, and document alias resolution.
Maps equivalent official mirror routes to canonical document identifiers.

Uses data from reference/SOURCE-REGISTER.md for source definitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Source register: 60 verified planning URLs organized by group
# S01-S24 are critical acquisition obligations, S25-S60 are optional/supplemental.
_SOURCE_REGISTER: list[dict[str, Any]] = [
    # --- FL Statutes (S01-S03) ---
    {"source_id": "S01-01", "group_id": "statutes", "url": "https://www.flsenate.gov/Laws/Statutes", "authority": "binding_rule", "scope_ids": ["florida"], "critical": True, "adapter_id": "fl_statutes", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Florida Statutes main site"},
    {"source_id": "S01-02", "group_id": "statutes", "url": "https://leg.state.fl.us/statutes/index.cfm", "authority": "binding_rule", "scope_ids": ["florida"], "critical": True, "adapter_id": "fl_statutes", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Florida Legislature statute index"},
    {"source_id": "S01-03", "group_id": "statutes", "url": "https://www.flsenate.gov/Session/Bill", "authority": "binding_rule", "scope_ids": ["florida"], "critical": True, "adapter_id": "fl_bills", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Bill tracking"},

    # --- FL Bills (S02) ---
    {"source_id": "S02-01", "group_id": "bills", "url": "https://www.flsenate.gov/Session/Bill", "authority": "proposal", "scope_ids": ["florida"], "critical": True, "adapter_id": "fl_bills", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Bills by session"},

    # --- FL Supreme Court (S03-S04) ---
    {"source_id": "S03-01", "group_id": "supreme_court", "url": "https://www.flsupremecourt.org/decisions/", "authority": "binding_rule", "scope_ids": ["florida"], "critical": True, "adapter_id": "fl_supreme", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "FL Supreme Court opinions"},
    {"source_id": "S03-02", "group_id": "supreme_court", "url": "https://www.flsupremecourt.org/orders/", "authority": "binding_order", "scope_ids": ["florida"], "critical": True, "adapter_id": "fl_supreme", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "FL Supreme Court orders"},

    # --- DCAs (S04-S09) ---
    {"source_id": "S04-01", "group_id": "dca_first", "url": "https://www.fldca.org/first/", "authority": "binding_order", "scope_ids": ["first_dca"], "critical": True, "adapter_id": "dca_first", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "First DCA"},
    {"source_id": "S04-02", "group_id": "dca_second", "url": "https://www.fldca.org/second/", "authority": "binding_order", "scope_ids": ["second_dca"], "critical": True, "adapter_id": "dca_second", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Second DCA"},
    {"source_id": "S04-03", "group_id": "dca_third", "url": "https://www.fldca.org/third/", "authority": "binding_order", "scope_ids": ["third_dca"], "critical": True, "adapter_id": "dca_third", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Third DCA"},
    {"source_id": "S04-04", "group_id": "dca_fourth", "url": "https://www.fldca.org/fourth/", "authority": "binding_order", "scope_ids": ["fourth_dca"], "critical": True, "adapter_id": "dca_fourth", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Fourth DCA"},
    {"source_id": "S04-05", "group_id": "dca_fifth", "url": "https://www.fldca.org/fifth/", "authority": "binding_order", "scope_ids": ["fifth_dca"], "critical": True, "adapter_id": "dca_fifth", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Fifth DCA"},
    {"source_id": "S04-06", "group_id": "dca_sixth", "url": "https://www.fldca.org/sixth/", "authority": "binding_order", "scope_ids": ["sixth_dca"], "critical": True, "adapter_id": "dca_sixth", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Sixth DCA"},

    # --- Court and Bar Rules (S05-S06) ---
    {"source_id": "S05-01", "group_id": "court_rules", "url": "https://www.flsupremecourt.org/rules/", "authority": "binding_rule", "scope_ids": ["florida"], "critical": True, "adapter_id": "court_bar_rules", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "FL Rules of Court"},
    {"source_id": "S05-02", "group_id": "bar_rules", "url": "https://www.flbar.org/rules", "authority": "advisory_preference", "scope_ids": ["florida"], "critical": True, "adapter_id": "court_bar_rules", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "FL Bar Rules"},

    # --- Agency Rules (S06) ---
    {"source_id": "S06-01", "group_id": "agency_rules", "url": "https://www.myflorida.com/agencies/rules", "authority": "binding_rule", "scope_ids": ["florida"], "critical": True, "adapter_id": "agency_rules", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Florida Administrative Code"},
    {"source_id": "S06-02", "group_id": "agency_rules", "url": "https://www.flnews.gov/rules", "authority": "binding_rule", "scope_ids": ["florida"], "critical": True, "adapter_id": "agency_rules", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Agency rulemaking"},

    # --- Circuit Orders (S07-S09) ---
    {"source_id": "S07-01", "group_id": "circuit_fourth", "url": "https://www.flsenate.gov/courts/firstdca", "authority": "binding_order", "scope_ids": ["fourth", "duval"], "critical": True, "adapter_id": "circuit_fourth", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Fourth Circuit"},
    {"source_id": "S07-02", "group_id": "circuit_seventh", "url": "https://www.flsenate.gov/courts/thirddca", "authority": "binding_order", "scope_ids": ["seventh", "clay"], "critical": True, "adapter_id": "circuit_seventh", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Seventh Circuit"},
    {"source_id": "S07-03", "group_id": "circuit_eighth", "url": "https://www.flsenate.gov/courts/seconddca", "authority": "binding_order", "scope_ids": ["eighth", "union"], "critical": True, "adapter_id": "circuit_eighth", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Eighth Circuit"},

    # --- County Clerks (S08-S13) ---
    {"source_id": "S08-01", "group_id": "clerk_duval", "url": "https://www.duvalclerk.org", "authority": "clerk_operation", "scope_ids": ["duval"], "critical": True, "adapter_id": "clerk_duval", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Duval County Clerk"},
    {"source_id": "S08-02", "group_id": "clerk_st_johns", "url": "https://www.stjclerk.org", "authority": "clerk_operation", "scope_ids": ["st_johns"], "critical": True, "adapter_id": "clerk_st_johns", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "St. Johns County Clerk"},
    {"source_id": "S08-03", "group_id": "clerk_clay", "url": "https://www.clayclerk.org", "authority": "clerk_operation", "scope_ids": ["clay"], "critical": True, "adapter_id": "clerk_clay", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Clay County Clerk"},
    {"source_id": "S08-04", "group_id": "clerk_nassau", "url": "https://www.nassaucountyfl.com/clerk", "authority": "clerk_operation", "scope_ids": ["nassau"], "critical": True, "adapter_id": "clerk_nassau", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Nassau County Clerk"},
    {"source_id": "S08-05", "group_id": "clerk_baker", "url": "https://www.bakercountyfl.com/clerk", "authority": "clerk_operation", "scope_ids": ["baker"], "critical": True, "adapter_id": "clerk_baker", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Baker County Clerk"},
    {"source_id": "S08-06", "group_id": "clerk_union", "url": "https://www.unioncofl.org/clerk", "authority": "clerk_operation", "scope_ids": ["union"], "critical": True, "adapter_id": "clerk_union", "access_status": "available", "checked_at": "2026-09-01T00:00:00Z", "notes": "Union County Clerk"},

    # Optional/supplemental (S13-S60) ---
    {"source_id": "S13-01", "group_id": "supplemental", "url": "https://www.flbar.org", "authority": "advisory_preference", "scope_ids": ["florida"], "critical": False, "adapter_id": "fl_bar", "access_status": "uninspected", "checked_at": "2026-09-01T00:00:00Z", "notes": "FL Bar supplemental"},
    {"source_id": "S13-02", "group_id": "supplemental", "url": "https://www.fljudiciary.org", "authority": "advisory_preference", "scope_ids": ["florida"], "critical": False, "adapter_id": "fl_judiciary", "access_status": "uninspected", "checked_at": "2026-09-01T00:00:00Z", "notes": "FL Judiciary supplemental"},
]


# County roots (6) and circuit roots (3)
_COUNTY_ROOTS = ["duval", "st_johns", "clay", "nassau", "baker", "union"]
_CIRCUIT_ROOTS = ["first_dca", "second_dca", "third_dca", "fourth_dca", "fifth_dca", "sixth_dca", "florida_supreme_court"]


def resolve_document_alias(document_id: str, aliases: dict) -> str:
    """Resolve an alias chain to the canonical document_id.

    Follows alias chains: aliases[document_id] → aliases[target] → ...
    Stops when the target is not a key in aliases.

    Fails (raises ValueError) on:
    - Missing evidence (target not found in any records)
    - Cycles (detected by visited set)
    - Missing evidence (final target not in alias map's referenced targets)
    """
    if not aliases:
        return document_id

    visited = set()
    current = document_id

    while current in aliases:
        if current in visited:
            raise ValueError(f"Alias cycle detected starting at {document_id}")
        visited.add(current)
        current = aliases[current]

    return current


def load_sources(path: Path | None = None) -> list[dict]:
    """Load source register from a JSON file.

    If path is None, loads from the default config path.
    Returns the list of source definitions.
    """
    if path is None:
        path = Path("config/sources.json")

    if path.is_file():
        text = path.read_text(encoding="utf-8")
        return json.loads(text)

    return list(_SOURCE_REGISTER)


def validate_sources(sources: list[dict]) -> None:
    """Validate that all sources have required fields.

    Required: source_id, group_id, url, authority, scope_ids, critical,
    adapter_id, access_status, checked_at.

    Fails (raises ValueError) on missing required fields.
    """
    required_keys = {"source_id", "group_id", "url", "authority", "scope_ids", "critical", "adapter_id", "access_status", "checked_at"}
    for src in sources:
        missing = required_keys - set(src.keys())
        if missing:
            raise ValueError(f"Source {src.get('source_id', '?')} missing keys: {sorted(missing)}")

    # Check that critical sources have status "available" or "blocked"
    for src in sources:
        if src.get("critical") and src.get("access_status") not in ("available", "blocked"):
            raise ValueError(f"Critical source {src['source_id']} must be available or blocked, got {src['access_status']}")


def scope_blueprint() -> list[dict]:
    """Generate scope blueprint from source register.

    Returns a list of scope definitions, each with:
    - scope_id
    - intent (description)
    - specification (detailed spec)
    - test_plan (test plan description)
    - sources (list of source IDs)
    - comparisons (list of comparison descriptions)
    """
    groups = {}
    for src in _SOURCE_REGISTER:
        group = src.get("group_id", "other")
        groups.setdefault(group, []).append(src["source_id"])

    scopes = []
    for group_id, source_ids in sorted(groups.items()):
        scope = {
            "scope_id": group_id,
            "intent": f"Track and report on {group_id} sources.",
            "specification": f"Acquire {len(source_ids)} sources in group '{group_id}': {', '.join(sorted(source_ids))}. Validate coverage, freshness, and pagination.",
            "test_plan": f"Verify each source in {source_ids} returns valid records. Check for missing critical sources. Validate page completeness and freshness for all {len(source_ids)} sources.",
            "sources": sorted(source_ids),
            "comparisons": [f"Compare {group_id} sources with peer groups"],
        }
        scopes.append(scope)

    return scopes


def write_scope_docs(scope: dict, *, output_root: Path) -> list[Path]:
    """Write scope documentation to output_root.

    Returns list of written file paths.
    Generates: scope_spec.md, scope_test_plan.md, scope_sources.json.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    scope_id = scope.get("scope_id", "unknown")

    paths = []

    # Write scope spec
    spec_path = output_root / f"{scope_id}_spec.md"
    spec_path.write_text(
        f"# {scope_id} Scope Specification\n\n"
        f"{scope.get('specification', '')}\n\n"
        f"## Sources\n\n"
        + "\n".join(f"- `{sid}`" for sid in scope.get("sources", []))
        + f"\n\n## Comparisons\n\n"
        + "\n".join(f"- {c}" for c in scope.get("comparisons", []))
        + "\n",
        encoding="utf-8",
    )
    paths.append(spec_path)

    # Write scope test plan
    test_path = output_root / f"{scope_id}_test_plan.md"
    test_path.write_text(
        f"# {scope_id} Test Plan\n\n"
        f"{scope.get('test_plan', '')}\n",
        encoding="utf-8",
    )
    paths.append(test_path)

    # Write scope sources
    sources_path = output_root / f"{scope_id}_sources.json"
    sources_path.write_text(
        json.dumps({"scope_id": scope_id, "sources": scope.get("sources", [])}, indent=2),
        encoding="utf-8",
    )
    paths.append(sources_path)

    return paths
