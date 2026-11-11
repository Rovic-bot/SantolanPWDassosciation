# Reference-inspired Admin dashboard — October 29, 2026

**Rolled back at the owner's request.** The previous dashboard design, navigation, chart renderer, and chart markup were restored. Only an asset cache-version change remains so browsers fetch the restored files. The experimental browser harness was removed. The notes and screenshots below are historical evidence of the reverted design, not the current interface. Earlier program and application fixes were preserved.

The owner requested the four supplied dark dashboard screenshots as visual references. This update applies that presentation to the existing Admin overview: dark navy panels, teal/cyan accents, six metric cards, rounded chart panels, compact desktop navigation, and the event heatmap. A persistent Light theme toggle is available on the dashboard. Existing high-contrast and enlarged-text preferences take priority.

The desktop navigation rail expands on hover or keyboard focus. It retains the existing permission-filtered destinations, disclosure state, collapse button, account controls, and mobile menu. All styling is scoped to the dashboard.

## Scope and data

The existing six metrics, ten chart assignments, date filters, count definitions, permissions, and table fallbacks remain. [The previous chart inventory](../dashboard-chart-variety-2026-10-29/inventory.md) continues to define their sources. No screenshot sample values, work-hour metric, speculative trends, or Gemini integration were introduced. No model, aggregation query, migration, publication rule, or application workflow changed in this update. Earlier unfinished work remains intact.

Eligibility bars now show shares within each program, with the exact application counts in the labels and table; the chart explains this normalization. Disability bars use a shared maximum-count scale. Metric accent lines are decorative, not percentages. The program status chart remains a pie chart and the Assistance Desk chart remains a donut, preserving the earlier ten-chart assignment.

Changes:

- `templates/admin_portal/dashboard.html`: header, theme toggle, asset version.
- `templates/analytics/chart.html`: share/count explanation and theme-neutral heatmap explanation.
- `static/css/dashboard.css`: dashboard themes, responsive cards, scoped navigation rail, chart and accessibility styling.
- `static/js/dashboard.js`: theme persistence, rounded bars, gradient area fill, thinner donut ring, row-based eligibility chart, bounded labels for overlapping scatter points.
- `scripts/dashboard_reference_browser.cjs`: GET-only browser validation adapted from the existing chart harness; historical validation artifacts are preserved.

## Validation

**22 analytics tests passed** in 1.173 seconds using a fresh, verified native MySQL 8.4.11 disposable database, separate from the application database. Test artifacts: `C:/Users/rovic/AppData/Local/Temp/santolan-g12-tests-ntmrlfz5`. The disposable database was destroyed after the run. The fixture render used 18 SELECT queries and took 53.8 ms. This is a focused test run, not the full repository suite.

```text
.venv/Scripts/python.exe scripts/g12_test_runner.py test analytics --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node scripts/dashboard_reference_browser.cjs
.venv/Scripts/python.exe manage.py check --database default --settings=config.current_development_settings
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=config.current_development_settings
git diff --check
```

The final browser run passed:

- Six metrics, nine SVG charts, one heatmap, and ten fallback tables; chart values and table cells reconcile to the synthetic server aggregates.
- 1852, 1440, 1024, 768, 390, and 320 px layouts, without page overflow or clipped chart text.
- Persistent dark/light theme toggle; desktop rail expansion by hover and keyboard; sidebar collapse/restore; mobile menu and Escape.
- Date filter submission and result focus, keyboard-operated data tables, empty-period rendering.
- High contrast (minimum legend text contrast 8.47:1), reduced motion, 200% text at 320 px with keyboard chart scrolling, forced colors, and JavaScript-disabled tables.
- No JavaScript errors, non-GET requests, or external requests. Accessibility-tree names were checked; an actual screen reader was not tested.

The current-data dashboard was additionally rendered through the actual view under a database wrapper permitting only SELECT/SHOW/SET, then inspected in Chrome at 1852, 1440, and 390 px. All ten charts rendered without page overflow, clipped text, or JavaScript errors. This found and corrected a scatter-label clipping issue for coincident program points. Current-data HTML and its screenshot stay under `.local/`; only synthetic fixture screenshots are included here. No member/application records or authentication sessions were modified by these checks.

Django configuration checks passed, and no missing migrations were detected. The verified local web process on port 8013 was restarted; the retained database process and data were preserved.

## Visual evidence

- [Desktop](dashboard-desktop.png)
- [Full desktop dashboard](overview-1852.png)
- [Mobile layout](overview-390.png)
- [Eligibility rows](eligibility.png)
- [Events heatmap](events-heatmap.png)
- [Keyboard navigation](keyboard-navigation.png)
- [Light theme](light-theme.png)
- [High contrast](high-contrast.png)
- [200% text at 320 px](text-200-percent-320.png)
- [No JavaScript](no-javascript.png)
- [Filtered](filtered.png)
- [No period activity](no-activity.png)
