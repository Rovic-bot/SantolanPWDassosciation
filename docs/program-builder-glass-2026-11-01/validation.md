# Program creation workspace — 1 November 2026

The Create program action now opens `/admin/programs/create`, a guided program builder using the existing Django forms and audited save service. The existing `/programs/manage/new/` route renders the same creation interface. Program Management received only the requested Create program link update. Events, member pages, registration, the analytics dashboard, native administration, and the public website retain their layouts.

## Delivered behavior

- Five numbered sections: Identity, Schedule, Capacity, Eligibility, and Requirements. Sticky section navigation and live draft summary on desktop, horizontal section navigation on small screens, responsive grouped fields, and sticky Save draft / Review program actions.
- Existing admin colors, sidebar, theme persistence, typography, and glass treatments. The new-program breadcrumb and Program portfolio return action apply only to the builder.
- Two separate, Monday-first range calendars: blue registration window and violet program schedule. Month/year selectors, month navigation, keyboard arrows/Home/End/Page Up/Page Down (Shift changes years), start/end markers, inclusive range shading, times, Clear, and explicit Apply range are supported. Earlier second clicks reset the start; another click after a complete range starts a new range. Apply stays disabled for incomplete or invalid ranges. Date/time values remain Philippine wall time throughout submission.
- Native datetime fields remain usable when JavaScript is disabled; they are progressively replaced as the primary scheduling interface. The optional correction deadline remains available.
- Live title, category, capacity, EWAF/manual selection, privacy state, and six readiness items. Review validates the existing required fields and applied ranges, saves the private draft when needed, and opens an inline review-ready state with a link to the existing program review record. Setup readiness is not policy authorization or publication.
- Dynamic questions preserve the current response kinds: Written answer, Document upload, and Acknowledgement checkbox. Labels, instructions, required flags, removal, numbering, formset bounds, server errors, and existing requirement edit links are retained. No new answer type or category was invented.
- Save draft uses the existing protected POST and service transaction, with an HTML response for in-place refresh. The saved timestamp and record version come from the database. Later saves update that draft, require the existing change reason and permissions, and preserve audit history. Submitted questions become saved requirements instead of being submitted again. Reload resumes the saved draft through its existing edit URL with `?builder=1`; ordinary record editing keeps its original interface.
- Double clicks are ignored during a save. An unconfirmed network result disables further saves and asks staff to check the portfolio before retrying, avoiding a silent duplicate-create retry. Unsaved work receives the browser's normal leave-page protection. Input preview uses text nodes rather than injected HTML.

## Preserved boundaries

All fields and current choices come from `ProgramForm` and `NewRequirementFormSet`, including feature-flag-dependent purpose, selection, and identity-evidence requirements. Existing optional program-delivery dates and optional fields stay optional. Stored classifications, assistance categories, eligibility rules, private evidence, EWAF calculations/configuration, approval gates, and publication permissions are unchanged. Save and Review never publish, approve policies, calculate scores, or select beneficiaries. No model, migration, dependency, external API, authentication system, or new data store was added.

## Verification

- **18 focused Django tests passed:** eight new builder tests, nine portfolio tests, and the existing atomic program/inline-requirements save test. These cover aliases, all form fields, ordinary edit-page isolation, private status, audited updates, no duplicate requirements, stale versions, validation, transaction rollback, formset limits, permissions, CSRF, non-draft protection, and native form submission.
- After the visual cleanup, the eight builder tests passed again and the full builder browser scenario passed. The scenario performs two real saves against disposable synthetic data, confirms only one private program and three requirements exist, checks saved Philippine datetimes, and verifies the update audit reason.
- **14 responsive combinations passed:** dark and light at 1600, 1440, 1280, 1024, 768, 390, and 320 pixels. Browser checks include keyboard calendars, leap dates, reversed/same-day selections, time validation, Apply/Clear, live summaries, question addition/removal, stale validation cleanup, safe text preview, no horizontal page overflow or duplicate IDs, sticky controls, high contrast/forced colors, reduced motion, JavaScript-disabled fallback, no document reload during saving, duplicate-click protection, review readiness, persistence after reload, and uncertain-save handling. No JavaScript errors occurred.
- A separately selected older test, `ConfirmedApplicationTests.test_admin_can_create_ewaf_draft_and_open_settings_before_publication`, passes its creation/private-draft assertions but fails later at line 243 because the separate EWAF settings page does not contain the evidence-policy URL it expects. That unrelated EWAF template/workflow was not changed. This is recorded as an outstanding regression expectation, not a passing full-suite run. Only this test's old “Save program draft” label expectation was updated to the new “Save draft” label.
- `manage.py check --database default`: passed. `manage.py makemigrations --check --dry-run`: no changes detected. `collectstatic --noinput`: 201 assets collected into isolated `.local/program-builder-static-build`. The repository is Django, so no Vite/TypeScript build applies.
- `node --check` passed for both new JavaScript files. `git diff --check` passed.
- Database tests ran through `scripts/g12_test_runner.py` with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`, on fresh disposable MySQL instances with model-synchronized schemas. No historical migrations or test fixtures were run against application data.
- Final read-only rendering passed for all three creation-route variants against the retained application. Final asset collection copied the two updated assets with 199 unchanged. The local web process was refreshed and its health check passed; the retained MySQL process ID and live connection were unchanged. Open `http://127.0.0.1:8013/admin/programs/create`.

Evidence beside this file includes `browser-results.json`, both desktop/mobile themes, and calendar viewport screenshots. These contain fictional test data. Full-page screenshots show the sticky action bar at its viewport position; the remaining document extends below it. The final status-card label is “Draft status”; captures were made just before that text-only correction.

## Files changed for this task

- Routing and existing save-response presentation: `config/urls.py`, `programs/views.py`.
- Creation-only navigation context and return link: `core/templatetags/workspace_navigation.py`, `templates/admin_portal/dashboard_topbar.html`.
- Portfolio Create action target: `templates/programs/manage_list.html`.
- Builder components: `templates/programs/builder/page.html`, `field.html`, `calendar.html`, `question.html`, `summary.html`.
- Scoped styling and behavior: `static/css/program-builder.css`, `static/js/program-builder.js`.
- Tests: `programs/test_creation_builder.py`, `programs/test_portfolio.py`, `programs/test_application_workflow.py`, `scripts/program_builder_browser_qa.py`, `scripts/program_builder_browser_qa.cjs`.
- Validation evidence: this directory. All earlier unfinished changes remain preserved.

## Follow-up: compact schedule calendars

At the owner's request, reduced the calendar size to match the supplied reference. Removed the 1600px stacking cutoff: the two calendars now share a row whenever the form has room for readable controls. The grid is capped at 880px, day controls stay 38px on desktop instead of growing with column width, and calendar headings, selected-range text, time fields, and feedback use tighter spacing. Mobile retains 44px-tall day targets and stacked calendars. No date-selection or saving logic changed.

Changed `static/css/program-builder.css` and the stylesheet version in `templates/programs/builder/page.html`. Extended the existing browser harness to verify calendar dimensions and desktop alignment. The full browser scenario passed again across 14 theme/width combinations, including two private saves in the disposable database. At 1600px each calendar measured 393 × 594px; at 1440px, 316 × 594px. Dark and light screenshots were visually reviewed. See `compact-calendar-results.json` and `compact-calendars-{dark,light}-1440.png`.

Django checks, deployment asset collection (one stylesheet updated; 200 assets unchanged), and `git diff --check` passed. The local web process was refreshed and its health check passed while retained MySQL stayed running with the same process ID.

## Follow-up: remove correction-deadline control

Removed the correction-deadline label, visible input, explanation, and surrounding spacing from the creation builder. The field is carried as a hidden value so resuming and saving an existing draft does not erase an already recorded deadline. New drafts leave it blank. Ordinary record editing and correction policy are unchanged.

Updated `templates/programs/builder/page.html`, `templates/programs/builder/field.html`, and `static/css/program-builder.css`, with a new stylesheet version. Read-only rendering verified the control is absent on all three creation-route variants; an in-memory form round-trip verified retention of an existing date and time. Django checks, asset collection, and whitespace checks passed. The local web process was refreshed with the retained database process unchanged. Earlier calendar screenshots precede this field removal.


## Follow-up: one calendar with automatic ranges

Replaced the two calendars with one shared Monday-first calendar. Registration is blue and program delivery is violet, with separate labeled range selectors and retained dates/times for each. Both ranges are visible when they overlap: the active range has a filled band and the other has a thin colored track. Rounded caps cover endpoints and every week boundary. The calendar remains capped at 520px wide, with 44px-tall day controls and additional spacing below the time fields.

After a complete range, clicks alternate between editing start and end while preserving the other endpoint. The requested sequence is verified: November 1-10 becomes November 2-10, then November 2-7. Explicit Start date / End date buttons also allow choosing which endpoint to edit. A start after the previous end requires a new end; an earlier end selection becomes the new start, preserving a still-valid existing end. Incomplete or invalid date/time selections block saving instead of silently submitting previous dates. Valid ranges and time changes immediately populate the existing form fields and readiness checklist. Apply range and Clear actions were removed. Save draft still persists through the existing audited service; automatic application does not publish or create a record.

Changed only `templates/programs/builder/page.html`, `templates/programs/builder/calendar.html`, `static/css/program-builder.css`, `static/js/program-builder.js`, the existing `scripts/program_builder_browser_qa.cjs` harness, and this validation/evidence directory. The removed correction deadline remains hidden as before. Native datetime controls remain available without JavaScript; all backend fields, permissions, date validation, private-save behavior, and unrelated routes are unchanged.

Verification: eight builder tests and the updated browser integration scenario passed (9 tests total) on a fresh disposable MySQL database. The browser verified the exact alternating-date example, independent times, automatic form updates, overlapping ranges, rounded week caps, invalid time rejection, leap dates, keyboard use, native fallback, both themes at seven widths (14 combinations), no page overflow or duplicate IDs, sticky controls, and two actual private draft saves. Saved datetimes and audit records were confirmed by Django assertions. No browser JavaScript errors occurred. `node --check` passed for the application script and browser harness. Django database configuration checks passed; production asset collection updated two files with 199 unchanged. Whitespace checks passed. Evidence: `shared-calendar-results.json`, `shared-calendar-overlap-{dark,light}.png`, `shared-calendar-{dark,light}-1440.png`, and mobile captures. Captures retain the sticky action bar, which may overlay the viewport's lower edge.

The local web process was refreshed after these changes; its health check passed and the retained MySQL process and connection stayed running unchanged.


## Follow-up: date controls beside the calendar

Moved the registration/program selectors and Start date / End date controls into a right-hand panel beside the calendar. The calendar and time fields stay on the left. The controls align with the top of the calendar; a subtle divider separates the two areas. When the available content width is below 560px, the controls stack above the calendar to keep the day cells and fields readable. The combined workspace is capped at 880px. Date-selection and automatic update behavior are unchanged.

Changed `templates/programs/builder/calendar.html`, `templates/programs/builder/page.html` (stylesheet version), `static/css/program-builder.css`, and the existing browser layout assertions in `scripts/program_builder_browser_qa.cjs`. The browser scenario passed on disposable MySQL, including 14 width/theme combinations, right-side alignment and narrow-screen stacking, existing calendar interactions, and two private draft saves. Dark and light desktop screenshots were visually checked. Django checks and production asset collection passed (one stylesheet updated, 200 assets unchanged). Evidence: `calendar-sidebar-results.json` and `calendar-sidebar-{dark,light}-1440.png`.


## Follow-up: vertical date-control stack

The right-side schedule controls now form one full-width vertical stack: Registration window, Program schedule, Start date, then End date. Both control groups share the available height beside the calendar, removing the large unused area below them. Narrow-screen layout and date-selection behavior remain unchanged.

Only `static/css/program-builder.css` and the stylesheet version in `templates/programs/builder/page.html` changed, plus this evidence. The existing browser scenario passed across 14 theme/width combinations with two private draft saves on disposable MySQL. Both desktop themes were visually checked. Django checks and production asset collection passed (one updated stylesheet; 200 assets unchanged). Evidence: `calendar-vertical-controls-results.json` and `calendar-vertical-controls-{dark,light}.png`.

## Follow-up: shared create and edit workspace - November 2, 2026

Ordinary Edit program links now open the same builder used by Create program, including its shared range calendar, section navigation, requirements, and live summary. The existing record is prefilled and updates in place through the same audited save service. Editing uses an Edit program title/breadcrumb, Update program action, and Update status card. The card shows Up to date initially, Unsaved changes after editing, and Program updated after a confirmed update. The saved timestamp comes from the server. Initial creation still reports Draft saved before switching to edit mode. The title and top bar refresh alongside the saved form.

Removed the large creation introduction and replaced it with a compact Create program heading. Removed Other status changes from the draft publication card. Published records retain their existing reasoned status controls. The editor shows the actual publication status and visibility; it does not reset an existing record to a private draft. Published/approved terms remain protected by the existing service and form guards. The previous notice suggesting immediate published edits was corrected to explain those protections.

Changed files:

- `programs/views.py` (shared template routing and save-result context)
- `templates/programs/builder/page.html`, `summary.html`
- `templates/admin_portal/dashboard_topbar.html` (builder-only create/edit labels)
- `templates/programs/profile/operations.html`
- `static/css/program-builder.css`, `static/js/program-builder.js`
- `programs/test_creation_builder.py`, `programs/test_detail_workspace.py`
- `scripts/program_builder_browser_qa.cjs`
- This validation and screenshot evidence.

Verification: 15 focused Django tests passed, including audited draft updates, no duplicated requirements, stale versions, rollback, CSRF, permissions, and locked published terms. Both existing browser harnesses passed: 14 create layouts, six edit layouts, 14 standalone detail layouts, and 12 popup layouts across both themes. Real saves and publication/status actions used disposable synthetic data only. An initial regression assertion incorrectly expected published terms to be editable; it was corrected to verify the existing protection, without changing that protection. Final unit artifacts: `santolan-g12-tests-nzvnh53q`; browser artifacts: `santolan-g12-tests-4px1df9l`.

All 14 retained edit pages rendered with the shared builder under a read-only SQL guard. System/database checks, JavaScript syntax checks, and whitespace checks passed. Production static collection completed with two updated assets and 205 unchanged. Desktop and mobile screenshots were visually inspected.

[Edit in dark mode](edit-program-dark.png) · [Edit in light mode](edit-program-light.png) · [Mobile edit layout](edit-program-mobile.png)


## Follow-up: compact creation header ? November 5, 2026

Removed the visible Create program heading and its full-width header row from creation. The draft-status card now starts the right summary column; creation content has 1.25rem top padding. The edit-page heading and update status are preserved. An off-screen page heading retains screen-reader navigation. No fields, save logic, or business rules changed.

The two existing builder checks for creation/edit rendering and in-place draft saves passed on disposable MySQL. Django checks and template compilation passed, and static assets were collected. The local web process was refreshed. The browser showed the status card in the summary column; the final top-of-page inspection was limited by concurrent user interaction. Previous file versions are under `.local/program-header-cleanup-20261105/before/`.
