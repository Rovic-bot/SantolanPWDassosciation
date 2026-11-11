# EWAF program-selection workspace — November 2, 2026

The owner-authorized redesign applies to `/admin/ewaf`. The existing `/ewaf/` entry remains available. The permission-filtered EWAF navigation now opens the admin alias. Other admin pages and the public website keep their existing layouts.

The page uses the shared light/dark theme tokens: a compact Configuration Vault action, a search/ranking-status toolbar, selectable program rows, and a sticky analysis rail. The owner subsequently removed the introductory heading/copy and four portfolio summary cards. Narrow screens use stacked rows and place analysis below the queue. The desktop rail scrolls independently so its configuration and generation actions remain reachable.

Search and status filters run immediately against the loaded program records; they do not reload the page or repeat evidence checks on each keystroke. Selection supports keyboard activation and exposes its selected state. Ordinary GET filters and selection links remain usable without JavaScript. No-match states include a clear-filters action.

## Preserved operational meaning

- Counts come from existing application reviews and beneficiary reservations. Missing capacity or capacity permission is explicitly distinguished from zero.
- Generation readiness calls the existing approved-configuration and complete-pool context services. The gauge shows the share of the two remaining program checks completed (eligible-pool review and assessment/cutoff), not an invented probability or EWAF score. Configuration is managed through the shared Vault rather than a repeated program-level warning.
- The analysis panel displays actual criterion names and approved AHP percentages, including the shared Vault weight identifier where applicable. The reference screenshot's illustrative criteria, weights, applicants, and scores were not installed as production policy or records.
- Generate and Regenerate post to the existing protected per-program workspace with its CSRF token, source context, and request key. The service still checks permissions, stale sources, cutoff, complete evidence, and immutable audit history. The UI does not calculate scores, retry uncertain POSTs automatically, approve policy, select beneficiaries, or publish results.
- A saved ranking preview shows the first three rows in the existing exact ranking order. True ties keep their ranks. Scores are rounded only for display. Stale runs are labeled for refresh; invalid retained calculations do not expose scores. Full ranking and scoring-explanation links retain their private routes.

The initial page validates loaded programs and their saved rankings. In the retained development dataset this took approximately 12 seconds; filters and program selection then operate locally without additional requests. Generation deliberately revalidates on the server. No scoring-service optimization or caching policy was introduced in this presentation change.

## Changed files

- `ewaf/selection_workspace.py`: read-only portfolio, readiness, and saved-ranking projection.
- `ewaf/operational_views.py`, `ewaf/program_cards.py`: use the workspace and expose existing weight-version metadata.
- `templates/ewaf/operational_programs.html`, `templates/ewaf/selection/{results,panel}.html`: program-first workspace. The unused metrics partial was removed in the follow-up.
- `static/css/ewaf-selection.css`, `static/js/ewaf-selection.js`: responsive glass styling and progressive interactions.
- `config/urls.py`, `core/templatetags/workspace_navigation.py`, `templates/admin_portal/dashboard_topbar.html`: scoped route, navigation, breadcrumb, and label.
- `ewaf/test_selection_workspace.py`, `ewaf/test_program_cards.py`, `scripts/ewaf_selection_browser_qa.{py,cjs}`: checks and updated legacy capacity-heading assertion.
- This note and synthetic screenshot evidence.

## Verification

30 distinct checks passed across the scoped runs: 18 existing navigation tests, six EWAF card/projection regressions, five new selection-workspace tests, and one full browser journey. The final combined EWAF/browser run passed all 12 cases in 65.233 seconds with no skips.

The browser checked 14 width/theme combinations (1600, 1440, 1280, 1024, 768, 390, and 320 pixels in both themes), overflow, duplicate IDs, accessible selection, immediate filtering with no extra page requests, empty states, disabled generation, reachable sticky analysis, enlarged text/high contrast, and no-JavaScript fallback. It generated and regenerated two real synthetic runs through the protected service, verified the top-three preview, and created no selection decisions. Desktop, mobile, and generated-preview screenshots were inspected.

All write tests used verified fresh disposable MySQL instances and synthetic applicants. Both retained EWAF entry routes rendered successfully under a SQL guard rejecting writes. Retained programs, approvals, applicant data, scores, rankings, decisions, and releases were not changed by the UI task. There are no new models, migrations, dependencies, scoring formulas, APIs, or external services.

System/database checks, Python/JavaScript syntax, and `git diff --check` passed. Production static collection built the two page assets. The local web process was refreshed independently of its retained database.

Initial checks caught missing public codes on draft fixtures and JavaScript form-name shadowing of the POST action. Both were fixed. A historical test's removed capacity heading was updated to assert the new queue heading; all other relevant assertions remain. Disposable artifacts: initial navigation/regression run `santolan-g12-tests-7rs_0ejn`; corrected regressions `santolan-g12-tests-nn_vg3l9`; first complete browser `santolan-g12-tests-_vx53fvg`; final combined verification `santolan-g12-tests-os7h6l5d`.

[Dark desktop](ewaf-dark.png) · [Light desktop](ewaf-light.png) · [Mobile](ewaf-mobile.png) · [Saved ranking preview](ewaf-preview.png)

## Compact workspace follow-up

Removed the EWAF eyebrow, large introductory heading and description, all four metric cards, and the “What needs attention” block. The queue filter is now labeled “Ranking status” and offers Ready and Pending scoring. Removed the per-program “Needs configuration” label, repeated configuration-completeness check, and unconfigured weight placeholders. Actual approved weights remain visible where the existing data source supplies them. The shared Vault action remains available.

The initial configuration projection and calculation eligibility remain unchanged; this UI cleanup does not bind or reapprove programs, change approved shared weights, or alter scores. The existing shared-configuration application workflow remains in place. Browser refresh no longer expects the removed metrics fragment.

All 12 focused EWAF and browser cases passed in 51.345 seconds, including 14 responsive theme/width combinations, immediate filters, and two protected ranking saves in disposable MySQL. The browser also verified absence of the removed hero, summary cards, warning block, and “Needs configuration” wording. Final artifact: `santolan-g12-tests-sfv7rg5r`. Screenshot evidence above was refreshed for the compact layout. Python/JavaScript syntax, system/database and whitespace checks passed; the CSS and JavaScript production assets were rebuilt and the local web process refreshed independently of its database.
