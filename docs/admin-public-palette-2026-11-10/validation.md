# Admin palette aligned with the public portal — November 10, 2026

The owner requested the public portal's existing light/dark palette throughout administration, readable text, and coordinated chart colours. This change is presentation only. No models, migrations, calculations, ranking, selection, publication rules, records, permissions or email services changed.

## Implementation

- Added `static/css/admin-palette.css`, loaded after feature styles by both `templates/admin_portal/base.html` and `templates/admin/base_site.html`. The palette is scoped to `.admin-workspace` and screen media; public pages and printed records retain their own styles.
- Matched the public palette in `static/css/public-bento.css` and `static/css/public-dark.css`. Light mode uses a warm paper canvas (`#e8e5df`), cream panels (`#f4f2ec`) and charcoal text (`#1c1a18`). Dark mode uses charcoal canvas/panels (`#191817` / `#242220`), cream text (`#f4f2ec`) and cream primary buttons (`#e6dfd2`). Small secondary light-mode text uses the stronger `#625d56`.
- Replaced fixed neon action gradients and page glows. Corrected action text, selected tabs, form placeholders, disabled controls, calendar dates, member portraits, record dialogs and report initials. Primary, hover, focus and disabled states use paired foreground/background colours.
- Retained semantic status colours. Charts use related sage, slate, plum, rose and ochre shades, adjusted for each theme. Twelve categorical colours support the membership breakdown; the heatmap uses a sequential sage scale. SVG labels, legends and table keys use corresponding readable foregrounds. Chart data and calculations remain unchanged.
- Retained the existing theme toggle, saved preference, high-contrast mode, forced-colour support, reduced motion, enlarged text and chart data tables.

## Verification

All data used for rendered fixtures and screenshots is synthetic. Django tests ran through `g12_test_runner.py` with `RegistrationIntakeTestRunner`, which verifies a fresh disposable MySQL instance. Browser document requests were served from captured fixtures; interactive checks never submitted operational forms. No real messages were sent.

| Check | Result |
| --- | --- |
| `scripts.admin_theme_fixtures` | 2 tests passed; 56 admin screens rendered; public routes exclude the admin palette |
| `analytics.tests.OverviewTests.test_render_privacy_tables_and_capture_synthetic_evidence` | Passed; generated current chart fixtures and expected aggregates |
| `node scripts/admin_palette_browser.cjs` | 336 screen/theme/width combinations passed: 56 screens × light/dark/high contrast × 1440/390 px |
| `node scripts/admin_palette_interactions.cjs` | 108 dialog and interaction states passed; chart data, member record, audit inspection, Display preferences, publication hover/focus and expanded panels |
| `node scripts/admin_theme_browser.cjs` (interactions only) | Theme persistence across custom/native admin and reload; keyboard focus; native permissions picker; high contrast; enlarged text; mobile navigation passed |
| `node scripts/dashboard_themes_browser.cjs` | Twelve charts and their tables matched expected aggregates; responsive layout, scrolling, scatter tooltips, modal focus/close behaviour, both themes, high contrast, reduced motion, 200% text, forced colours and no-JavaScript fallback passed |
| `node scripts/dashboard_disability_chart_qa.cjs` | Distinct categorical colours, matching legend colours, seven-category responsive sample, full eleven-category catalog, overlapping classifications, tiny segments, single/empty samples, percentages and accessible tables passed |
| `python scripts/current_development.py check` | No system-check issues |
| `git -c core.safecrlf=false diff --check` | Passed |

The text scanner checks visible non-decorative text, field values and placeholders against computed backgrounds at 4.5:1, or 3:1 for large text. It accounts for alpha/opacity and the SVG slice behind numbered chart labels. All 336 screen combinations and 108 interaction states had no detected low-contrast text, horizontal page overflow or JavaScript errors. Hidden accessible names, native progress fallback text and decorative `aria-hidden` artwork are excluded. Screenshots were also visually reviewed. This is not a full accessibility certification: the scanner does not model arbitrary uploaded photographs or every gradient/pseudo-element pixel, and an actual screen reader was not tested.

Existing browser harness expectations were updated for the current member-donut layout, its count-and-percentage legend, the current grid breakpoint, and automatic dashboard filters that retain focus on the date field. Those application behaviours were not changed by this task.

## Evidence

- [Screen checks](screen-checks.json), [dialog checks](dialog-checks.json), [theme interactions](theme-interactions.json), [chart category checks](chart-category-checks.json).
- [Dashboard light](dashboard-light.png), [dashboard dark](dashboard-dark.png), [high contrast](dashboard-high-contrast.png), [mobile](dashboard-mobile.png).
- [Onsite form light](onsite-form-light.png), [onsite form dark](onsite-form-dark.png), [member record](member-record-light.png), [audit inspection](audit-inspect-dark.png).
- [Chart colours light](chart-colors-light.png), [chart colours dark](chart-colors-dark.png).

The local system at `http://127.0.0.1:8013/` was restarted. The served palette stylesheet matches the local file byte-for-byte; the public home and admin login pages return 200 and do not load the admin-only stylesheet. No database migration or data cleanup was needed.
