# Workspace tabs and membership layout — November 4, 2026

The owner requested tab changes without a full reload or automatic jump to the top; the onsite application status immediately above the application guide at the same width; removal of the onsite upload presentation hint; and removal of the redundant Association/PDAO inbox navigation, headings, introduction and Association process steps.

## Delivered behavior

- Custom administrator sidebar tabs, membership review entry links and inbox status tabs fetch fresh, permission-checked HTML and update the current document. Current scroll is retained, clamped only when the destination is shorter. Back and Forward work. Automatic GET filters also preserve focus and selection.
- Page scripts have an explicit lifecycle: old global listeners, observers, timers and requests are cleaned up, and destination controls are initialized once. Existing builder unsaved-change guards are retained. Requests use the normal server authorization; no private page HTML, registration values, or drafts are cached in browser storage. Leaving onsite registration still discards its in-memory draft.
- Network failures keep the current page and present readable feedback. Session expiry, denied access, public routes and native Django administration retain normal server navigation. Native administration is a separate layout; its tab links continue to use normal navigation. Existing POST actions, printing and explicit record-loading links keep their own workflow.
- Onsite status and application guide share a single column, in that order, on desktop and narrow layouts. The shared public form's upload guidance and server validation remain intact; its onsite-only copy and associated accessibility reference are omitted.
- Association and PDAO inboxes keep accessible, visually hidden page titles, filters, records and review actions. The requested visible navigation, descriptions, and Association three-step header are removed.

No model, migration, membership decision, EWAF formula, publication, or email delivery rule changed. Existing unfinished work remains in place.

## Validation

All database-backed tests used the G12 disposable native MySQL runner and `RegistrationIntakeTestRunner`; application data was not used as a test database.

The following 21 Django/browser tests passed across two focused runs:

- `membership.test_onsite_registration_alignment`, `membership.test_pdao_review`
- `scripts.admin_cleanup_browser_qa`, `scripts.member_directory_browser_qa`, `scripts.onsite_registration_browser_qa`, `scripts.ewaf_selection_browser_qa`
- `scripts.workspace_navigation_browser_qa`, `scripts.admin_filters_browser_qa`

The first run passed 19 tests; the new navigation fixture initially used an incompatible registration policy and failed during setup. Its fixture was corrected to use its intended synthetic policy, and both new navigation/filter tests then passed.

Browser evidence includes 25 tab/filter transitions within one browser document, retained scroll, Back/Forward, repeated theme initialization, unique element IDs, responsive status alignment at 1440/900/390 pixels, search focus retention, draft clearing, and failed-request recovery. The existing filter harness passed 42 workflows across 25 admin pages, with no POST requests or JavaScript errors. Existing member and ticket popups, onsite submission/approval, and protected EWAF generation checks also passed.

Additional checks passed: JavaScript syntax, Django database/system checks, migration dry-run (no changes), `git diff --check`, EWAF editor DOM regression, and the 2,500-case weight slider regression with six exact cascade examples.

Static assets were collected and only the identity-checked local web process was restarted. The retained MySQL instance and uploads remained running. Health and HTTP 200 checks confirmed the running server on port 8013 serves the updated scripts and stylesheet.

## Evidence

- [Desktop status and guide](onsite-1440.png)
- [Onsite after repeated tab switching](onsite-after-switching.png)
- [Navigation browser results](workspace-navigation-browser-results.json)
- [Automatic filter browser results](admin-filters-browser-results.json)
