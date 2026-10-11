"""Issue rendering for Florida Litigator Weekly Update.

Converts records, analyses, and diff results into HTML and Markdown output.
Fixture mode always adds a synthetic warning banner. Produces deterministic,
escaped output with the four required major headings.

Uses only records and analyses from fixture_pipeline; no live model calls.
"""

from __future__ import annotations

from typing import Any
import json
from flwu.directory_render import render_appendix


def render_issue(records: list[dict], analyses: list[dict], *, issue: dict) -> str:
    """Render an issue as escaped HTML.

    In fixture mode, adds the required H1 notice and four section headings.
    In production mode, still contains the four section headings but omits
    the synthetic warning.

    Every production item includes official identifier/citation, jurisdiction,
    source URL/pinpoint, dates/status, prior/new change where relevant,
    supported analysis and practice action.

    Returns escaped HTML string; never executes user content.
    """
    mode = issue.get("mode", "fixture")
    categories = _categorize(records, analyses)
    window_start = issue.get("window_start", "")
    window_end = issue.get("window_end", "")
    title = _escape(issue.get("title", "FLWU Report"))
    cutoff = issue.get("cutoff_utc", "N/A")

    parts = [
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n',
        '<meta charset="utf-8">\n',
        f'<title>{_escape(title)}</title>\n',
        '<style>\n',
        'body { font-family: system-ui, sans-serif; max-width: 860px; margin: 2em auto; line-height: 1.6; }\n',
        'h1 { color: #222; }\n',
        'h2 { border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }\n',
        '.synthetic-warning { background: #fff3cd; padding: 1em; border-left: 4px solid #ffc107; margin-bottom: 1em; }\n',
        '.record { border: 1px solid #e0e0e0; padding: 0.75em; margin: 0.75em 0; background: #fafafa; }\n',
        '.record h4 { margin: 0 0 0.3em 0; }\n',
        '.analysis { background: #f0f0f0; padding: 0.5em; margin: 0.3em 0; }\n',
        '.source-link { color: #0066cc; }\n',
        'table { border-collapse: collapse; width: 100%; }\n',
        'td, th { border: 1px solid #ddd; padding: 0.3em 0.5em; text-align: left; }\n',
        'footer { font-size: 0.85em; color: #666; }\n',
        '</style>\n</head>\n<body>\n',
    ]

    # Synthetic warning (fixture mode only)
    if mode == "fixture":
        parts.append('<h1 class="synthetic-warning">SYNTHETIC FIXTURE PREVIEW — NOT LEGAL RESEARCH</h1>\n')

    # Report header
    parts.extend([
        f'<h2 id="report-header">{_escape(title)}</h2>\n',
        f'<p><strong>Window:</strong> {_escape(window_start)} to {_escape(window_end)}</p>\n',
        f'<p><strong>Cutoff:</strong> {_escape(cutoff)}</p>\n',
        f'<p><strong>Mode:</strong> {_escape(mode)}</p>\n',
    ])

    # Four major headings with sections
    section_defs = [
        ("Statutes", "statutes"),
        ("Case Law", "case_law"),
        ("Procedural Rules", "procedural_rules"),
        ("Local Rules", "local_rules"),
    ]

    for heading_name, heading_id in section_defs:
        section_records = categories.get(heading_id, [])
        parts.append(f'<h2 id="{heading_id}">{_escape(heading_name)}</h2>\n')
        parts.append(f'<div class="section" id="{heading_id}-section">\n')

        if not section_records:
            parts.append(f'<p>No {heading_id.replace("_", " ")} in this report window.</p>\n')
        else:
            for rec, anas in section_records:
                parts.append(_render_record(rec, anas))
            parts.append('\n')

        parts.append('</div>\n')

    # Footer
    parts.extend([
        '<hr>\n',
        '<footer>',
        '<p>Florida Litigator Weekly Update generated pipeline output.</p>',
        '<p>This is a machine-generated informational publication. ',
        'It is not a substitute for professional legal advice.</p>',
        '</footer>\n',
        render_appendix(issue.get('directory')),
        '</body>\n</html>\n',
    ])

    return "".join(parts)


def render_markdown_issue(records: list[dict], analyses: list[dict], *, issue: dict) -> str:
    """Render an issue as Markdown text.

    Uses the same evidence as render_issue but outputs Markdown with
    four headings instead of HTML.
    """
    mode = issue.get("mode", "fixture")
    categories = _categorize(records, analyses)

    parts = [
        "# ", _escape(issue.get("title", "FLWU Report")), "\n\n",
    ]

    if mode == "fixture":
        parts.extend([
            "> **SYNTHETIC FIXTURE PREVIEW — NOT LEGAL RESEARCH**\n\n",
        ])

    parts.extend([
        f"**Window:** {_escape(issue.get('window_start', ''))} to {_escape(issue.get('window_end', ''))}\n\n",
        f"**Cutoff:** {_escape(issue.get('cutoff_utc', 'N/A'))}\n\n",
    ])

    section_defs = [
        ("Statutes", "statutes"),
        ("Case Law", "case_law"),
        ("Procedural Rules", "procedural_rules"),
        ("Local Rules", "local_rules"),
    ]

    for heading_name, heading_id in section_defs:
        section_records = categories.get(heading_id, [])
        parts.append(f"## {_escape(heading_name)}\n\n")

        if not section_records:
            parts.append(f"No {heading_id.replace('_', ' ')} in this report window.\n\n")
        else:
            for rec, anas in section_records:
                parts.append(_render_markdown_record(rec, anas))
            parts.append("\n")

    parts.append("---\n")
    parts.append("*Florida Litigator Weekly Update — machine-generated informational publication.*\n")

    parts.append(render_appendix(issue.get("directory")))
    return "".join(parts)


def _categorize(records: list[dict], analyses: list[dict]) -> dict[str, list[dict]]:
    """Categorize records into standard issue sections."""
    categories = {"statutes": [], "case_law": [], "procedural_rules": [], "local_rules": []}

    analysis_map = {}
    for ana in analyses:
        rev_id = ana.get("revision_id")
        if rev_id:
            analysis_map.setdefault(rev_id, []).append(ana)

    for rec in records:
        record_data = json.loads(rec["record_json"]) if isinstance(rec["record_json"], str) else rec["record_json"]
        kind = record_data.get("kind", "")
        if kind in ("statute", "bill"):
            categories["statutes"].append((rec, analysis_map.get(rec.get("revision_id"), [])))
        elif kind == "case":
            categories["case_law"].append((rec, analysis_map.get(rec.get("revision_id"), [])))
        elif kind in ("court_rule", "agency_rule"):
            categories["procedural_rules"].append((rec, analysis_map.get(rec.get("revision_id"), [])))
        else:
            categories["local_rules"].append((rec, analysis_map.get(rec.get("revision_id"), [])))

    return categories


def _render_categories(categories: dict, mode: str) -> str:
    """Render categorized records as HTML string."""
    section_defs = [
        ("Statutes", "statutes"),
        ("Case Law", "case_law"),
        ("Procedural Rules", "procedural_rules"),
        ("Local Rules", "local_rules"),
    ]

    parts = []
    for heading_name, heading_id in section_defs:
        section_records = categories.get(heading_id, [])
        parts.append(f'<h2 id="{heading_id}">{_escape(heading_name)}</h2>\n')
        parts.append(f'<div class="section" id="{heading_id}-section">\n')

        if not section_records:
            parts.append(f'<p>No {heading_id.replace("_", " ")} in this report window.</p>\n')
        else:
            for rec, anas in section_records:
                parts.append(_render_record(rec, anas))
            parts.append('\n')

        parts.append('</div>\n')

    return "".join(parts)


def _render_record(rec: dict, analyses: list[dict]) -> str:
    """Render a single record as HTML."""
    rd = json.loads(rec["record_json"]) if isinstance(rec.get("record_json"), str) else rec.get("record_json", {})
    parts = ['<div class="record">\n']
    parts.append(f'<h4>{_escape(rd.get("title", "Untitled"))}</h4>\n')
    parts.append(f'<p><em>Kind:</em> {_escape(rd.get("kind", ""))}</p>\n')
    parts.append(f'<p><em>Status:</em> {_escape(rd.get("legal_status", "unknown"))}</p>\n')

    pub_date = rd.get("publication_date")
    if pub_date:
        parts.append(f'<p><em>Published:</em> {_escape(str(pub_date))}</p>\n')

    eff_date = rec.get("effective_date")
    if eff_date:
        parts.append(f'<p><em>Effective:</em> {_escape(str(eff_date))}</p>\n')

    if rd.get("body_text"):
        parts.append(f'<p>{_escape(rd["body_text"])}</p>\n')

    if rd.get("canonical_url"):
        url = _escape(rd["canonical_url"])
        parts.append(f'<p><a href="{url}" class="source-link">{url}</a></p>\n')

    # Render analyses
    for ana in analyses:
        parts.append('<div class="analysis">\n')
        parts.append(f'<p><em>Analysis:</em> {(_escape(str(ana.get("result", ""))))}</p>\n')
        parts.append('</div>\n')

    parts.append('</div>\n')
    return "".join(parts)


def _render_markdown_record(rec: dict, analyses: list[dict]) -> str:
    """Render a single record as Markdown."""
    rd = json.loads(rec["record_json"]) if isinstance(rec.get("record_json"), str) else rec.get("record_json", {})
    parts = [
        f"### {_escape(rd.get('title', 'Untitled'))}\n\n",
        f"*Kind:* {_escape(rd.get('kind', ''))}\n",
        f"*Status:* {_escape(rd.get('legal_status', 'unknown'))}\n",
    ]

    pub_date = rd.get("publication_date")
    if pub_date:
        parts.append(f"*Published:* {_escape(str(pub_date))}\n")

    eff_date = rec.get("effective_date")
    if eff_date:
        parts.append(f"*Effective:* {_escape(str(eff_date))}\n")

    if rec.get("body_text"):
        parts.append(f"{_escape(rec['body_text'])}\n")

    if rec.get("canonical_url"):
        url = _escape(rec["canonical_url"])
        parts.append(f"[{url}]({url})\n")

    for ana in analyses:
        parts.append(f"  - **Analysis:** {(_escape(str(ana.get('result', ''))))}\n")

    parts.append("\n")
    return "".join(parts)


def _escape(text: str) -> str:
    """Escape HTML special characters for safe embedding."""
    if not isinstance(text, str):
        text = str(text)
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;"))
