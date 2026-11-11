# Every recorded disability type in the dashboard — November 8, 2026

Replaced the largest-category progress ring with a colored horizontal bar for every category in the existing member aggregate. Each bar shows its count and share of current members. Missing classification remains a separate row. The chart grows to show every row without vertical chart scrolling, and the data table includes the same member-based percentages.

Multiple classifications can overlap, so each percentage uses the current member count and the shares may exceed 100% in total. Existing aggregation, archived-member exclusion, permissions and private-data protections are unchanged. No application data or schema was modified.

Validation:

- `scripts/g12_test_runner.py test analytics --noinput`: all 25 tests passed in disposable native MySQL, with application data excluded. The overlap fixture retains three members and four category memberships: 66.7%, 33.3%, 33.3%.
- `node scripts/dashboard_disability_chart_qa.cjs`: passed dark/light layouts at 1440, 768, 390 and 320 px; all seven sample categories; exact bar proportions; single-category and empty data; table/dialog access; 200% text; high contrast and forced colors; no-JavaScript table fallback. No JavaScript errors, clipped SVG text or page overflow.
- JavaScript syntax and `git diff --check`: passed.
- Desktop/mobile screenshots inspected. Screenshots use synthetic browser fixtures only, with matching synthetic headline, chart and table values.

The development server was restarted to load the new template and asset versions. Browser requests were read-only. This replaces the earlier single-category ring presentation while retaining the dashboard's source definitions.
