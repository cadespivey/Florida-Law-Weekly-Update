"""Compact, linked, two-page county appendix plus full on-screen directory."""
from html import escape
from flwu.directory import load_directory, county_judges, validate_directory

CSS = '''
@page directory { size: letter landscape; margin: 0.3in; }
.directory {font-family:Arial,sans-serif;color:#162c40;line-height:1.15;}
.directory-page {page:directory;break-before:page;margin:24px 0;}
.directory h2 {font-size:16px;margin:0 0 5px;border:0;padding:0;}
.directory p {margin:3px 0;font-size:10px;}
.directory table {width:100%;border-collapse:collapse;table-layout:fixed;font-size:11px;}
.directory th,.directory td {padding:2px 3px;border:0;border-bottom:1px solid #dde5eb;vertical-align:top;text-align:left;}
.directory th {background:#e7eef4;}
.directory .group td {background:#eef3f7;font-weight:bold;padding-top:4px;}
.directory a {color:#165e8d;text-decoration:underline;}
.directory .addresses {font-size:9px;line-height:1.15;}
.directory .key {font-size:10px;}
.directory-full {margin-top:24px;}
.directory-full summary {cursor:pointer;}
.directory-full article {border-top:1px solid #ccd;padding:10px 0;}
@media print {
 body {max-width:none!important;margin:0!important;}
 .directory-page {margin:0;}
 .directory table {font-size:8pt;line-height:1;}
 .directory .addresses {font-size:8px;line-height:1;}
 .directory p {margin:2px 0;font-size:9px;}
 .directory th,.directory td {padding:0.3px 3px;}
 .directory .group td {padding-top:3px;}
 .directory-full {display:none;}
}
'''

def link(url, label):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def short(value):
    return escape(value.replace('Not publicly verified', 'Unverified').replace('Michele (Shelly)', 'Shelly'))


def render_appendix(data=None) -> str:
    data = load_directory() if data is None else data
    validate_directory(data)
    judges = county_judges(data)
    clerks = sorted((e for e in data['entities'] if e['entity_type'] == 'clerk' and e['counties']), key=lambda e:e['counties'][0])
    circuits = sorted((e for e in data['entities'] if e['entity_type'] == 'circuit'), key=lambda e:e['name'])
    parts = ['<style>'+CSS+'</style><section class="directory" aria-label="Judicial directory">']
    groups = [('Duval', ['Duval']), ('Clay', ['Clay']), ('Nassau', ['Nassau']), ('St. Johns / Putnam', ['St. Johns','Putnam']), ('Baker / Union', ['Baker','Union'])]
    for page, page_groups in enumerate((groups[:1], groups[1:]), 1):
        page_rows=[j for j in judges if any(set(j['counties']) & set(cs) for _,cs in page_groups)]
        addresses=list(dict.fromkeys(j['address'] for j in page_rows))
        parts.append(f'<div class="directory-page"><h2>Judicial directory · {"Duval" if page==1 else "Clay · Nassau · St. Johns · Putnam · Baker · Union"}</h2>')
        parts.append(f'<p class="key">Public-source reference (not fixture data) · checked {escape(data["checked_on"])} · {page}/2 · C = circuit, K = county · P = individual procedures; J = judge page / procedures index; I = court index only.</p>')
        parts.append('<table><colgroup><col style="width:27%"><col style="width:20%"><col style="width:19%"><col style="width:27%"><col style="width:7%"></colgroup><thead><tr><th>Judge · court / address</th><th>Judicial assistant</th><th>Chambers / JA phone</th><th>JA email</th><th>Links</th></tr></thead><tbody>')
        for title, cs in page_groups:
            parts.append(f'<tr class="group"><td colspan="5">{escape(title)}</td></tr>')
            for j in (j for j in page_rows if set(j['counties']) & set(cs)):
                level='K' if 'County Court' in j['court'] else 'C'
                scope='' if len(cs)==1 else ' · '+('/'.join(c.replace('St. Johns','SJ').replace('Putnam','P').replace('Baker','B').replace('Union','U') for c in j['counties']))
                addr=addresses.index(j['address'])+1
                special=' †' if j['name'] in ('Nicole D. Saunders','Russell L. Healey','L. E. Hutton','Mose L. Floyd','Meredith Charbula') else ''
                proc=' '.join(link(p['url'],{'individual_procedure':'P','judge_page_procedure_index':'J','court_index_only':'I'}[p['type']]) for p in j['procedures'][:1])
                email=j['assistant_contact']
                email_html=link('mailto:'+email,email) if '@' in email and ' ' not in email else short(email)
                parts.append(f'<tr><td>{link(j["sources"][0],j["name"])} <small>{level}{scope} [{addr}]</small></td><td>{short(j["assistant"])}</td><td>{short(j["phone"])}{special}</td><td>{email_html}</td><td>{proc}</td></tr>')
        parts.append('</tbody></table>')
        parts.append('<p class="addresses"><b>Chambers mailing / location key:</b> '+' · '.join(f'[{i}] {escape(a)}' for i,a in enumerate(addresses,1))+'</p>')
        cs_page={c for _,cs in page_groups for c in cs}
        for c in clerks:
            if set(c['counties']) & cs_page:
                contact=c['contact']
                if contact.startswith('Contact page: '):
                    contact=link(contact.removeprefix('Contact page: '),'contact form / website')
                else: contact=escape(contact)
                parts.append(f'<p><b>{escape(c["counties"][0])} clerk: {link(c["sources"][0],c["name"])}</b> · {escape(c["phone"])} · {contact}</p>')
        parts.append('<p><b>Circuit orders / procedures:</b> '+' · '.join(link(c['administrative_orders_url'],c['name']) for c in circuits if set(c['counties']) & cs_page)+' · '+link('https://www.floridabar.org/rules/ctproc/','Statewide court rules')+'</p>')
        parts.append('<p class="key">Phones may be shared offices; Clay numbers (except Cox) may route through the clerk. Unverified = not confirmed in collected sources. Links are clickable.</p>')
        if page==1:
            parts.append('<p class="key">† Saunders and Healey: conflicting published emails, call to confirm. Hutton: alternate JA number 904-255-1269. Floyd: assistant also listed for Moran; confirm assignment.</p>')
        else:
            parts.append('<p class="key">† Charbula: judge 904-548-4921; listed number is JA. SJ/P = St. Johns/Putnam; B/U = Baker/Union; some circuit assignments are regional. McGillin PDF fetch returned 503; use judge-page link. Full clerk addresses / notes in electronic directory.</p>')
        parts.append('</div>')
    parts.append('<details class="directory-full"><summary>Full directory: all courts, addresses, source notes, and verification gaps</summary>')
    for e in sorted(data['entities'],key=lambda e:(e.get('court',''),e['name'])):
        parts.append('<article><h3>'+escape(e['name'])+'</h3>')
        for key in ('court','assignment_scope','phone','phone_type','assistant','assistant_contact','contact','address','notes','procedure_status','checked_on'):
            if e.get(key):parts.append(f'<p><b>{escape(key.replace("_"," ").title())}:</b> {escape(e[key])}</p>')
        parts.append('<p><b>Individual procedures:</b> '+' · '.join(link(p['url'],p.get('title','Procedures')+' ['+p['type']+']') for p in e.get('procedures',[]))+'</p>')
        parts.append('<p>'+' · '.join(link(u,'Official source '+str(i)) for i,u in enumerate(e['sources'],1))+'</p></article>')
    parts.append('</details></section>')
    return ''.join(parts)


def render_directory(data=None):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>FLWU Judicial Directory</title><body>'+render_appendix(data)+'</body></html>'
