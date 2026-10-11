"""Explicit, allowlisted public exports from immutable research captures.

Public builds consume only these exports, never the private research database.
Finalization is the recorded editorial approval; synthetic previews are isolated.
"""
from __future__ import annotations
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit, parse_qs

SECTIONS = [('statutes', 'Statutes'), ('case_law', 'Case Law'),
            ('procedural_rules', 'Procedural Rules'), ('local_rules', 'Local Rules')]
KEYS = {k for k, _ in SECTIONS}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def safe_url(value, *, preview=False):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('Invalid citation URL')
    if preview and re.fullmatch(r'evidence/[a-f0-9]{64}\.txt', value):
        return value
    url = urlsplit(value)
    if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
        raise ValueError('Citations require public HTTP(S) URLs without credentials')
    if set(k.lower() for k in parse_qs(url.query)) & {'token', 'access_token', 'api_key', 'apikey', 'key', 'password'}:
        raise ValueError('Credential-bearing URL cannot be exported')
    if not preview and (url.hostname.endswith('.invalid') or url.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('Synthetic/local citation cannot be published')
    return value


def validate_issue(issue, *, preview=False):
    try:
        return _validate_issue(issue, preview=preview)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Malformed public issue schema') from exc


def _validate_issue(issue, *, preview=False):
    allowed = {'schema_version', 'id', 'title', 'window_start', 'window_end', 'published_at',
               'synthetic', 'sections', 'directory', 'provenance', 'content_sha256'}
    if set(issue) != allowed or issue['schema_version'] != 1:
        raise ValueError('Invalid public issue schema')
    if not re.fullmatch(r'[a-z0-9-]+', issue['id']):
        raise ValueError('Invalid public issue ID')
    if not isinstance(issue['title'], str) or not issue['title'].strip():
        raise ValueError('Issue title must be text')
    if not isinstance(issue['synthetic'], bool) or (issue['synthetic'] and not preview):
        raise ValueError('Synthetic issue requires an explicit preview build')
    for key in ('window_start', 'window_end'):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', issue[key]):
            raise ValueError('Report dates must use YYYY-MM-DD')
    if date.fromisoformat(issue['window_start']) > date.fromisoformat(issue['window_end']):
        raise ValueError('Reversed report period')
    if datetime.fromisoformat(issue['published_at'].replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('Publication timestamp requires timezone')
    if set(issue['sections']) != KEYS:
        raise ValueError('All four report sections are required')
    if issue['content_sha256'] != digest({k: v for k, v in issue.items() if k != 'content_sha256'}):
        raise ValueError('Public issue checksum mismatch; re-export the reviewed capture')
    provenance = issue['provenance']
    if set(provenance) != {'capture_id', 'report_sha256', 'review_status'}:
        raise ValueError('Invalid public provenance')
    if not re.fullmatch(r'[a-f0-9]{64}', provenance['capture_id']):
        raise ValueError('Invalid capture checksum')
    if not preview and (provenance['review_status'] != 'finalized' or not re.fullmatch(r'[a-f0-9]{64}', provenance['report_sha256'] or '')):
        raise ValueError('Public issue requires a finalized report')
    for section in issue['sections'].values():
        if set(section) != {'status', 'items'} or section['status'] not in ('reviewed', 'incomplete'):
            raise ValueError('Section requires reviewed/incomplete status and items')
        if not preview and section['status'] != 'reviewed':
            raise ValueError('Incomplete section cannot be published')
        if not isinstance(section['items'], list):
            raise ValueError('Section items must be a list')
        for item in section['items']:
            if set(item) != {'id', 'title', 'summary', 'publication_date', 'effective_date', 'legal_status', 'citations'}:
                raise ValueError('Unexpected public item fields')
            if not item['summary'] or not isinstance(item['citations'], list) or not item['citations']:
                raise ValueError('Every summary needs source citations')
            if any(not isinstance(item[k], str) for k in ('id', 'title', 'summary', 'legal_status')):
                raise ValueError('Item text fields must be strings')
            if item['publication_date']:
                day = date.fromisoformat(item['publication_date'])
                if not date.fromisoformat(issue['window_start']) <= day <= date.fromisoformat(issue['window_end']):
                    raise ValueError('Published item falls outside its reporting period')
            if item['effective_date']:
                date.fromisoformat(item['effective_date'])
            for cite in item['citations']:
                validate_citation(cite, preview)
    if not isinstance(issue['directory'], list):
        raise ValueError('Directory must be a list')
    for person in issue['directory']:
        if set(person) - {'court_ids'} != {'id', 'name', 'kind', 'counties', 'details', 'procedures', 'governing_rules', 'citations'}:
            raise ValueError('Unexpected public directory fields')
        if 'court_ids' in person and (not isinstance(person['court_ids'], list) or any(not isinstance(v, str) for v in person['court_ids'])):
            raise ValueError('Court IDs must be a list of strings')
        if not isinstance(person['citations'], list) or not person['citations']:
            raise ValueError('Directory entry lacks citations')
        if person['kind'] not in ('judge', 'clerk') or any(not isinstance(person[k], str) for k in ('id', 'name', 'procedures')):
            raise ValueError('Invalid public person')
        if any(not isinstance(person[k], list) or any(not isinstance(v, str) for v in person[k]) for k in ('counties', 'governing_rules')):
            raise ValueError('Directory counties/rules must be lists of text')
        if not isinstance(person['details'], dict) or any(not isinstance(v, str) for v in person['details'].values()):
            raise ValueError('Directory contacts must be text')
        for cite in person['citations']:
            validate_citation(cite, preview)
    return issue


def validate_citation(cite, preview):
    if set(cite) != {'label', 'url', 'quote'} or not cite['label']:
        raise ValueError('Invalid public citation')
    if not isinstance(cite['label'], str) or not isinstance(cite['quote'], str) or not cite['quote'].strip():
        raise ValueError('Citation label and quotation must be text')
    safe_url(cite['url'], preview=preview)


def export_capture(database, capture_id, archive, *, preview=False):
    archive = Path(archive)
    conn = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT c.*,s.mode FROM captures c JOIN streams s ON s.stream=c.stream WHERE capture_id=?', (capture_id,)).fetchone()
        if not row:
            raise ValueError('Unknown research capture')
        payload = json.loads(row['payload']); contract = payload['contract']
        if digest([row['stream'], row['run_id'], payload]) != capture_id:
            raise ValueError('Research capture checksum mismatch')
        approval = conn.execute('SELECT * FROM finalized_reports WHERE capture_seq=? ORDER BY seq DESC LIMIT 1', (row['seq'],)).fetchone()
        synthetic = row['mode'] == 'synthetic_replay'
        if not preview and (synthetic or not approval or payload['status'] != 'ready_for_review'):
            raise ValueError('Publication requires a complete, finalized live research capture')
        if approval:
            report = conn.execute('SELECT bytes FROM artifacts WHERE sha256=?', (approval['report_sha256'],)).fetchone()
            if not report or hashlib.sha256(report[0]).hexdigest() != approval['report_sha256']:
                raise ValueError('Finalized report bytes missing or changed')
        artifact_files = {}

        def citations(refs):
            result = []
            for ref in refs:
                if not ref.get('quote'):
                    continue
                raw = conn.execute('SELECT bytes FROM artifacts WHERE sha256=?', (ref['sha256'],)).fetchone()
                if not raw or hashlib.sha256(raw[0]).hexdigest() != ref['sha256']:
                    raise ValueError('Citation original missing or changed')
                extracted = conn.execute('SELECT bytes FROM artifacts WHERE sha256=?', (ref['text_sha256'],)).fetchone()
                if not extracted or hashlib.sha256(extracted[0]).hexdigest() != ref['text_sha256'] or ref['quote'] not in extracted[0].decode('utf-8'):
                    raise ValueError('Citation quotation is absent from verified extracted text')
                if not preview and ref.get('synthetic'):
                    raise ValueError('Synthetic citation cannot enter a public issue')
                url = safe_url(ref['url'], preview=preview)
                if synthetic:
                    url = 'evidence/' + ref['sha256'] + '.txt'
                    artifact_files[url] = raw[0]
                item = {'label': (ref.get('endpoint') or urlsplit(ref['url']).hostname) + ' · ' + str(ref.get('locator', 'source')),
                        'url': url, 'quote': ref['quote']}
                if item not in result:
                    result.append(item)
            return result

        issue = {'schema_version': 1, 'id': 'update-' + capture_id[:20],
                 'title': 'Florida Law Weekly Update', 'window_start': contract['window_start'],
                 'window_end': contract['window_end'], 'published_at': approval['finalized_at'] if approval else row['recorded_at'],
                 'synthetic': synthetic, 'sections': {k: {'status': 'reviewed' if payload['status'] == 'ready_for_review' else 'incomplete', 'items': []} for k, _ in SECTIONS},
                 'directory': [], 'provenance': {'capture_id': capture_id,
                   'report_sha256': approval['report_sha256'] if approval else None,
                   'review_status': 'finalized' if approval else 'preview'}}
        roster = {}
        court_roster = {}
        court_names = {'roster-supreme': 'supreme_court', **{'roster-dca-'+str(n): 'dca_'+word for n, word in enumerate(['first','second','third','fourth','fifth','sixth'], 1)},
                       'roster-circuit-4':'circuit_fourth', 'roster-circuit-7':'circuit_seventh', 'roster-circuit-8':'circuit_eighth'}
        for finding in payload['findings']:
            if finding['kind'] == 'source_inventory':
                for person in finding['facts'].get('entities', []):
                    key = 'person-' + person['id']
                    roster.setdefault(key, set()).update(person['counties'])
                    if finding['key'] in court_names:
                        court_roster.setdefault(key, set()).add(court_names[finding['key']])
        for finding in payload['findings']:
            facts = finding['facts']; kind = finding['kind']
            if kind == 'candidate' and facts.get('decision') == 'include':
                section = facts.get('section')
                if synthetic:
                    section = 'procedural_rules' if facts['id'].startswith('R-') else 'case_law'
                if section not in KEYS:
                    raise ValueError('Candidate needs explicit section before review/finalization: ' + finding['key'])
                if not synthetic and not facts.get('title'):
                    raise ValueError('Included candidate requires a reviewed public title')
                summary = facts.get('summary') or '\n\n'.join(c['statement'] for c in facts.get('claims', []) if c.get('review') == 'supported')
                issue['sections'][section]['items'].append({'id': finding['key'], 'title': facts.get('title') or facts['id'],
                    'summary': summary, 'publication_date': facts.get('publication_date'), 'effective_date': facts.get('effective_date'),
                    'legal_status': facts.get('legal_status', 'unknown'), 'citations': citations(finding['citations'])})
            elif kind in ('judge', 'clerk'):
                details = {}
                labels = {'chambers_phone': 'Chambers', 'address': 'Address', 'assistant_name': 'Judicial assistant',
                          'assistant_contact': 'Assistant contact', 'division': 'Division', 'phone': 'Office phone', 'contact': 'Office contact'}
                for key, label in labels.items():
                    if facts.get(key): details[label] = str(facts[key])
                for key, field in facts.get('fields', {}).items():
                    details[key.replace('_', ' ').capitalize()] = str(field.get('value') or 'Not published in checked sources')
                procedure = facts.get('procedure', {})
                procedure_text = procedure.get('summary') or '; '.join(d.get('applicability', '') for d in procedure.get('documents', []))
                if procedure.get('status') == 'no_published_procedure_located':
                    procedure_text = procedure_text or 'No individual procedure located in the sources checked.'
                issue['directory'].append({'id': finding['key'], 'name': facts['name'], 'kind': kind,
                    'court_ids': sorted(court_roster.get(finding['key'], [])),
                    'counties': facts.get('counties') or ([facts['county']] if facts.get('county') else sorted(roster.get(finding['key'], []))),
                    'details': details, 'procedures': procedure_text,
                    'governing_rules': [r.get('summary') or r.get('title') or 'See governing rule source.' for r in facts.get('governing_rules', [])],
                    'citations': citations(finding['citations'])})
        issue['content_sha256'] = digest(issue)
        validate_issue(issue, preview=preview)
        # Write only an explicit public allowlist; no receipts, drafts, DB or prompts.
        target = archive / (issue['id'] + '.json')
        text = json.dumps(issue, indent=2, ensure_ascii=False, sort_keys=True) + '\n'
        if target.exists():
            if json.loads(target.read_text(encoding='utf-8')) != issue:
                raise ValueError('Immutable public issue already exists with different content')
            return target
        archive.mkdir(parents=True, exist_ok=True)
        for relative, data in artifact_files.items():
            path = archive / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        with target.open('x', encoding='utf-8') as output:
            output.write(text)
        return target
    finally:
        conn.close()
