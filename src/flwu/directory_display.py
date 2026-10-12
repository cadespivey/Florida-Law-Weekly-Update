"""Reviewed contact presentation; immutable research exports remain unchanged."""
from pathlib import Path
import json
import re
from flwu.publication import safe_url


def format_contacts(person, formats):
    """Exact source-value matches prevent old editorial formatting following new facts."""
    office, assistant = [], []
    def order(item):
        key=item[0].lower()
        return 0 if 'name' in key else 1 if 'phone' in key else 2 if 'fax' in key else 3 if 'contact' in key else 4
    for key, value in sorted(person['details'].items(), key=order):
        destination = assistant if 'assistant' in key.lower() else office
        category = 'addresses' if 'address' in key.lower() else 'names' if 'name' in key.lower() else 'contacts'
        reviewed = formats.get(category, {}).get(value)
        if reviewed is None:
            # Unknown/revised source text stays intact until its display is reviewed.
            destination.append({'label': key, 'lines': [value]})
        else:
            destination.extend(reviewed)
    # Keep one occurrence of each actual contact value, even when JA/chambers share it.
    seen = set()
    for rows in (office, assistant):
        unique = []
        for row in rows:
            identity = (row.get('type', row['label']), tuple(s.casefold() for s in row['lines']))
            if identity in seen:
                continue
            if row.get('href'):
                href = row['href']
                if href.startswith('mailto:'):
                    if not re.fullmatch(r'mailto:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',href):
                        raise ValueError('Invalid email link')
                elif href.startswith('tel:'):
                    if not re.fullmatch(r'tel:\d{7,15}',href):
                        raise ValueError('Invalid telephone link')
                else:
                    safe_url(href)
            seen.add(identity)
            unique.append(row)
        rows[:] = unique
    return {'office': office, 'assistant': assistant}


def load_formats():
    return json.loads((Path(__file__).parent/'data/web/directory-format.json').read_text())
