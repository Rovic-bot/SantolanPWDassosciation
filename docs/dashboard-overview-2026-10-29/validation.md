# Dashboard overview implementation and validation — October 29, 2026

Implemented the authorized analytics dashboard at the existing `/dashboard/`
route. It has six headline metrics and all six requested sections, with eight
server-rendered charts and matching accessible HTML data tables. Detailed source,
date, inclusion, exclusion, permission, and failure definitions are in
[definitions.md](definitions.md).

## Exact source files changed in this task

Added:

- `analytics/forms.py` — bounded date presets/custom range and timezone boundaries.
- `analytics/services.py` — module-scoped, database-level read-only aggregates.
- `analytics/tests.py` — synthetic source, privacy, authorization, date and rendering checks.
- `templates/analytics/chart.html` — visible charts and native View data tables.
- `templates/analytics/state.html` — restricted, unavailable and failed sources.
- `templates/analytics/undated.html` — missing date disclosure.
- `static/css/dashboard.css` — dashboard-only responsive layout and charts.
- `static/js/dashboard.js` — short filter completion/error focus handling.

Modified:

- `core/views.py` — validates dashboard filters and loads the aggregate projection.
- `templates/admin_portal/dashboard.html` — replaces the shortcut overview.
- `core/tests/test_foundation.py` — updates the authorized dashboard title assertion.

Documentation: this file and `definitions.md` in this directory. The eight PNG
files linked below are synthetic evidence, not application uploads. Local-only
harness artifacts under `.local/dashboard-overview-20261029/` are
`before-template.html`, `before.html`, `after.html`, `filtered.html`, `empty.html`,
`check_live.py`, and `verify.cjs`. They are not part of application behavior.
All unrelated pre-existing Git edits were preserved.

## Automated checks actually executed

The verified runner initialized fresh native MySQL 8.4.11 instances, checked the
loopback datadir/server identity and disposable `test_g12_disposable` database,
and removed the test database after each run. No synthetic database records were
inserted into the retained development database. Tests used the existing
`scripts.durable_test_runner.DurableTestRunner` with the local Windows runner.

Final focused run: **91 tests passed in 14.216 seconds**. Labels:

```text
analytics
core.tests.test_foundation.AdminAccessTests
assistance.tests.AssistanceTests
programs.test_public_availability
programs.test_revised_workflow
ewaf.test_operational.OperationalTests.test_exact_calculation_predecessor_reasoned_decisions_and_separation
ewaf.test_operational.OperationalTests.test_stale_sources_permissions_and_audit_rollback
```

After the dashboard-only top-bar wrapping adjustment, repeated the synthetic
render/privacy/evidence test: **1 test passed in 0.179 seconds**. No backend change
was made after the 91-test run. The two existing EWAF tests above actually ran;
this is not a claim that the complete EWAF or repository suite was run.

Fixtures reconcile to 3 current official members, 4 recorded joins in the period,
6 applications, 2 non-voided releases to 1 distinct recipient, 1 accepting program
among 3 program records, 2 scheduled Event records, and 5 Desk requests. One
pending membership intake and one archived member do not inflate the current
member total. The disability bars correctly show Visual 2, Deaf/Hard of Hearing 1,
and classification missing 1 across 3 members. M2M and legacy FK do not double count.
Eligibility totals cover the same 6 applications separately, including 3 with no
recorded eligibility review. One retained voided release is excluded; annual
observance reference content is not counted as scheduled events.

Checks also cover half-open Asia/Manila boundaries, DateField delivery dates,
leap-day/month boundaries, partial months, invalid/excessive ranges, future event
ranges, empty periods with unchanged snapshots, unknown states, missing date
handling, disabled sources, database source failures, no-permission source query
suppression, no dashboard permission, separately restricted eligibility, escaped
long classification labels, private-data absence, method restrictions and the
existing program availability rule with PDAO enforcement both off and on in tests.

All overview aggregation and measured template rendering ran inside a SQL wrapper
that rejects anything other than SELECT/SHOW/EXPLAIN. Browser requests were limited
to local GET requests. No mail, calculation, publication, selection, release,
attendance or registration service was invoked by the dashboard.

### Existing failures encountered in broader checks

An earlier 107-test run passed 106 tests and had one error:
`WorkspaceNavigationTests.test_results_preparation_navigation_requires_its_complete_existing_gate`.
It requests the existing `announcements:manage_list` route, then its helper fails
with IndexError because the expected sidebar markup is absent. This route and its
permission gates were not edited. Other navigation checks in that run passed.

The initial broader run also encountered the existing
`PublicFoundationTests.test_home_is_public_and_honest_about_unavailable_features`
wording expectation on the public Home page (no public Home edit in this task).
The first analytics fixture collided with an already seeded classification; that
fixture was corrected to reuse it before the successful runs. These earlier runs
are not described as passing suites. The two unrelated failures remain unresolved.

## Browser and accessibility evidence

Headless installed Chrome, actual Django templates rendered from the isolated
synthetic fixtures. Synthetic HTML responses were intercepted locally; styles,
scripts and logo came from the retained development server. No external service
requests or business POSTs were allowed; zero JavaScript errors.

- 1440, 1024, 768, 390, and 320 CSS-pixel layouts: six metrics and six sections,
  no page-level horizontal overflow, meaningful stacking order.
- Every chart's visible values matched its HTML table (eight pairs).
- Native View data disclosures opened/closed with Enter and visible focus.
- Apply returned focus to the short activity confirmation; filters and tables
  remain usable without JavaScript.
- Existing display controls changed chart colors directly; reduced motion has
  no animated chart content. Forced-colors emulation retained visible bars.
- 200% root text size at 320 CSS pixels: no horizontal overflow. The inherited
  top bar now wraps on this dashboard only. 320 CSS pixels also covers the reflow
  width corresponding to a 1280-pixel viewport at 400% zoom. Native browser UI
  zoom itself was **Not Tested**.
- High-contrast measured ratios against white: caption text **8.87:1**, bars
  **8.54:1**, input borders **4.29:1**. This is a targeted measurement, not a full
  contrast audit of the application shell.
- Chrome accessibility tree contained chart names and named data disclosures.
  Actual screen-reader speech/interaction and representative PWD user testing:
  **Not Tested**. No claim of complete WCAG 2.2 AA conformance.

Screenshots:

| State | Desktop | Mobile |
| --- | --- | --- |
| Before | [1440 px](before-1440.png) | [390 px](before-390.png) |
| After | [1440 px](after-1440.png) | [390 px](after-390.png) |

Additional captures: [Filtered one-day cohort](filtered-desktop.png),
[No period activity, current snapshots retained](no-activity-desktop.png),
[High contrast](high-contrast.png),
[200% text at 320 CSS px](text-200-percent-320.png).
Desktop, mobile, filtered and high-contrast captures were visually inspected.

## Performance and configuration checks

- Full-authority synthetic projection plus template: **14 SELECT queries**;
  21.0 ms in the focused suite and 79.8 ms in the later cold isolated render check.
- Five retained-site view renders with all writes blocked: **14 SELECT queries
  each**, 483.8, 23.6, 22.4, 24.3, 26.3 ms; median **24.3 ms**, about 34 KB HTML.
  The first run includes cold template/module loading. Small local datasets only;
  no production-scale concurrency/load guarantee.
- Django system check: no issues. Migration drift check: no changes detected.
- `git diff --check`: passed.

## Limits and scope

No new data collection was needed for the requested count analytics. Missing-date
coverage is disclosed without inventing history. Financial valuation, attendance,
historical status snapshots, and growth percentages are intentionally not inferred.
Desk analytics display Unavailable when the existing service flag is disabled;
the flag was not changed by this task.

Read-only backend aggregation code **was added**. Native HTML/CSS charts were used
because no chart library was installed. The old dashboard-only side column and
onsite shortcut were also removed to support the requested overview. The shell,
sidebar groups, routes and underlying module functionality were preserved; the
only shell presentation adjustment is dashboard-only wrapping at narrow widths.

No EWAF criteria/formulas/weights, evidence rules, ranking, selection, eligibility,
registration, release, publication, permissions, credentials or production settings
changed. No application schema/data migration, feature activation, dependency
installation, commit, push, merge or deployment. The recorded accepted milestone
remains unchanged. Local development server refresh is the only runtime restart.
