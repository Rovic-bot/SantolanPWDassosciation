# Disability chart doughnut — November 8, 2026

The owner requested a segmented doughnut like the Community Assistance Desk chart. The support-needs chart now displays every recorded category as a colored segment with a matching numbered legend. The center shows the distinct current-member count. The legend sits beside the ring when space allows and below it on narrower screens, without clipping or chart scrolling.

Ring angles use each category count divided by the sum of category counts. Legend percentages and the existing data table continue to use distinct current members. A visible note explains the difference because one member can have multiple classifications. Missing classification remains a separate category. Counts, source queries, archived-member exclusion and permission rules are unchanged.

Validation:

- All 25 analytics tests passed using `scripts/g12_test_runner.py test analytics --noinput` and a verified disposable native MySQL instance. Application data was excluded.
- `scripts/dashboard_disability_chart_qa.cjs` passed dark/light checks at 1440, 768, 390 and 320 px. All seven sample categories have matching segment and legend colors.
- Checked all ten catalog types plus missing classification, overlapping types, one category, empty data and 1% segments. Segment proportions total 100%; member percentages retain their original denominator.
- Data-table dialog, 200% text, high contrast, forced colors and no-JavaScript table fallback passed. No JavaScript errors, clipped chart text, horizontal chart scrolling or page overflow.
- JavaScript syntax and `git diff --check` passed. Desktop and mobile screenshots were inspected.

Screenshots and `results.json` use synthetic browser data. The development server was restarted to load the template and versioned assets. No migration, application-data change or submission was performed.

This supersedes the bar presentation in `../dashboard-disability-types-2026-11-08/validation.md` while preserving its member-count semantics.
