# Florida Litigator Weekly Update

A Python package for generating weekly updates on Florida litigation matters.

## Installation

```bash
pip install flwu
```

## Usage

```bash
flwu --help
```

## License

All rights reserved.

## Judicial contact and procedure directory

The reviewed reference directory covers the Florida Supreme Court, all six
DCAs, and circuit/county judges serving **Duval, St. Johns, Putnam, Nassau,
Baker, Union, and Clay**. The initial research date is October 11, 2026.
It contains 163 judges/justices, 14 clerk offices, and three circuit
administrative-order indexes. The closing appendix contains the 84 trial judges;
the electronic directory also exposes the appellate contacts and full source notes.

```sh
flwu directory --database output/directory/flwu-directory.sqlite --output output/directory
flwu preview --fixture fixtures/synthetic-source.json \
  --state-root /tmp/flwu-preview-state --output output/weekly \
  --directory-db output/directory/flwu-directory.sqlite
```

`directory` imports the bundled reviewed data and exports HTML plus JSON. It uses
the frozen SQLite schema v1 without adding tables or changing validators.
Documents have source ID `flwu_judicial_directory`; each `roster` record's
`body_text` holds canonical JSON of one directory entity. This is a compiled
contact reference, not a verbatim court document or a legal-change finding.
`exact_sha256` describes that compiled JSON, not the linked court page.
Stable entity IDs are pinned in `src/flwu/data/judicial_directory.json`;
preserve them when changing names, assignments, contacts, or URLs.
Repeated imports reuse revisions, retain historical observations, and advance
the directory checkpoint atomically. Removed entities disappear from the current
snapshot but remain in history. Use `read_directory(connection)` to retrieve the
current snapshot; do not query all historical revisions as the current roster.

The report renderers and fixture preview append a two-page landscape Letter
county directory. Without `--directory-db`, preview uses the bundled reference;
with it, preview reads the selected database without writing to it. Programmatic
renderers accept the retrieved directory in `issue['directory']`. The Markdown
renderer includes an HTML appendix. Fixture research remains synthetic; the
appendix explicitly identifies its separate public-source reference data.

Procedure links distinguish individual documents from a judge page or general
court index. Individual procedures were located for 82 of 84 trial judges.
Current individual procedures remain unverified for Chief Judge Lance Day and
Meredith Charbula's Nassau assignment; older Charbula Duval procedures are not
represented as current Nassau procedures. McGillin's official page links a PDF
whose retrieval returned HTTP 503; his judge-page link is retained as a fallback.
Supplemental procedure links and source notes are available in the electronic
directory. Circuit indexes are discovery links, not a representation that every
order applies to every case. Contact gaps, shared phone numbers, and conflicting
published email addresses are labeled rather than inferred.

Updating the reference requires reviewing official sources, editing the bundled
JSON while retaining IDs, and running the import again. This command does not
recrawl sources or claim a fresh verification date. Existing live weekly
orchestration and the `produce`/`schedule` commands remain placeholders; this
change connects the directory to the working preview and report renderers.
