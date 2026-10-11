import pytest
from flwu.diff import compare_snapshots

def _r(doc, rev, status="adopted"):
    return {"document_id": doc, "revision_id": rev, "legal_status": status}

def test_same_revision_unchanged():
    r = compare_snapshots([_r("d1","r1")], [_r("d1","r1")])
    assert r["unchanged"] == ["d1"]

def test_changed_text_amended():
    r = compare_snapshots([_r("d1","old")], [_r("d1","new")])
    assert r["amended"] == ["d1"]

def test_withdrawn():
    r = compare_snapshots([_r("d1","r1","adopted")], [_r("d1","r1","withdrawn")])
    assert "d1" in r["superseded"] or "d1" in r["withdrawn"]

def test_absent_not_withdrawn():
    r = compare_snapshots([], [_r("new","r1")])
    assert r["added"] == ["new"] and r["withdrawn"] == []

def test_full_inventory_missing():
    r = compare_snapshots([_r("d1","r1")], [], inventory_complete=True)
    assert r["missing_for_review"] == ["d1"] and r["withdrawn"] == []

def test_first_run_baseline():
    r = compare_snapshots([], [_r("d1","r1"), _r("d2","r2")], first_run=True)
    assert r["baseline"] is True and r["added"] == ["d1", "d2"]

def test_duplicate_conflicting():
    with pytest.raises(ValueError):
        compare_snapshots([], [_r("d1","a"), _r("d1","b")])
