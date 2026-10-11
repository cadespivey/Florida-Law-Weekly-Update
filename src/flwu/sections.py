"""Report sections (C34)."""
SECTION_ORDER = [
    ("statutes", "Statutes"),
    ("case_law", "Case Law"),
    ("procedural_rules", "Procedural Rules"),
    ("local_rules", "Local Rules"),
]
def get_section_categories():
    return list(SECTION_ORDER)
