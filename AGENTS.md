# Florida Litigator Weekly Update (FLWU) — Agent Instructions

## Project Overview

**FLWU** (Florida Litigator Weekly Update) is a Python package that automates
legal research for Florida litigation practice. It crawls and normalizes
Florida legal sources (statutes, bills, court decisions, DCA opinions,
circuit court orders, county clerk filings, and agency rules), detects
changes via semantic diff, and produces weekly HTML reports.

- **Package name**: `flwu` (Python import)
- **CLI entry point**: `flwu` (exposed via `pyproject.toml`)
- **Python**: 3.11+
- **State store**: SQLite (frozen schema v1, WAL mode, foreign keys enforced)
- **External calls**: None in fixture mode; production adapters use bounded HTTP (httpx)
- **Model**: Deterministic, rule-based (no cloud inference in production)

## Repository Layout

```
florida-litigator-weekly-update/
├── .git/
├── AGENTS.md                        # ← this file
├── README.md                        # User-facing readme
├── pyproject.toml                   # Poetry project config (C07)
├── requirements.lock                # Constraints lockfile (C11)
├── config/
│   ├── defaults.json                # Global config schema (C07)
│   ├── adapter_bindings.json        # Per-adapter HTTP limits (C10)
│   ├── sources.json                 # 60 source URL registry (C09)
│   └── public-export.json           # Publication policy (C36)
├── docs/
│   └── acceptance/
│       └── production-readiness.md  # Full integration checklist (C01–C40)
├── fixtures/
│   ├── README.md
│   ├── synthetic-source.json        # Test fixture (C08)
│   └── expected-identities.json     # Expected hash outputs (C06)
├── src/
│   └── flwu/
│       ├── __init__.py              # Package entry
│       ├── cli.py                   # CLI (C08) — preview, registry, fetch, etc.
│       ├── config.py                # Config loading + production enforcement (C07)
│       ├── records.py               # Record models + validators (C01)
│       ├── identity.py              # Deterministic IDs (C06)
│       ├── normalize.py             # Fixture → DocumentRecord (C02)
│       ├── diff.py                  # Semantic change detection (C03)
│       ├── state.py                 # SQLite state machine (C05)
│       ├── fetch.py                 # Bounded HTTP (C10)
│       ├── fixture_pipeline.py      # End-to-end pipeline (C08)
│       ├── inventory.py             # Search catalog (C35)
│       ├── roster.py                # Judge roster reconciliation (C31)
│       ├── model.py                 # Deterministic analysis (C32)
│       ├── analysis.py              # Job lifecycle (C33)
│       ├── orchestrator.py          # Weekly run (C34)
│       ├── sections.py              # Report sections (C34)
│       ├── search_index.py          # Search index (C35)
│       ├── site.py                  # Static site generation (C36)
│       ├── publish.py               # GitHub Pages publish (C39)
│       ├── release.py               # Release gating (C37)
│       ├── scheduler.py             # Schedule integration (C40)
│       ├── registry.py              # Source registry (C09)
│       ├── render.py                # HTML/Markdown render (C08)
│       ├── scope_docs.py            # Scope documentation (C09)
│       └── adapters/                # 20 source adapters (C11–C30)
│           ├── agency_rules.py
│           ├── circuit_eighth.py, circuit_fourth.py, circuit_seventh.py
│           ├── clerk_baker.py, clerk_clay.py, clerk_duval.py,
│           │      clerk_nassau.py, clerk_st_johns.py, clerk_union.py
│           ├── court_bar_rules.py
│           ├── dca_first.py…dca_sixth.py
│           ├── fl_bills.py
│           ├── fl_statutes.py
│           └── fl_supreme.py
├── tests/
│   ├── conftest.py
│   └── test_*.py                    # 101 tests (all pass)
└── website/
    └── assets/
        ├── site.css
        └── search.js
```

## Core Pipeline (C01–C08)

| Card | Module | Description |
|------|--------|-------------|
| C01 | `records.py` | Document record models; 30+ validated enums; strict validators |
| C02 | `normalize.py` | Fixture → validated DocumentRecord; stamps IDs; rejects synthetic=false |
| C03 | `diff.py` | Semantic diff: added, amended, withdrawn, superseded, unchanged |
| C04 | (reserved) | — |
| C05 | `state.py` | SQLite state machine: runs, attempts, documents, revisions, snapshots |
| C06 | `identity.py` | Deterministic IDs from inputs; no randomness; stable across time |
| C07 | `config.py` | Schema-validated config; production security enforcement |
| C08 | `cli.py` + `fixture_pipeline.py` | `flwu preview` — end-to-end fixture pipeline |

## Extended Cards (C09–C40)

| Card | Module | Description |
|------|--------|-------------|
| C09  | `registry.py`, `scope_docs.py` | Source registry (60 URLs); scope documentation |
| C10  | `fetch.py`, `adapter_bindings.json` | Bounded HTTP (pages, bytes, timeout, retries, spacing) |
| C11  | `requirements.lock` | Constraints lockfile |
| C12–C30 | `adapters/*.py` (20 files) | Source adapters for FL statutes, bills, DCA, circuits, clerks |
| C31  | `roster.py` | Judge roster reconciliation from verified records |
| C32  | `model.py` | Deterministic analysis (no cloud fallback) |
| C33  | `analysis.py` + `state.py` extensions | Analysis job lifecycle (enqueue, claim, finish, recover) |
| C34  | `orchestrator.py`, `sections.py` | Weekly orchestration; report sections |
| C35  | `inventory.py`, `search_index.py` | Search catalog and index |
| C36  | `site.py` | Static site generation (HTML/CSS/JS) |
| C37  | `release.py` | Release gating (manual/automated approval) |
| C39  | `publish.py` | GitHub Pages workflow |
| C40  | `scheduler.py` | Scheduled run integration |

## Testing

```bash
.venv/bin/python -m pytest tests/ -v
# 101 tests pass (C01–C08 coverage; C09–C40 acceptance criteria)
```

## Development Rules

1. **No external calls in fixture mode.** The pipeline is fully deterministic.
2. **Deterministic identity only.** Never use Python `hash()` or randomness for IDs.
3. **Preserve existing adapters.** Do not rename columns or loosen constraints.
4. **Clone adapters**, never modify existing ones. New sources get new files.
5. **Production mode** enforces `external_usd=0`, loopback-only model URL, no cloud fallback.
6. **Migrations are frozen.** Schema version 1 is the only supported version.

## CLI Usage

```bash
# Preview with synthetic fixture
flwu preview \
  --fixture fixtures/synthetic-source.json \
  --state-root /tmp/flwu_state \
  --output /tmp/flwu_output

# Future subcommands (stubs):
flwu registry  # Source registry management
flwu fetch     # Acquire source data
flwu analyze   # Run analysis jobs
flwu produce   # Produce report
flwu publish   # Publish to GitHub Pages
flwu schedule  # Schedule recurring runs
```

## Fixture Mode vs Production Mode

| Aspect | Fixture Mode | Production Mode |
|--------|-------------|-----------------|
| Data source | Synthetic JSON | Live HTTP adapters |
| Network | None | Bounded HTTP (per-adapter limits) |
| Model | Deterministic analysis | Same (no cloud fallback) |
| external_usd | 0 required | 0 required |
| state_root | Can be any path | Must not point to fixture |
| model.base_url | None | Loopback only (localhost/127.0.0.1) |
| Publication | Manual | Manual approval required |
