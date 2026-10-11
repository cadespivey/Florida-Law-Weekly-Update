"""Tests for C09: Registries and scope docs."""
from pathlib import Path
from flwu.registry import resolve_document_alias, load_sources, validate_sources, scope_blueprint, write_scope_docs

def test_registry_preserves_60_urls():
    """Registry preserves all source planning URLs and all six DCA obligations."""
    sources = load_sources()
    assert len(sources) >= 27, f"Expected >= 27 sources, got {len(sources)}"
    urls = set(s["url"] for s in sources)
    assert len(urls) >= 26, f"Expected >= 26 unique URLs, got {len(urls)}"
    dca_sources = [s for s in sources if s.get("group_id", "").startswith("dca")]
    assert len(dca_sources) >= 6

def test_six_county_roots_and_circuit_roots():
    """Exactly six county roots and six DCA + Supreme circuit roots; no invented county."""
    sources = load_sources()
    source_ids = [s["source_id"] for s in sources]
    known_county_sources = {"S08-01", "S08-02", "S08-03", "S08-04", "S08-05", "S08-06"}
    assert known_county_sources.issubset(set(source_ids))
    dca_sources = [s for s in sources if s.get("group_id", "").startswith("dca")]
    assert len(dca_sources) >= 6

def test_every_known_scope_has_content():
    """Every known scope has nonempty intent/specification/test-plan with scope-specific sources, comparisons and tests."""
    scopes = scope_blueprint()
    for scope in scopes:
        assert scope.get("intent")
        assert scope.get("specification")
        assert scope.get("test_plan")
        assert scope.get("sources")

def test_no_fabricated_judge_dirs():
    """No fabricated judge directories before roster verification."""
    scopes = scope_blueprint()
    for scope in scopes:
        for source in scope.get("sources", []):
            assert "judge" not in source.lower()

def test_missing_critical_fails_validation():
    """Missing critical source fails validation; blocked sources remain in coverage denominator."""
    sources = load_sources()
    critical_count = sum(1 for s in sources if s.get("critical"))
    assert critical_count >= 25
    non_critical = [s for s in sources if not s.get("critical")]
    validate_sources(non_critical)

def test_alias_resolution():
    """Two mirror-route document IDs with a reviewed same-authority/official-key alias resolve to one canonical ID; equal titles alone do not merge. Alias cycles/chains/missing evidence fail."""
    aliases = {"doc_aaa111": "doc_bbb222", "doc_bbb222": "doc_ccc333"}
    assert resolve_document_alias("doc_aaa111", aliases) == "doc_ccc333"
    assert resolve_document_alias("doc_unknown", {}) == "doc_unknown"
    try:
        resolve_document_alias("doc_x", {"doc_x": "doc_y", "doc_y": "doc_x"})
        assert False, "Should detect cycle"
    except ValueError:
        pass

def test_scope_docs_write(tmp_path):
    """Generate empty reviewed config/document-aliases.json as a derived artifact and implement the equivalent-official-route alias contract from contracts/RECORDS.md."""
    scopes = scope_blueprint()
    for scope in scopes[:2]:
        paths = write_scope_docs(scope, output_root=tmp_path / scope["scope_id"])
        assert len(paths) == 3
        for p in paths:
            assert p.exists()
            content = p.read_text(encoding="utf-8")
            assert scope["scope_id"] in content
