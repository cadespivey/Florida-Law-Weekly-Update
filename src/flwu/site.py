"""Deterministic static archive; public builds read only reviewed public exports."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from datetime import datetime
from html import escape
from flwu.publication import validate_issue, safe_url

ASSETS = Path(__file__).parent / 'data' / 'web'


def navigation(page):
    """Official destinations restricted to the packaged research registry's scope."""
    groups = {row['group_id'] for row in json.loads((ASSETS.parent / 'sources.json').read_text())}
    sections, personnel = {}, {}
    for row in json.loads((ASSETS / 'courts.json').read_text()):
        if row['group_id'] in groups:
            url = escape(safe_url(row['url']), quote=True)
            label = escape(row['label'])
            resources = ''.join(
                f'<li><a href="{escape(safe_url(link["url"]), quote=True)}" '
                f'aria-label="{label}: {escape(link["label"], quote=True)}">{escape(link["label"])}</a></li>'
                for link in row.get('resources', [])
            )
            children = f'<ul class="county-resources">{resources}</ul>' if resources else ''
            sections.setdefault(row['category'], []).append(f'<li><a href="{url}">{label}</a>{children}</li>')
            court = escape(row['group_id'], quote=True)
            personnel.setdefault(row['category'], []).append(f'<li><a data-court="{court}" href="directory.html?court={court}">{label}</a></li>')
    def panel(items):
        return ''.join(f'<div class="{"county-section" if title == "County Courts" else "court-section"}"><h2>{escape(title)}</h2><ul>{"".join(links)}</ul></div>' for title, links in items.items())
    resources = ''.join(
        f'<li><a href="{escape(safe_url(link["url"]), quote=True)}">{escape(link["label"])}</a></li>'
        for link in json.loads((ASSETS / 'links.json').read_text())
    )
    current = ' aria-current="page"'
    return ('<nav class="site-nav" aria-label="Main navigation">'
            f'<a id="updates-link" href="./"{current if page == "updates" else ""}>Updates</a>'
            '<details class="court-menu"><summary>Courts</summary>'
            f'<div class="court-links">{panel(sections)}</div></details>'
            '<details class="personnel-menu"><summary>Personnel Directory</summary>'
            f'<div class="court-links"><a id="directory-link" href="directory.html"{current if page == "directory" else ""}>All covered courts</a>{panel(personnel)}</div></details>'
            '<details class="resources-menu"><summary>Links</summary>'
            f'<div class="court-links"><ul class="resource-links">{resources}</ul></div></details></nav>')


def build_site(archive, output, *, preview=False):
    archive, output = Path(archive).resolve(), Path(output).resolve()
    if not archive.is_dir():
        raise ValueError('Public archive directory does not exist')
    if output == archive or output in archive.parents or archive in output.parents:
        raise ValueError('Build output and source archive must be separate')
    if output.exists():
        raise ValueError('Use a new output directory; existing builds are preserved')
    issues, evidence = [], {}
    for path in sorted(archive.glob('*.json')):
        if path.is_symlink():
            raise ValueError('Archive symlinks are not permitted')
        issue = validate_issue(json.loads(path.read_text(encoding='utf-8')), preview=preview)
        if any(i['id'] == issue['id'] for i in issues):
            raise ValueError('Duplicate public issue ID')
        issues.append(issue)
        for record in [p for s in issue['sections'].values() for p in s['items']] + issue['directory']:
            for citation in record['citations']:
                relative = citation['url']
                if relative.startswith('evidence/'):
                    source = archive / relative
                    if (archive / 'evidence').is_symlink() or source.resolve().parent != (archive / 'evidence').resolve() or source.is_symlink():
                        raise ValueError('Invalid preview evidence path')
                    content = source.read_bytes()
                    if hashlib.sha256(content).hexdigest() != source.stem:
                        raise ValueError('Preview evidence checksum mismatch')
                    evidence[relative] = content
    issues.sort(key=lambda i: (i['window_end'], i['window_start'], datetime.fromisoformat(i['published_at'].replace('Z', '+00:00')), i['id']), reverse=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.flwu-site-', dir=output.parent) as staging:
        root = Path(staging) / 'site'
        (root / 'assets').mkdir(parents=True)
        for name in ('site.css', 'search.js'):
            shutil.copyfile(ASSETS / name, root / 'assets' / name)
        data = json.dumps({'preview': preview, 'issues': issues, 'courts': json.loads((ASSETS / 'courts.json').read_text())}, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')
        template = (ASSETS / 'index.html').read_text(encoding='utf-8').replace('<!--ARCHIVE-->', data)
        for page, filename in [('updates', 'index.html'), ('directory', 'directory.html')]:
            html = template.replace('<!--NAVIGATION-->', navigation(page)).replace('data-page="updates"', f'data-page="{page}"')
            if page == 'directory':
                html = html.replace('<title>Florida Law Weekly Update</title>', '<title>Court Personnel Directory — Florida Law Weekly Update</title>')
                html = html.replace('<!--PAGE-TITLE-->', '<h2 class="page-title">Personnel Directory</h2>')
                html = html.replace('In Florida’s legal system, justice is shaped by judges, who interpret the law, and court personnel, who oversee its administration. These are their updates... <em>Dun-dun.</em>', 'Court contacts, judicial assistants, and individual procedures.')
            (root / filename).write_text(html.replace('<!--PAGE-TITLE-->', ''), encoding='utf-8')
        (root / '.nojekyll').touch()
        for relative, content in evidence.items():
            target = root / relative
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(content)
        (root / 'procedures').mkdir()
        (root / 'procedures' / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=../directory.html"><title>Judicial directory</title><a href="../directory.html">Open the judicial directory</a></html>', encoding='utf-8')
        root.rename(output)
    return output


def generate_site(issue, inventory_rows, output_dir):
    """Legacy callers must now supply a complete public export."""
    validate_issue(issue, preview=issue.get('synthetic', False))
    if inventory_rows:
        raise ValueError('Put reviewed directory entries in the public issue export')
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary)
        (archive / 'issue.json').write_text(json.dumps(issue), encoding='utf-8')
        return build_site(archive, Path(output_dir) / 'public', preview=issue['synthetic'])


def _site_css():
    return (ASSETS / 'site.css').read_text(encoding='utf-8')


def _search_js():
    return (ASSETS / 'search.js').read_text(encoding='utf-8')
