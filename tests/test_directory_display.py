import copy
import json
import re
from pathlib import Path
import pytest
from flwu.directory_display import format_contacts, load_formats


def test_exact_source_change_does_not_reuse_old_format():
    formats={'contacts':{'old source':[{'label':'Phone','lines':['old number']}]}}
    assert format_contacts({'details':{'Office contact':'new source'}},formats)['office']==[{'label':'Office contact','lines':['new source']}]


def test_shared_phone_deduplicates_but_distinct_values_survive():
    formats={'contacts':{'chambers':[{'label':'Phone — profile','type':'phone','lines':['111']},{'label':'Phone — procedure','type':'phone','lines':['222']}],
                         'assistant':[{'label':'Phone','type':'phone','lines':['111']} ]}}
    person={'details':{'Assistant contact':'assistant','Chambers phone':'chambers'}}
    before=copy.deepcopy(person)
    output=format_contacts(person,formats)
    assert len(output['office'])==2 and output['assistant']==[]
    assert person==before


def test_reviewed_baseline_preserves_all_distinct_contact_numbers_and_emails():
    path=Path('website/updates/update-9090865a53f00952babe.json')
    if not path.exists():pytest.skip('Published baseline not included in this checkout')
    formats=load_formats()
    for person in json.loads(path.read_text())['directory']:
        display=format_contacts(person,formats)
        rows=display['office']+display['assistant']
        source=' '.join(person['details'].values())
        source=source.replace('ordersDivision46@','Division46@').replace('Wordordersdivision52@','division52@')
        expected_emails={s.casefold() for s in re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',source)}
        expected_phones={re.sub(r'\D','',s) for s in re.findall(r'(?<!\d)(?:\(\d{3}\)\s*|\d{3}-)\d{3}-\d{4}',source)}
        assert {r['href'][7:].casefold() for r in rows if r.get('href','').startswith('mailto:')}==expected_emails,person['name']
        assert {r['href'][4:] for r in rows if r.get('href','').startswith('tel:')}==expected_phones,person['name']
        assert all(r['lines'] and all(r['lines']) for r in rows)


def test_invalid_contact_link_rejected():
    formats={'contacts':{'bad':[{'label':'Email','lines':['test'],'href':'mailto:bad\naddress'}]}}
    with pytest.raises(ValueError):format_contacts({'details':{'Office contact':'bad'}},formats)
