# Public Announcements design — 26 October 2026

The owner requested the supplied Announcements UI: a clean heading, dated notice rows, search, a topic sidebar, a Results link and numbered pagination. The implementation adapts that reference to the existing Association branding and published data.

## Changes

- White page with a compact breadcrumb/header, clear heading hierarchy and thin row separators.
- Separate day/month-year date column, category and responsible office, linked title, short excerpt and aligned action link. Result notices retain their official Results destination; program notices retain the canonical program destination.
- Five notices per page, ordered by publication date with a stable identifier tie-break, and numbered pagination with a visible result range.
- Working search and topic navigation. Search/topic/program filters survive pagination; changing topics resets the page and category-specific filters.
- Existing disability-classification and program-category filters remain on the Programs topic. Unrestricted programs remain included, and filter matches do not establish eligibility.
- Responsive CSS moves topic navigation above the list on narrow screens. Accessible search labels, date semantics, keyboard focus, high-contrast settings and the shared reduced-motion behavior remain intact.

## Publication and privacy

The existing `Announcement.objects.published()` gate and `public_notice()` projection remain authoritative. Search targets general published title/content, canonical linked-program title/description, or the current authorized result title/description. It does not index legacy result content, copied program-notice text, applicant rows, member identifiers, references, private revision reasons or source digests.

Existing result details, participation tables, publication authorization, freshness checks, masking/disclosure rules, immutable revisions, application screening and scoring are unchanged. No business records, models, migrations, dependencies or global navigation were modified.

## Validation

- The initial 74-test source run passed 73 tests; one historical assertion required `datetime` to be the first attribute on the date element. That compatible markup order was retained.
- The final focused source run passed **8 tests**, including all six new board tests, the date/source/category regression and the new result-search privacy test.
- The retained development runtime passed **all 74 tests** across public board, category, public Results, existing announcement, result-publication and participation suites.
- Tests used fresh disposable MySQL instances with `DB_TEST_NAME=test_g12_disposable`, via the existing G12 launcher and `RegistrationIntakeTestRunner`. Test databases were destroyed afterward.
- Live GET-only HTTP checks passed for the redesigned board, search/empty search, topic navigation, numbered pagination, existing program filters, dates/search labels and the new stylesheet. Existing Programs and Results pages also responded successfully. These checks did not create, edit or publish business records.
- Changed Python syntax, Django system checks during tests, and `git diff --check` passed.
- Browser screenshot/visual QA was unavailable because browser launching is restricted in this session. Responsive styling is implemented but rendered viewport acceptance is not claimed.

Evidence: `source-focused-tests.log`, `runtime-tests.log`, `http-checks.json` and `source-test-summary.txt`.

## Files and local preview

New files: `announcements/public_board.py`, `announcements/test_public_board.py`, `templates/announcements/public_board.html` and `static/css/announcement-board.css`. Scoped changes update the public-list handler, the existing pagination assertion and the result-search regression test.

Seven runtime files were synchronized after verifying the captured baselines. Backups and installed hashes remain under ignored `.local/public-announcements-design-20261026/`. The earlier public-list template and unrelated runtime work are retained, so an older running process remains coherent until restarted.

The refreshed preview at **http://127.0.0.1:8000/announcements/** serves this design and the earlier Programs redesign. The agent-owned port-8000 process was restarted successfully. The normal port-8003 process requires a manual **Restart System.cmd** because Windows denied access to that process earlier in the session.
