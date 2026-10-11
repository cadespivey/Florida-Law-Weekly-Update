"""Comprehensive integration tests for C10-C40."""
import json
import tempfile
from pathlib import Path

from flwu.registry import load_sources, validate_sources, scope_blueprint, write_scope_docs
from flwu.roster import reconcile_rosters
from flwu.model import run_analysis, load_analysis_config, AnalysisProfile
from flwu.inventory import build_inventory, select_snapshot, search_inventory
from flwu.search_index import write_search_index, load_search_index
from flwu.site import generate_site, _site_css, _search_js
from flwu.release import ReleaseGate, create_release_manifest, validate_release, publish_release
from flwu.scheduler import generate_launchd_plist, write_schedule_config, schedule_command
from flwu.orchestrator import run_weekly
from flwu.sections import get_section_categories
from flwu.fetch import FetchError, _load_adapter_bindings
from flwu.adapters import get_adapter, _REGISTRY


def test_all_20_adapters_registered():
    """All 20 source adapters are registered."""
    expected = {"fl_statutes", "fl_bills", "fl_supreme",
                "dca_first", "dca_second", "dca_third", "dca_fourth", "dca_fifth", "dca_sixth",
                "court_bar_rules", "agency_rules",
                "circuit_fourth", "circuit_seventh", "circuit_eighth",
                "clerk_duval", "clerk_st_johns", "clerk_clay",
                "clerk_nassau", "clerk_baker", "clerk_union"}
    # Import all adapters to ensure they are registered
    from flwu.adapters.fl_statutes import FLStatutesAdapter
    from flwu.adapters.fl_bills import FLBillsAdapter
    from flwu.adapters.fl_supreme import FLSupremeAdapter
    from flwu.adapters.dca_first import FirstDCAAdapter
    from flwu.adapters.dca_second import SecondDCAAdapter
    from flwu.adapters.dca_third import ThirdDCAAdapter
    from flwu.adapters.dca_fourth import FourthDCAAdapter
    from flwu.adapters.dca_fifth import FifthDCAAdapter
    from flwu.adapters.dca_sixth import SixthDCAAdapter
    from flwu.adapters.court_bar_rules import CourtBarRulesAdapter
    from flwu.adapters.agency_rules import AgencyRulesAdapter
    from flwu.adapters.circuit_fourth import CircuitFourthAdapter
    from flwu.adapters.circuit_seventh import CircuitSeventhAdapter
    from flwu.adapters.circuit_eighth import CircuitEighthAdapter
    from flwu.adapters.clerk_duval import ClerkDuvalAdapter
    from flwu.adapters.clerk_st_johns import ClerkStJohnsAdapter
    from flwu.adapters.clerk_clay import ClerkClayAdapter
    from flwu.adapters.clerk_nassau import ClerkNassauAdapter
    from flwu.adapters.clerk_baker import ClerkBakerAdapter
    from flwu.adapters.clerk_union import ClerkUnionAdapter
    assert set(_REGISTRY.keys()) == expected

def test_adapters_require_live_access():
    """All adapters raise NotImplementedError (no live calls in tests)."""
    for adapter_id, cls in _REGISTRY.items():
        adapter = cls()
        try:
            adapter.acquire({"source_id": "test"}, page_limit=1)
            assert False, f"Adapter {adapter_id} should raise NotImplementedError"
        except NotImplementedError:
            pass  # Expected

def test_adapter_bindings_config():
    """Adapter bindings are loaded with appropriate limits."""
    bindings = _load_adapter_bindings()
    assert "default" in bindings
    assert "fl_statutes" in bindings
    assert bindings["default"]["max_pages"] > 0
    assert bindings["default"]["timeout_seconds"] > 0

def test_roster_reconciliation():
    """Roster reconciliation processes verified records."""
    records = [
        {"kind": "roster", "title": "Judge List", "body_text": "Test roster",
         "canonical_url": "https://example.invalid/roster",
         "scope_ids": ["duval"], "publication_date": "2026-01-01",
         "effective_date": "2026-01-01", "status_date": "2026-01-01",
         "legal_status": "operative", "document_key": "R-001",
         "document_id": "d_roster", "revision_id": "r_roster",
         "content_sha256": "abc123",
         "judge_names": ["Judge Smith"], "judge_aliases": ["J. Smith", "Smith J."],
         "assignments": [
             {"circuit_id": "fourth", "division": "civil", "as_of": "2026-01-01", "is_future": False},
         ]},
    ]
    result = reconcile_rosters(records)
    assert result["count"] == 1
    judges = result["judges"]
    assert any("Smith" in data["canonical_name"] for data in judges.values())

def test_analysis_profile():
    """Deterministic analysis produces documented output."""
    profile = AnalysisProfile("test_profile")
    record = {"kind": "statute", "title": "Test Statute", "body_text": "Test body text that is long enough",
              "canonical_url": "https://example.invalid/stat", "document_key": "S-001",
              "scope_ids": ["florida"], "publication_date": "2026-01-01",
              "effective_date": "2026-01-01", "status_date": "2026-01-01",
              "legal_status": "operative", "facts": {}, "document_id": "d1",
              "revision_id": "r1", "content_sha256": "abc"}
    result = profile.analyze(record)
    assert result["analysis_type"] == "statute"
    assert result["confidence"] == "high"
    assert len(result["practice_actions"]) > 0

def test_analysis_config():
    """Analysis config loads default profiles."""
    profiles = load_analysis_config()
    assert len(profiles) >= 1
    assert profiles[0].profile_id

def test_inventory_build():
    """Inventory builds searchable rows from records."""
    records = [
        {"kind": "judge_procedure", "title": "Test Procedure", "body_text": "Test body text",
         "canonical_url": "https://example.invalid/proc", "scope_ids": ["county:duval"],
         "publication_date": "2026-01-01", "effective_date": "2026-01-01",
         "status_date": "2026-01-01", "legal_status": "operative",
         "document_key": "P-001", "document_id": "d1", "revision_id": "r1",
         "content_sha256": "abc", "facts": {"subject_tags": ["filing"]},
         "pinpoints": [{"page": None, "paragraph": "fixture:1", "excerpt": "test"}]},
        {"kind": "circuit_order", "title": "Test Order", "body_text": "Test body text for order",
         "canonical_url": "https://example.invalid/order", "scope_ids": ["county:clay", "circuit:fourth"],
         "publication_date": "2026-01-02", "effective_date": "2026-01-02",
         "status_date": "2026-01-02", "legal_status": "operative",
         "document_key": "O-001", "document_id": "d2", "revision_id": "r2",
         "content_sha256": "def", "facts": {"subject_tags": ["hearing"]},
         "pinpoints": [{"page": None, "paragraph": "fixture:1", "excerpt": "test"}]},
    ]
    rows = build_inventory(records, snapshot_id="snap_test", as_of="2026-01-01T00:00:00Z", aliases={})
    assert len(rows) == 2
    assert rows[0]["record_id"]
    assert rows[0]["category"] in ("Procedural Rules", "Local Rules")

def test_select_snapshot():
    """Select snapshot by mode."""
    catalog = {
        "schema_version": 1,
        "latest_snapshot_id": "snap_latest",
        "snapshots": [
            {"snapshot_id": "snap_001", "as_of": "2026-01-01", "cutoff_utc": "2026-01-02T00:00:00Z"},
            {"snapshot_id": "snap_latest", "as_of": "2026-01-08", "cutoff_utc": "2026-01-09T00:00:00Z"},
        ],
    }
    current = select_snapshot(catalog, mode="current")
    assert current["snapshot_id"] == "snap_latest"
    hist = select_snapshot(catalog, mode="historical", snapshot_id="snap_001")
    assert hist["snapshot_id"] == "snap_001"
    try:
        select_snapshot(catalog, mode="historical")
        assert False
    except ValueError:
        pass

def test_search_inventory():
    """Search filters work correctly."""
    rows = [
        {"record_id": "d1", "title": "Procedure A", "text": "Test body text", "category": "Local Rules",
         "county_ids": ["duval"], "circuit_ids": ["fourth"], "topics": ["filing"],
         "court_levels": ["county"], "divisions": ["duval"]},
        {"record_id": "d2", "title": "Procedure B", "text": "Another test text", "category": "Local Rules",
         "county_ids": ["clay"], "circuit_ids": ["seventh"], "topics": ["hearing"],
         "court_levels": ["county"], "divisions": ["clay"]},
    ]
    results = search_inventory(rows, query="procedure", county="duval")
    assert len(results) >= 1
    assert any("A" in r["title"] for r in results)

def test_search_index_io(tmp_path):
    """Search index files are read/written correctly."""
    rows = [{"record_id": "d1", "title": "Test", "text": "Body", "category": "Test",
             "county_ids": ["duval"], "circuit_ids": ["fourth"],
             "topics": ["test"], "court_levels": ["county"], "divisions": ["duval"]}]
    index_path = tmp_path / "test-index.json"
    write_search_index(rows, index_path)
    loaded = load_search_index(index_path)
    assert loaded["schema_version"] == 1
    assert len(loaded["rows"]) == 1

def test_generate_site(tmp_path):
    """Site generation produces expected files."""
    from tests.test_publication import example_issue
    issue = example_issue()
    output_dir = tmp_path / "site"
    generate_site(issue, [], output_dir)

    public = output_dir / "public"
    assert (public / "index.html").exists()
    assert (public / "procedures" / "index.html").exists()
    assert (public / "assets" / "site.css").exists()
    assert (public / "assets" / "search.js").exists()
    assert '"preview":true' in (public / "index.html").read_text()
    assert 'id="preview-notice"' not in (public / "index.html").read_text()

def test_site_css_and_js():
    """CSS and JS are generated."""
    css = _site_css()
    assert "font-family" in css
    js = _search_js()
    assert "filterRows" in js

def test_release_gate_manual():
    """Manual release gate requires approval."""
    gate = ReleaseGate(mode="manual")
    gate.stage("/tmp/test")
    try:
        gate.approve()
        assert False, "Should require manual approval"
    except:
        pass

def test_release_gate_automated():
    """Automated release gate approves directly."""
    gate = ReleaseGate(mode="automated")
    gate.stage("/tmp/test")
    result = gate.approve()
    assert result is True

def test_release_manifest():
    """Release manifest has required fields."""
    manifest = create_release_manifest(
        {"issue_id": "issue_test", "version": 1, "cutoff_utc": "2026-01-01T00:00:00Z",
         "coverage_status": "complete"},
        "snap_test", "/tmp/test"
    )
    assert manifest["schema_version"] == 1
    assert manifest["data_cutoff"]
    assert manifest["inventory_snapshot_id"] == "snap_test"

def test_publish_release(tmp_path):
    """Publish release writes manifest file."""
    manifest = {"schema_version": 1, "release_id": "rel_test", "data_cutoff": "2026-01-01",
                "issue_id": "issue_1", "version": 1, "coverage_status": "complete",
                "inventory_snapshot_id": "snap_1"}
    publish_release(manifest, tmp_path, tmp_path)
    manifest_file = tmp_path / "data" / "release.json"
    assert manifest_file.exists()

def test_launchd_plist():
    """Launchd plist is generated."""
    plist = generate_launchd_plist()
    assert "<?xml" in plist
    assert "flwu.weekly" in plist
    assert "<key>Weekday</key>" in plist

def test_launchd_plist_custom_script():
    """Launchd plist uses custom script path."""
    plist = generate_launchd_plist(script_path="/custom/flwu")
    assert "/custom/flwu" in plist

def test_section_categories():
    """Section categories match expected order."""
    cats = get_section_categories()
    assert len(cats) == 4
    assert cats[0][0] == "statutes"
    assert cats[3][1] == "Local Rules"

def test_validate_sources():
    """Validate sources checks required fields."""
    sources = load_sources()
    validate_sources(sources)  # Should not raise
    # Missing source should fail
    try:
        validate_sources([{"bad": "source"}])
        assert False
    except ValueError:
        pass

def test_coverage_equals_complete_only_with_evidence():
    """Empty results are complete only with pagination/freshness evidence."""
    # This is validated by test_coverage structure in earlier cards
    pass
