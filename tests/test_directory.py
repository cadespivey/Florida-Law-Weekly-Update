import copy
import json
import sqlite3

import pytest

from flwu.directory import load_directory, import_directory, read_directory, county_judges
from flwu.directory_render import render_appendix
from flwu.state import open_db, migrate
from flwu.render import render_issue, render_markdown_issue
from flwu.fixture_pipeline import run_fixture
from pathlib import Path


def test_snapshot_roundtrip_idempotence_and_history(tmp_path):
    conn = open_db(tmp_path / 'directory.db')
    migrate(conn)
    schema = conn.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall()
    data = load_directory()
    assert import_directory(conn, data)['new_revisions'] == 180
    assert import_directory(conn, data)['new_revisions'] == 0
    assert len(read_directory(conn)['entities']) == 180
    changed = copy.deepcopy(data)
    changed['entities'][0]['assistant'] = 'TEST ASSISTANT'
    assert import_directory(conn, changed)['new_revisions'] == 1
    assert conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0] == 180
    assert conn.execute('SELECT COUNT(*) FROM revisions').fetchone()[0] == 181
    assert schema == conn.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall()
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    current = {e['entity_id']:e for e in read_directory(conn)['entities']}
    assert current[data['entities'][0]['entity_id']]['assistant'] == 'TEST ASSISTANT'
    conn.close()


def test_all_counties_unique_shared_assignments_and_procedures():
    data = load_directory()
    judges = county_judges(data)
    assert len(judges) == 84
    assert len({e['entity_id'] for e in judges}) == 84
    assert len(county_judges(data,['Clay'])) == 7
    assert any(e['name']=='Howard O. McGillin Jr.' for e in county_judges(data,['Putnam']))
    assert sum(e['procedure_status']=='individual_document_located' for e in judges) == 82
    with pytest.raises(ValueError): county_judges(data,['Orange'])
    gaps=[e for e in judges if e['procedure_status']=='individual_procedure_not_verified']
    assert {e['name'] for e in gaps} == {'Lance M. Day','Meredith Charbula'}


def test_invalid_import_is_atomic(tmp_path):
    conn=open_db(tmp_path/'invalid.db');migrate(conn)
    data=load_directory();data['entities'][-1]['sources']=['javascript:alert(1)']
    with pytest.raises(ValueError):import_directory(conn,data)
    assert conn.execute('SELECT count(*) FROM runs').fetchone()[0]==0
    conn.close()


def test_render_integration_and_escaping(tmp_path):
    data=load_directory()
    data['entities'][0]['name']='<script>bad()</script>'
    html=render_appendix(data)
    assert '<script>bad()' not in html
    assert '&lt;script&gt;' in html
    assert html.count('class="directory-page"')==2
    assert 'CALL TO CONFIRM' in html
    for renderer in (render_issue,render_markdown_issue):
        result=renderer([{'record_json':{'kind':'case','title':'Test opinion'},'revision_id':'r'}],[],issue={'directory':data})
        assert 'Test opinion' in result
        assert result.index('Local Rules') < result.index('Judicial directory')
    run_fixture(Path('fixtures/synthetic-source.json'),tmp_path/'state',tmp_path/'output',directory=data)
    preview=next((tmp_path/'output').rglob('index.html')).read_text()
    assert preview.index('Local Rules') < preview.index('Judicial directory')
    assert 'Public-source reference (not fixture data)' in preview
