"""Reviewed contact reference data, stored in FLWU's unchanged schema v1.

body_text is canonical JSON of a compiled directory entity, not court text.
Pinned entity IDs are assigned once in the seed and must survive name changes.
This reference source is separate from legal-change acquisition and analysis.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from flwu.identity import stamp_ids
from flwu.records import canonical_json, validate_record

SOURCE = 'flwu_judicial_directory'
SEED = Path(__file__).parent / 'data' / 'judicial_directory.json'
COUNTIES = ('Duval', 'St. Johns', 'Putnam', 'Nassau', 'Baker', 'Union', 'Clay')


def load_directory(path: Path = SEED) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    validate_directory(data)
    return data


def validate_directory(data: dict) -> None:
    if data.get('format_version') != 1 or set(data['counties']) != set(COUNTIES):
        raise ValueError('Expected directory v1 and the seven configured counties')
    seen = set()
    for e in data['entities']:
        if e['entity_id'] in seen:
            raise ValueError('Duplicate stable entity ID')
        seen.add(e['entity_id'])
        if e['entity_type'] not in ('judge', 'clerk', 'circuit'):
            raise ValueError('Unknown directory entity type')
        if not set(e['counties']) <= set(COUNTIES):
            raise ValueError('Unknown county')
        urls = e['sources'] + [p['url'] for p in e.get('procedures', [])]
        urls += [e[k] for k in ('administrative_orders_url', 'statewide_rules_url') if k in e]
        if not urls or any(urlparse(u).scheme != 'https' or not urlparse(u).netloc for u in urls):
            raise ValueError('Directory links must be absolute HTTPS URLs')


def directory_records(data: dict, observed_at: str) -> list[dict]:
    validate_directory(data)
    records = []
    for entity in data['entities']:
        body = canonical_json(entity)
        rec = dict(schema_version=1, mode='production', synthetic=False,
                   source_id=SOURCE, document_key=entity['entity_id'], kind='roster',
                   scope_ids=sorted(c.lower().replace('. ', '_').replace(' ', '_') for c in entity['counties']) or ['statewide'],
                   canonical_url=entity['sources'][0], title=entity['name'],
                   body_text=body.decode(), publication_date=None, effective_date=None,
                   status_date=None, legal_status='unknown', observed_at=observed_at,
                   exact_sha256=hashlib.sha256(body).hexdigest(), pinpoints=[],
                   facts={'source_notes': ['Compiled contact reference; hashes describe compiled JSON, not official source bytes.'],
                          'subject_tags': ['judicial_directory']}, supersedes_revision_id=None)
        records.append(validate_record(stamp_ids(rec), mode='production'))
    return records


def import_directory(conn: sqlite3.Connection, data: dict, *, observed_at: str | None = None) -> dict:
    """Atomically commit a reviewed snapshot; repeated imports reuse revisions.

    The caller opens/migrates the FLWU database. Import does not claim the linked
    court pages were freshly fetched; checked_on remains the research date.
    """
    now = observed_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    records = directory_records(data, now)
    token = uuid.uuid4().hex
    run, attempt, snapshot = ('directory_run_'+token, 'directory_attempt_'+token, 'directory_snapshot_'+token)
    coverage = json.dumps({'reference_only': True, 'checked_on': data['checked_on'],
                           'counties': data['counties'], 'entities': len(records),
                           'contact_gaps_preserved': True})
    added = 0
    with conn:
        conn.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)',
                     (run, 'production', data['checked_on'], data['checked_on'], 'running', now, None, None))
        conn.execute('INSERT INTO source_attempts VALUES (?,?,?,?,?,?,?,?)',
                     (attempt, run, SOURCE, 'running', now, None, coverage, None))
        for r in records:
            prior = conn.execute('SELECT source_id,document_key FROM documents WHERE document_id=?', (r['document_id'],)).fetchone()
            if prior and tuple(prior) != (SOURCE, r['document_key']):
                raise ValueError('Document identity collision')
            conn.execute('INSERT INTO documents VALUES (?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET canonical_url=excluded.canonical_url',
                         (r['document_id'], SOURCE, r['document_key'], r['canonical_url']))
            encoded = canonical_json(r).decode()
            cur = conn.execute('INSERT INTO revisions VALUES (?,?,?,?,?) ON CONFLICT(revision_id) DO NOTHING',
                               (r['revision_id'], r['document_id'], r['content_sha256'], encoded, now))
            added += cur.rowcount
            conn.execute('INSERT INTO observations VALUES (?,?,?,?)', (attempt, r['revision_id'], now, encoded))
        conn.execute('INSERT INTO source_snapshots VALUES (?,?,?,?,?,?)',
                     (snapshot, SOURCE, attempt, now, json.dumps(sorted(r['revision_id'] for r in records)), coverage))
        conn.execute('INSERT INTO source_checkpoints VALUES (?,?,?) ON CONFLICT(source_id) DO UPDATE SET snapshot_id=excluded.snapshot_id,watermark_utc=excluded.watermark_utc', (SOURCE, snapshot, now))
        conn.execute('UPDATE source_attempts SET status=?,finished_at=? WHERE attempt_id=?', ('complete', now, attempt))
        conn.execute('UPDATE runs SET status=?,finished_at=? WHERE run_id=?', ('success_changes' if added else 'success_no_changes', now, run))
    return {'entities': len(records), 'new_revisions': added, 'snapshot_id': snapshot}


def read_directory(conn: sqlite3.Connection) -> dict:
    snapshot = conn.execute('SELECT s.attempt_id,s.coverage_json FROM source_snapshots s JOIN source_checkpoints c ON c.snapshot_id=s.snapshot_id WHERE c.source_id=?', (SOURCE,)).fetchone()
    if not snapshot:
        raise ValueError('No imported judicial directory snapshot')
    coverage = json.loads(snapshot[1])
    rows = conn.execute('SELECT record_json FROM observations WHERE attempt_id=? ORDER BY revision_id', (snapshot[0],))
    data = dict(format_version=1, checked_on=coverage['checked_on'], counties=coverage['counties'],
                entities=[json.loads(json.loads(r[0])['body_text']) for r in rows])
    validate_directory(data)
    return data


def county_judges(data: dict, counties=COUNTIES) -> list[dict]:
    if not set(counties) <= set(COUNTIES):
        raise ValueError('Unknown county filter')
    return sorted((e for e in data['entities'] if e['entity_type'] == 'judge' and set(e['counties']) & set(counties)), key=lambda e: (e['court'], e['name']))
