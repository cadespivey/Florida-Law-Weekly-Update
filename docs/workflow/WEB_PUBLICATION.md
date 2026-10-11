# Website publication contract and operating procedure

The website is a static view of reviewed research snapshots. It does not perform
new legal analysis when a reader changes dates. Its public archive is separate
from the private cumulative research database.

## Reader behavior and design

- Default: the reporting period with the latest end date, then latest start date,
  then latest publication timestamp. Filesystem modification time is irrelevant.
- Date range: inclusive reporting-period overlap, not individual opinion dates.
  Both dates are required. Reversed or invalid dates return an explanatory message.
- Date controls occupy a subtle shaded band without surrounding divider lines.
  Use equal-width fields and buttons, 14px labels/control text and 44px control
  heights; reflow to two columns, then one on narrow screens. The first report
  heading below this band has no additional top divider.
- Render each selected report's summaries beneath Statutes, Case Law, Procedural
  Rules, and Local Rules. Show the selected reporting period once in a compact
  14px line directly below the site description, before the date controls. Do not
  repeat reporting-period labels within sections or entries. Preserve individual
  publication/effective dates. Show individual-period navigation links only when
  multiple periods match. In case-law summaries, bold the line-leading Holding:,
  Disposition: and Author: labels while keeping their following text normal weight.
  Display only deduplicated source links, not quoted-source panels or
  excerpts. Keep quotations in the underlying evidence/archive for validation.
  Links open the original source webpage or exported saved source. Empty sections say no items were
  included; they do not imply complete proof that no law changed.
- Same-period revisions: display the latest published revision in range results;
  retain earlier revisions through `?issue=ID` links. Date ranges use
  `?from=YYYY-MM-DD&to=YYYY-MM-DD`. Reload, Back and Forward preserve selection.
- The personnel directory is a separate `directory.html` page, linked in the top
  masthead beside the site title. Navigation order is Updates, Courts, Personnel
  Directory. Both Courts and Personnel Directory are dropdowns; CourtListener
  remains accessible within Courts. The personnel dropdown supplies an all-courts
  view and individual `directory.html?court=GROUP-ID` links.
  The menu lists the Supreme Court, six DCAs, circuits 4/7/8 and the seven counties
  in the packaged research registry. `data/web/courts.json` supplies their official
  destinations; registry group membership limits the menu's scope. These links
  describe configured research coverage, not proof of completed source review.
  Court-specific county pages were discovered through the official circuit sites.
- The directory page uses the newest selected issue's saved snapshot. Selecting
  one older issue shows its contacts and personal/governing procedures. Do not
  merge current contacts into historical results. Navigation between Updates and
  Directory preserves the date-range or individual-issue query parameters. The
  update page itself renders only the four research sections.
- Personnel records render as a six-column table: personnel, court/county,
  chambers/office, judicial assistant, procedures/rules, and sources. On narrow
  screens each record becomes labeled rows without horizontal clipping.
  County selections match county assignments; circuit selections show personnel
  serving covered counties in that circuit (including county courts and clerks),
  explicitly described on the page. Appellate selections require `court_ids`
  derived from the saved `roster-supreme` / `roster-dca-N` inventory membership;
  never infer a person's court from a cited appellate opinion. Old exports without
  appellate assignment metadata show a qualified empty view, not invented people.
  Date submission, reset and individual-issue links preserve the court filter.
- Body system-ui/sans-serif 16px, report title/main headings 24px, item headings
  16px bold, footer 0.85em, matching the original weekly HTML report. Directory
  retains Arial, 16px heading, 11px contact text and 10px explanatory text.
- Use a restrained single column, left alignment, whitespace between paragraphs,
  and plain underlined links. No external fonts, analytics or framework runtime.
  Guidance: Butterick's [line length](https://typographyforlawyers.com/line-length.html),
  [headings](https://typographyforlawyers.com/headings.html),
  [paragraph spacing](https://practicaltypography.com/space-between-paragraphs.html)
  and [browser alignment](https://practicaltypography.com/justified-text.html).

## Prepare one publishable issue

1. Complete the live research runbook. Each included candidate must have an
   explicit `section`: `statutes`, `case_law`, `procedural_rules`, or `local_rules`,
   plus a readable `title`, publication/effective dates, supported claim text and
   complete citations. Choose based on the document, not an ID prefix. Save these
   fields in the candidate's source receipt before the final capture and review.
   Do not add sections or rewrite summaries inside exported JSON.
2. Check all roster-derived people, individual procedures, governing rules, and
   clerk/contact fields. County associations come from saved roster entities.
   A negative procedure search remains qualified as a search result.
3. Run `flwu research status --run-dir RUN --history-db DB`. Resolve missing tasks.
   Read the exact `capture_id` from `RUN/history-capture.json`.
4. Independently review the final document's legal content and appearance. Record
   that actual review, not an assertion generated by the model:

   ```sh
   flwu history finalize --database DB --capture-id CAPTURE --report REPORT.html --review 'Reviewer: completed legal and visual review; details in review record'
   flwu site export --database DB --capture-id CAPTURE --archive website/updates
   flwu publish --archive website/updates --output build/site-REVIEW-ID
   ```

5. Serve and inspect the exact built artifact. Read its latest issue, date filters,
   source links and directory. Obtain explicit publication authorization unless
   already provided for this concrete release. Stage only the reviewed export and
   intended code changes. Commit/push the authorized change to main. Do not
   publish private research workspaces, SQLite files, model prompts or raw dumps.

The exporter opens the database read-only; it does not finalize or mutate history.
It requires a complete finalized live capture, validates the saved final report's
hash and cited original/extracted bytes, and checks quotations. Public JSON has
an exact field allowlist, content checksum, capture ID and report hash. IDs are
immutable; a changed report requires a new reviewed capture. These checks establish
integrity and recorded approval, not source authenticity or legal entailment.
Review must ensure the exported claims also match the reviewed final document.

A build validates the entire archive before atomically creating a new output
directory. Existing builds are never deleted or overwritten. Only packaged web
assets, embedded public JSON and the directory redirect enter production builds.
An empty archive builds an honest “No reviewed updates have been published yet”
page. No trial is automatically promoted just to fill the page.

## GitHub Pages

`.github/workflows/pages.yml` tests and builds the public archive, uploads only
`build/site`, then deploys via `actions/deploy-pages`. PRs build/test without
publishing. Main changes to the archive or site code and manual workflow dispatch
can deploy. Repository Settings → Pages → Source must be **GitHub Actions**.
The deployment uses the `github-pages` environment; configure protection rules
there if each release needs a separate review. Preserve any existing protections.
See [GitHub's custom workflow instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

`flwu publish` builds the artifact; it does not push Git or change Pages settings.
The old `release.py` manifest API remains fail-closed and is not this publishing
path. `produce`, automatic live acquisition and scheduling remain separate,
unaccepted capabilities. Do not claim they became operational because Pages did.

## Synthetic preview and verification

Use a directory outside `website/updates` and explicit `--preview` on both steps:

```sh
flwu site export --database TRIAL_DB --capture-id CAPTURE --archive output/web-preview/archive --preview
flwu site build --archive output/web-preview/archive --output output/web-preview/site-NEW --preview
```

Previews omit the header banner at the user's request; synthetic flags remain in
the archive. Previews copy cited synthetic evidence into content-addressed local
text files. Production rejects synthetic or unfinalized
exports. Never commit preview data to the production archive. A manually authored
archive UI fixture must be labeled as such; it is not a historical research run.

Acceptance: run `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q`; build/install a
wheel outside the repository and build an empty production archive. In a browser
at a project subpath, check latest, one older period, multi-period range, inclusive
boundaries, reversed/invalid/empty range, reset, issue link, Back/Forward/reload,
source links (without quoted-source panels), historical directory identity, keyboard labels,
320px mobile width and desktop computed fonts. Check console/network failures.
Inspect screenshots. Publication success additionally requires an observed green
Actions deployment and an HTTP/browser check of the live URL; local tests alone
must never be reported as live deployment.
