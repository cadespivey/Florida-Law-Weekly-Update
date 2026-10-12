"""Archive tests use invented text; they establish mechanics, never legal correctness."""
import copy
import json
from pathlib import Path
import pytest
from flwu.publication import SECTIONS, digest, validate_issue, export_capture
from flwu.site import build_site
from flwu.cli import main
from flwu import history as h


def example_issue(*, synthetic=True, start='2026-01-01', end='2026-01-07', ident='test-one'):
    cite = {'label': 'Test authority · paragraph 1', 'url': 'https://example.org/test', 'quote': 'Invented test text.'}
    issue = {'schema_version': 1, 'id': ident, 'title': 'Test update', 'window_start': start, 'window_end': end,
             'published_at': end+'T12:00:00Z', 'synthetic': synthetic,
             'sections': {key: {'status': 'reviewed', 'items': []} for key, _ in SECTIONS},
             'directory': [{'id': 'person-example', 'name': 'Example Judge', 'kind': 'judge', 'counties': ['Duval'],
                            'details': {'Chambers': '555-0100'}, 'procedures': 'Invented test procedure.',
                            'governing_rules': ['Invented governing rule.'], 'citations': [cite]}],
             'provenance': {'capture_id': 'a'*64, 'report_sha256': 'b'*64, 'review_status': 'finalized'}}
    issue['sections']['case_law']['items'] = [{'id': 'test-case', 'title': 'Example case', 'summary': 'Invented test summary.',
        'publication_date': start, 'effective_date': None, 'legal_status': 'operative', 'citations': [cite]}]
    return seal(issue)


def seal(issue):
    issue['content_sha256'] = digest({k:v for k,v in issue.items() if k != 'content_sha256'})
    return issue


def archive(tmp_path, *issues):
    folder=tmp_path/'archive';folder.mkdir()
    for issue in issues:
        (folder/(issue['id']+'.json')).write_text(json.dumps(issue))
    return folder


def test_deterministic_archive_order_safe_embedding_and_no_private_files(tmp_path):
    old=example_issue();new=example_issue(start='2026-02-01',end='2026-02-07',ident='new')
    new['sections']['case_law']['items'][0]['summary']='</script><script>window.bad=true</script>'
    source=archive(tmp_path, old, seal(new))
    (source/'private.sqlite').write_text('PRIVATE')
    first=build_site(source,tmp_path/'first',preview=True);second=build_site(source,tmp_path/'second',preview=True)
    text=(first/'index.html').read_text()
    assert '\\u003c/script>' in text and 'window.bad=true</script>' not in text
    assert text.index('"id":"new"')<text.index('"id":"test-one"')
    assert 'PRIVATE' not in text and not (first/'private.sqlite').exists()
    assert (first/'index.html').read_bytes()==(second/'index.html').read_bytes()
    assert (first/'procedures/index.html').read_text().count('../directory.html')==2
    from bs4 import BeautifulSoup
    directory = BeautifulSoup((first/'directory.html').read_text(), 'html.parser')
    homepage = BeautifulSoup(text, 'html.parser')
    assert directory.body['data-page'] == 'directory'
    assert homepage.body['data-page'] == 'updates'
    assert directory.select_one('#directory-link')['aria-current'] == 'page'
    assert homepage.select_one('#updates-link')['aria-current'] == 'page'
    assert len(homepage.select('.court-menu .court-links a')) == 38
    assert len(directory.select('.personnel-menu [data-court]')) == 17
    assert directory.select_one('script[src]')['src'] == 'assets/search.js'
    about = BeautifulSoup((first/'about.html').read_text(), 'html.parser')
    assert about.body['data-page'] == 'about'
    assert about.select_one('#about-link')['aria-current'] == 'page'
    assert not about.select('form, #archive-data')
    for page in (homepage, directory, about):
        assert page.select_one('.site-nav').find_all(recursive=False)[-1]['id'] == 'about-link'
    assert (first/'about.html').read_bytes() == (second/'about.html').read_bytes()


def test_failed_build_preserves_previous_and_rejects_synthetic(tmp_path):
    source=archive(tmp_path,example_issue());output=tmp_path/'site'
    with pytest.raises(ValueError,match='Synthetic'):build_site(source,output)
    assert not output.exists()
    build_site(source,output,preview=True)
    before=(output/'index.html').read_bytes()
    with pytest.raises(ValueError,match='existing'):build_site(source,output,preview=True)
    assert (output/'index.html').read_bytes()==before


@pytest.mark.parametrize('mutation',[
    lambda i:i.update(private_database='/private/history.sqlite'),
    lambda i:i['sections']['case_law']['items'][0].update(summary=''),
    lambda i:i['sections']['case_law']['items'][0].update(publication_date='2025-12-31'),
    lambda i:i['sections']['case_law']['items'][0]['citations'][0].update(url='javascript:alert(1)'),
    lambda i:i['sections']['case_law']['items'][0]['citations'][0].update(url='https://example.org/?api_key=secret'),
    lambda i:i['sections']['case_law'].update(status='incomplete'),
    lambda i:i['provenance'].update(review_status='preview'),
    lambda i:i['directory'][0].update(counties='Duval'),
    lambda i:i['sections']['case_law'].update(items={}),
    lambda i:i.update(directory={}),
    lambda i:i.update(window_start='20260101'),
])
def test_publication_rejects_invalid_exports(mutation):
    issue=example_issue(synthetic=False);mutation(issue)
    with pytest.raises(ValueError):validate_issue(seal(issue))


def test_checksum_tamper_and_duplicate_ids(tmp_path):
    issue=example_issue();issue['title']='Changed'
    with pytest.raises(ValueError,match='checksum'):validate_issue(issue,preview=True)
    source=archive(tmp_path,seal(issue));(source/'duplicate.json').write_text(json.dumps(issue))
    with pytest.raises(ValueError,match='Duplicate'):build_site(source,tmp_path/'site',preview=True)


def saved_capture(tmp_path, *, mode='manual_research', finalize=True, section=True, roster_key='roster', contract_overrides=None, fact_overrides=None, counties=None):
    raw=b'Invented test text.';sha=h.sha(raw)
    cite={'sha256':sha,'text_sha256':sha,'quote':raw.decode(),'url':'https://example.org/test','locator':'paragraph 1','retrieved_at':'2026-01-07T12:00:00Z'}
    facts={'id':'test-case','title':'Invented case','decision':'include','publication_date':'2026-01-01','effective_date':None,
           'claims':[{'statement':'Invented test summary.','review':'supported'}]}
    if section:facts['section']='case_law'
    payload={'status':'ready_for_review','contract':{'window_start':'2026-01-01','window_end':'2026-01-07'},
      'checks':[{'id':'test','status':'verified','checked_at':'2026-01-07T12:00:00Z','hashes':[sha]}], 'drafts':[{'private':'DO NOT EXPORT'}], 'origin':'/private/research',
      'findings':[{'key':'case:test','kind':'candidate','facts':facts,'citations':[cite]},
       {'key':roster_key,'kind':'source_inventory','facts':{'entities':[{'id':'example','counties':counties if counties is not None else ['Duval','Clay']}]},'citations':[cite]},
       {'key':'person-example','kind':'judge','facts':{'name':'Example Judge','fields':{'chambers_phone':{'value':'555-0100'}},
          'procedure':{'documents':[{'applicability':'Invented test procedure.'}]}},'citations':[cite]}]}
    db=tmp_path/'history.sqlite'
    payload['contract'].update(contract_overrides or {})
    facts.update(fact_overrides or {})
    with h.database(db) as conn:
        result=h.record(conn,stream='test',mode=mode,scope={},run_id='test',payload=payload,artifacts={sha:raw})
        if finalize:
            report=tmp_path/'report.html';report.write_text('Invented test report')
            h.finalize(conn,result['capture_id'],report,'Test fixture review only')
    return db,result['capture_id']


def test_research_county_ids_export_as_directory_labels(tmp_path):
    db,capture=saved_capture(tmp_path,counties=['duval','st_johns','Duval'])
    issue=json.loads(export_capture(db,capture,tmp_path/'archive').read_text())
    assert issue['directory'][0]['counties']==['Duval','St. Johns']


def test_reviewed_export_joins_counties_excludes_private_state_and_is_immutable(tmp_path):
    db,capture=saved_capture(tmp_path)
    target=export_capture(db,capture,tmp_path/'archive')
    issue=json.loads(target.read_text());validate_issue(issue)
    assert issue['directory'][0]['counties']==['Clay','Duval']
    assert 'DO NOT EXPORT' not in target.read_text() and '/private' not in target.read_text()
    assert export_capture(db,capture,tmp_path/'archive')==target
    # Whitespace/object order is not a new report, including another Python process.
    target.write_text(json.dumps(issue, sort_keys=False, separators=(',', ':')))
    assert export_capture(db,capture,tmp_path/'archive')==target
    target.write_text('{}')
    with pytest.raises(ValueError,match='Immutable'):export_capture(db,capture,tmp_path/'archive')


def test_export_needs_finalization_and_explicit_section(tmp_path):
    db,capture=saved_capture(tmp_path,finalize=False)
    with pytest.raises(ValueError,match='finalized'):export_capture(db,capture,tmp_path/'archive')
    second=tmp_path/'second';second.mkdir();db,capture=saved_capture(second,section=False)
    with pytest.raises(ValueError,match='explicit section'):export_capture(db,capture,tmp_path/'archive')


def test_directory_court_assignment_comes_from_roster_identity(tmp_path):
    db, capture = saved_capture(tmp_path, roster_key='roster-dca-1')
    issue = json.loads(export_capture(db, capture, tmp_path/'archive').read_text())
    assert issue['directory'][0]['court_ids'] == ['dca_first']


def test_citation_bytes_rechecked(tmp_path):
    db,capture=saved_capture(tmp_path)
    with h.database(db) as conn:
        conn.execute('UPDATE artifacts SET bytes=? WHERE sha256=?',(b'changed',h.sha(b'Invented test text.')));conn.commit()
    with pytest.raises(ValueError,match='missing or changed'):export_capture(db,capture,tmp_path/'archive')


def test_empty_production_archive_and_cli(tmp_path):
    source=archive(tmp_path)
    assert main(['publish','--archive',str(source),'--output',str(tmp_path/'public')])==0
    assert '"issues":[]' in (tmp_path/'public/index.html').read_text()
    assert main(['site','export','--archive',str(source)])==1


def test_workflow_matches_generator():
    from flwu.publish import publish_workflow_config
    workflow=json.loads(Path('.github/workflows/pages.yml').read_text())
    assert workflow==publish_workflow_config()
    assert workflow['jobs']['deploy']['needs']=='build'
    assert 'pull_request' in workflow['jobs']['deploy']['if']
    assert '--preview' not in json.dumps(workflow)


def evidence_issue(report_type='opening_baseline'):
    issue=example_issue(synthetic=False, start='2026-07-01', end='2026-07-01')
    issue.update(schema_version=2, report_type=report_type, coverage={
        'summary':'Dated primary-source evidence snapshot.',
        'limitations':['October directory observations do not reconstruct historical personnel.'],
        'directory_observed_at':'2026-10-12T19:00:00Z'})
    item=issue['sections']['case_law']['items'][0]
    item.update(publication_date='2026-06-01', inclusion_basis='opening_baseline')
    return issue


@pytest.mark.parametrize('pub,effective',[
    ('2026-06-01',None),('2026-06-01','2027-01-01'),(None,'2026-07-01')])
def test_opening_baseline_preserves_supported_source_dates(pub,effective):
    issue=evidence_issue();item=issue['sections']['case_law']['items'][0]
    item.update(publication_date=pub,effective_date=effective)
    result=validate_issue(seal(issue))
    assert result['sections']['case_law']['items'][0]['publication_date']==pub
    assert result['sections']['case_law']['items'][0]['effective_date']==effective


def test_later_effective_event_retains_old_issuance():
    issue=evidence_issue('period_update');item=issue['sections']['case_law']['items'][0]
    item.update(inclusion_basis='effective',effective_date='2026-07-01')
    validate_issue(seal(issue))
    assert item['publication_date']=='2026-06-01'
    item.update(inclusion_basis='publication',publication_date='2026-07-01')
    validate_issue(seal(issue))


@pytest.mark.parametrize('change',[
    {'publication_date':'2026-07-02'},
    {'publication_date':None,'effective_date':None},
    {'publication_date':None,'effective_date':'2027-01-01'},
    {'publication_date':'20260701'},
    {'publication_date':''},
    {'effective_date':'2026-02-30'},
    {'inclusion_basis':'publication'},
    {'inclusion_basis':None},
])
def test_baseline_rejects_unsupported_temporal_basis(change):
    issue=evidence_issue();issue['sections']['case_law']['items'][0].update(change)
    with pytest.raises(ValueError):validate_issue(seal(issue))


@pytest.mark.parametrize('basis,pub,effective',[
    ('opening_baseline','2026-07-01',None),('effective','2026-07-02','2026-07-01'),
    ('effective','2026-06-01',None),('effective','2026-06-01','2026-07-02'),
    ('publication',None,'2026-07-01'),('publication','2026-06-01',None),
    ('invented','2026-07-01',None)])
def test_period_update_rejects_wrong_event(basis,pub,effective):
    issue=evidence_issue('period_update')
    issue['sections']['case_law']['items'][0].update(inclusion_basis=basis,publication_date=pub,effective_date=effective)
    with pytest.raises(ValueError):validate_issue(seal(issue))


@pytest.mark.parametrize('change',[
    {'summary':''},{'summary':3},{'limitations':'not a list'}, {'limitations':['']},
    {'directory_observed_at':None},{'directory_observed_at':'2026-10-12'},
    {'directory_observed_at':False},{'extra':'private'}, {'limitations':[]}])
def test_coverage_and_current_directory_requirements(change):
    issue=evidence_issue();issue['coverage'].update(change)
    with pytest.raises(ValueError):validate_issue(seal(issue))


def test_v2_capture_export_roundtrip_and_approval_gate(tmp_path):
    issue=evidence_issue()
    overrides={'window_start':issue['window_start'],'window_end':issue['window_end'],
               'report_type':issue['report_type'],'coverage':issue['coverage']}
    facts={'publication_date':'2026-06-01','effective_date':'2027-01-01','inclusion_basis':'opening_baseline'}
    db,capture=saved_capture(tmp_path,contract_overrides=overrides,fact_overrides=facts)
    public=json.loads(export_capture(db,capture,tmp_path/'archive').read_text())
    assert public['schema_version']==2 and public['coverage']==issue['coverage']
    item=public['sections']['case_law']['items'][0]
    for key,value in facts.items():assert item[key]==value
    pending=tmp_path/'pending';pending.mkdir()
    db,capture=saved_capture(pending,finalize=False,contract_overrides=overrides,fact_overrides=facts)
    with pytest.raises(ValueError,match='finalized'):export_capture(db,capture,pending/'archive')


def test_v2_unknown_metadata_and_nonpoint_baseline_rejected():
    for change in [{'report_type':'other'},{'coverage':None},{'window_end':'2026-07-02'}]:
        issue=evidence_issue();issue.update(change)
        with pytest.raises(ValueError):validate_issue(seal(issue))
