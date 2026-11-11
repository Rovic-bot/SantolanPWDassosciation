# Public program results layout — 2026-11-10

## Follow-up: balance overview space

The owner requested less unused space beneath the overview. The desktop split is now approximately 57% overview / 43% program details, with the details arranged in two columns. This lets the taller details section fit without forcing a large blank area on the left. The existing small-screen stacked layout remains. Read-only browser inspection at 1440 px measured a 326 px section with only the intended 28 px bottom padding below the overview; 1920, 1024 and 390 px layouts also had no horizontal page overflow. Only CSS and its asset version changed; diff whitespace checks passed.

## Follow-up: compact result layout

The owner's latest reference replaces the top facts strip with a split overview and program-details section. Results now use a compact image header with a publication badge, title, publication date and organizing body. Overview, selection reason and privacy guidance sit on the left; complete registration/program dates, times, allocation and organizing body sit on the right. The records section places reference search and filters in one toolbar above the two tables, followed by a shared counts/claim-status footer.

The filtered results card, All-tab pop-up and both existing direct public detail routes reuse the result header and detail layout. General announcement cards retain their previous presentation. The portal's cream/charcoal palette, light/dark/high-contrast modes, title-initial fallback, one-card browsing and published-data boundaries remain in use. Current assistance-release status, reference search, copy controls and selection filtering are unchanged.

Read-only browser inspection confirmed the desktop split layout, stacking at 768/390/320 px, no horizontal page overflow, keyboard filtering, search/clear/no-match states in both tables, reference copying, pop-up footer access and closing, asynchronous topic switching, current receipt labels, direct result pages and readable no-JavaScript tables. Light, dark and high-contrast screenshots were inspected; the high-contrast records area uses white backing. No JavaScript or local HTTP errors were observed. Django system and diff whitespace checks passed. Private screenshots are in `.local/development/public-results-layout/revised-*.png`. No database records, publication revisions, scores or receipt records were changed by this work, and no automated test suite or fixture was run.

This supersedes the earlier layout descriptions below; the schedule, search and live claim-status behavior remain.

## Follow-up: current claim status

The owner reported that a recorded assistance receipt still showed Not reported publicly. The previous presentation read only the immutable publication snapshot, whose rows retain Selected after delivery. The owner explicitly requested that the public claim status reflect recorded receipts.

`announcements/public_claims.py` now adds a current receipt flag to a display-only copy of the authorized participation result. Its single query uses `AssistanceRelease.objects.successful()` (excludes voided receipts), the same program, and only exact references already present in the published selected list. It reads no private names or receipt details, does not add recipients, and does not rewrite publication history. Older result types retain their existing publication semantics. The board, pop-up and both direct public detail routes share this projection. Each page request rechecks the existing publication gate and reads current release status; no republication is needed.

Read-only verification against the existing records found 3 selected recipients, 1 active receipt and 2 without receipts. Reference ending 0001 now renders Received; the other two render Not recorded. This matched the database across all public result presentations and the reference search, with no JavaScript errors. Snapshot contents, receipt counts and revision counts stayed unchanged. Existing no-store response headers were confirmed. Void exclusion was checked in the query; no real receipt was voided to exercise it. Django system checks and diff checks passed; no automated test suites, synthetic records, migrations, emails or certificate actions were run.

This supersedes the original snapshot-only claim-status behavior described below.

## Follow-up: complete schedule and shared reference search

At the owner's request, the metadata now includes both registration and program date ranges, opening/closing or start/end times, and Philippine time (UTC+8). These public schedule fields come from the associated program so they match its Schedule & capacity section. Published result snapshots and their identity/decision data are not rewritten.

A labeled search filters both tables locally and combines with Selected Only. Full references are case-insensitive and whitespace-trimmed; numeric queries match the reference ending rather than the program number shared by every applicant. Clearing restores the rows; each table has a no-match message and live counts. No search requests or private lookups are made.

Read-only browser inspection confirmed the existing registration dates (Nov 10–19, 2026, 9 AM–5 PM), program dates (Nov 20–30, 2026, 9 AM–5 PM), full-reference and numeric-ending matches in both tables, combined filters, no matches, clearing, pop-up behavior and mobile layout. Django system checks, JavaScript syntax and diff whitespace checks passed. No database writes, synthetic records or automated test suites were used.

## Authorized change

The owner requested the supplied public-results layout: publication facts, program overview, highlighted selection explanation, privacy notice, and submitted/selected tables side by side with a selected-only filter. The existing full-width image/gradient card and swipe navigation remain. All-topic cards still open their existing pop-up; filtered Program Results still shows the complete result inline.

## Implementation

- Added `public_result_tags` and `announcements/public_result_details.html` to present an already-authorized public snapshot. The helper performs no database queries and does not mutate the snapshot.
- Reused the detailed presentation in the filtered card, announcement pop-up, and existing direct result/announcement links. Admin result previews and audit/history templates are unchanged.
- Added scoped `public-program-results.css` using the portal's cream/charcoal palette with amber selection guidance and a muted green recipient panel. The tables sit side by side on wide displays, stack in narrower containers, and use labeled rows on small phones.
- Added local Show All/Selected Only filtering, pressed states, keyboard activation, live feedback, and reference-copy controls. These operate only on information already rendered in the publication. Without JavaScript, both tables remain visible and inactive controls stay hidden.

## Data and workflow boundaries

The publication gate, published revision, and approved identity/reference projection remain authoritative. Current participation publications already permit masked names and full program application references under the existing October 25 implementation; this change does not widen that projection. Older revisions retain their published reference fragments and ambiguous-match guidance.

The page shows the saved **program schedule** and **beneficiary slots**, not an invented distribution schedule or quantity of goods. Selection reason and description come from the published revision. A selected applicant is not assumed to have received assistance: claim status is **Not reported** unless the published row explicitly records **Received**. No private release lookup, inferred pending pickup, new operational records, or publication changes were introduced.

## Verification

- `manage.py check --database default`: passed.
- `node --check` for both changed JavaScript files: passed.
- `git diff --check`: passed.
- Read-only database/render inspection of the existing published result: 3 applications and 3 selected entries; presentation retained the original snapshot and references.
- Browser inspection of the existing local public pages: desktop, 390 px and 320 px; light, dark, high contrast; filter buttons and keyboard activation; reference copying; All-tab pop-up/close; asynchronous topic switching; direct result and announcement links; JavaScript-disabled rendering. No JavaScript errors, local HTTP errors, or horizontal page overflow observed.
- Filter changes retained the mounted card. The filtered Program Results page still had one complete card with no pop-up trigger.
- Private screenshots and browser findings: `.local/development/public-results-layout/` (not committed).

No automated Django test suites, fixtures, synthetic records, migrations, emails, or certificate actions were run. The local development server was restarted to load the templates and new template-tag library.
