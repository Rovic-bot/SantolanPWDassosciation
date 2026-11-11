# Ten-chart Admin overview validation — October 29, 2026

Implemented all ten requested chart assignments with populated synthetic fixtures.
The six headline metrics remain. The ten-chart inventory, exact data sources,
permissions, date scopes, count definitions and limitations are documented in
[inventory.md](inventory.md).

## Exact files changed by this update

Application and tests:

- `analytics/services.py` — monthly applications, eligibility by program,
  cumulative inputs, server-binned ages, closed-window capacity and event heatmap.
- `analytics/visualizations.py` — **new** aggregate-to-chart/table/legend projection.
- `analytics/tests.py` — richer isolated fixtures and seven additional chart tests.
- `templates/admin_portal/dashboard.html` — ten chart sections; six metrics retained.
- `templates/analytics/chart.html` — safe JSON, SVG hosts, semantic heatmap and tables.
- `static/css/dashboard.css` — responsive chart layout, colors, legends and scroll regions.
- `static/js/dashboard.js` — local responsive SVG renderer, table fallback and preference redraw.
- `scripts/dashboard_charts_browser.cjs` — **new** reproducible, GET-only browser harness.

Evidence: this file, `inventory.md`, and seven PNG captures in this directory.
Local-only fixtures under `.local/dashboard-charts-20261029/`: `before.html`,
`after.html`, `empty.html`, `filtered.html`, `expected.json`. Database artifacts
remain in the existing private disposable-runner directory. The prior overview
documentation records the earlier implementation; this inventory supersedes its
chart assignments. All unrelated unfinished Git changes were preserved.

## Actual test results

**98 tests passed in 14.523 seconds**, using a freshly initialized, verified
loopback native MySQL 8.4.11 instance and isolated `test_g12_disposable` database.
The database was destroyed after the run; no fixtures entered working data.

Command:

```text
.venv/Scripts/python.exe -B .local/deploy-compatibility-20261028/run_tests.py test analytics core.tests.test_foundation.AdminAccessTests assistance.tests.AssistanceTests programs.test_public_availability programs.test_revised_workflow ewaf.test_operational.OperationalTests.test_exact_calculation_predecessor_reasoned_decisions_and_separation ewaf.test_operational.OperationalTests.test_stale_sources_permissions_and_audit_rollback --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
```

After the final chart accessibility markup adjustment, the isolated
`analytics.tests.OverviewTests.test_render_privacy_tables_and_capture_synthetic_evidence`
test was repeated: **1 passed in 0.211 seconds**. Subsequent changes concerned
front-end clipping/scroll handling and explanatory footer copy; browser checks
were rerun successfully. This is not a claim that the entire repository suite or
every business workflow was tested.

The first 22-test analytics run had one fixture-order assertion failure for two
programs sharing the same closing time; the test now compares coordinate sets in
sorted order. The subsequent 98-test run passed. The previously reported public
Home wording and announcements-navigation tests were not changed or rerun as part
of this update; their previous limitations remain recorded in the prior report.

### Fixtures and reconciliations

- 3 current official members, including an inactive member; one archived official
  Member and one pending intake are excluded from the current count.
- Disability bars 2 / 1 / 1 across those 3 members, correctly retaining overlap
  and missing classification without duplicate legacy-FK/M2M counting.
- Monthly new memberships 1 / 1 / 0 / 0 / 0 / 2 produce cumulative area values
  **1 / 2 / 2 / 2 / 2 / 4**; no historical active-membership total is fabricated.
- Monthly program submissions **1 / 1 / 0 / 0 / 1 / 3** sum to 6 applications.
- 2 non-voided deliveries to **1** distinct recipient; a retained void is excluded.
- 3 program records partition into Draft 1 / Published 2, while only 1 program is
  currently accepting applications under existing rules.
- 5 Desk tickets partition into the five actual current states; each slice is 1
  ticket / 20%. A separate thirds fixture verifies rounded percentages sum to 100%.
- Eligibility stacks count 6 applications once across 3 programs. Tests include
  eligible, pending, needs-information, ineligible and no-review cases, with no
  selection/delivery stages included as extra populations.
- Scatter contains two closed programs with configured slots 10 and 20 and two
  full-window applications each. A one-day close-date filter can have zero
  submission-date applications yet retain both scatter points. Exact window-open
  submissions count; window-close submissions do not. Unknown capacity is excluded
  and counted separately. The query also explicitly requires closing time <=
  refresh time; no future closure is treated as already closed.
- Age bins verify exact-birthday age 10, day-before-birthday age 39, age 70,
  exclusion of archived age 100, and separate future-birthdate exclusion.
  Missing DOB count is supported; current schema makes DOB non-null, so no schema
  relaxation was performed to manufacture a missing-DOB record.
- Heatmap tests put UTC Sunday afternoon on Manila Monday, count a multiday event
  once, preserve Sunday/Monday distinctions and exclude AnnualObservance references.
- Backend assertions reconcile all ten table values to chart payloads, with
  permission suppression and no sensitive individual data in rendered HTML/JSON.

## Browser and accessibility checks

Command: `node scripts/dashboard_charts_browser.cjs` using installed headless Chrome.
The harness serves HTML rendered by the isolated fixture test and reads local
assets from the development site. Only local GETs are permitted. No external
requests, business writes or JavaScript errors occurred.

- Ten populated visualizations: nine SVG renderers plus one semantic heatmap.
  All ten tables match their expected server aggregates. Six metrics retained.
- Verified the actual SVG data-bearing shapes and scatter coordinates, not merely
  the presence of empty chart containers.
- 1440, 1024, 768, 390 and 320 CSS-pixel widths: no page-level horizontal overflow.
  At most two chart columns; stacked eligibility and heatmap get extra width.
- Native View data disclosures work with Enter, retain visible focus, and match
  chart values. Apply restores focus to the short filter confirmation.
- Chart text bounds checked for clipping at all five viewport sizes. An initial
  edge-clipping finding was fixed with internal SVG padding.
- 200% root text at 320 CSS pixels: labels redraw at 32px and charts remain
  available. Bounded chart/table scrolling avoids shrinking text; ArrowRight
  successfully scrolls the focused enlarged chart. No page overflow.
- High contrast updates SVG colors and retains readable legends. Measured minimum
  high-contrast legend text ratio: **8.47:1**. Reduced motion has no chart animation.
  Forced-colors mode retains labels/values and visible chart boundaries.
- JavaScript disabled: all ten data tables remain visible and usable, including
  the heatmap; no misleading zero or chart-dependency error replaces the data.
- Chrome's accessibility tree exposes the named chart and semantic table.
  Actual screen-reader speech/interaction and representative user testing:
  **Not Tested**. Native browser 400% zoom was **Not Tested**; 320 CSS-pixel reflow
  was checked. These checks are not a claim of complete WCAG 2.2 AA conformance.

## Screenshots

- [Desktop overview, 1440 px](overview-1440.png)
- [Mobile overview, 390 px](overview-390.png)
- [Filtered activity](filtered.png)
- [No matching activity, current snapshots retained](no-activity.png)
- [High contrast](high-contrast.png)
- [200% text at 320 CSS px](text-200-percent-320.png)
- [JavaScript-disabled tables](no-javascript.png)

Desktop and mobile captures were visually inspected. All screenshots use synthetic
counts/records rendered from the isolated test fixture, not working personal data.

## Read-only performance and remaining limits

Full-authority overview: **18 SELECT queries**. Five measured retained-development
view renders with all database writes blocked: **169.2, 64.1, 58.2, 57.6, 57.5 ms**;
median **58.2 ms**, roughly 44 KB HTML. Synthetic render measurements were 223.5 ms
in the focused suite and 111.2 ms in the final isolated render. These small local
measurements are not production-scale/concurrency guarantees.

Age bins are grouped in SQL; individual ages/DOBs are not selected into Python or
browser data. Heatmap aggregation uses bounded local-day CASE expressions in one
query, avoiding a dependency on installed MySQL named-timezone tables. No per-member
or per-event query loop, chart-service request, cache or new endpoint was added.

Django checks, migration drift check (`No changes detected`), JavaScript syntax
check and `git diff --check` passed. No schema/data migration was run.

All ten source definitions are supported. Truthful empty/restricted/unavailable
states and table fallbacks remain. The requested Chart.js reuse was not possible
because this repository has no installed Chart.js; local SVG/HTML is the documented
implementation choice. No unnecessary dependency/plugin was installed.

Existing business workflows, sidebar destinations, module actions, permissions,
feature flags, production settings and the accepted milestone remain unchanged.
No working business data modification, commit, push, merge or deployment occurred.
The local development server was refreshed for the changed templates/assets only.
