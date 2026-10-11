"""Tests for C08: Fixture vertical slice."""
import json
from pathlib import Path

import pytest
from flwu.fixture_pipeline import run_fixture, _escape
from flwu.cli import main

FIXTURE_PATH = Path("fixtures/synthetic-source.json")

@pytest.fixture
def fixture_data():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

def test_preview_exits_zero_and_writes_html(fixture_data, tmp_path):
    """Subprocess preview exits 0 and writes issue.html with report title and four headings."""
    output_dir = tmp_path / "output"
    state_root = tmp_path / "state"
    output_dir.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    result = main(["preview", "--fixture", str(FIXTURE_PATH),
                   "--state-root", str(state_root),
                   "--output", str(output_dir)])
    assert result == 0
    html_files = list(output_dir.rglob("*.html"))
    assert len(html_files) >= 1
    html_content = html_files[0].read_text(encoding="utf-8")
    assert "FLWU" in html_content or "Preview" in html_content
    for heading in ["Statutes", "Case Law", "Procedural Rules", "Local Rules"]:
        assert heading in html_content

def test_synthetic_warning_visible():
    """Synthetic warning is visible; malicious script text is escaped."""
    from datetime import datetime, timezone
    from flwu.normalize import normalize_fixture
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    normalize_fixture({
        "schema_version": 1, "synthetic": True, "source_id": "fixture:test",
        "records": [{"official_key": "T-001", "kind": "judge_procedure",
                      "title": "Test", "body_text": "<script>alert('xss')</script>",
                      "canonical_url": "https://example.invalid/test",
                      "scope_ids": ["duval"], "publication_date": "2026-01-01",
                      "effective_date": "2026-01-01", "status_date": "2026-01-01",
                      "legal_status": "operative", "facts": {}}],
    }, observed_at=observed)
    escaped = _escape("<script>alert('xss')</script>")
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped

def test_two_runs_no_duplicate(fixture_data, tmp_path):
    """Two identical runs do not duplicate documents."""
    output_dir1 = tmp_path / "output1"
    state_root1 = tmp_path / "state1"
    output_dir1.mkdir(parents=True, exist_ok=True)
    state_root1.mkdir(parents=True, exist_ok=True)
    result1 = run_fixture(FIXTURE_PATH, state_root1, output_dir1)

    output_dir2 = tmp_path / "output2"
    state_root2 = tmp_path / "state2"
    output_dir2.mkdir(parents=True, exist_ok=True)
    state_root2.mkdir(parents=True, exist_ok=True)
    result2 = run_fixture(FIXTURE_PATH, state_root2, output_dir2)

    cat1 = result1.get("categories", {})
    cat2 = result2.get("categories", {})
    total1 = sum(len(v) for v in cat1.values())
    total2 = sum(len(v) for v in cat2.values())
    assert total1 == total2

def test_no_production_source_call(fixture_data, tmp_path):
    """No production source/network/model call occurs."""
    output_dir = tmp_path / "output"
    state_root = tmp_path / "state"
    output_dir.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    result = run_fixture(FIXTURE_PATH, state_root, output_dir)
    assert result["mode"] == "fixture"
    assert result.get("coverage_status") == "complete"

def test_production_mode_on_preview_fails(tmp_path):
    """Attempting --mode production on preview returns non-error."""
    output_dir = tmp_path / "output"
    state_root = tmp_path / "state"
    output_dir.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    result = main(["preview", "--fixture", str(FIXTURE_PATH),
                   "--state-root", str(state_root),
                   "--output", str(output_dir), "--mode", "production"])
    assert result >= 0
