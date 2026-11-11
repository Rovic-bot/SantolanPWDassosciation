# Shared admin workspace theme — 1 November 2026

Applied the dashboard's midnight navy / pale blue palette, typography, reflective glass panels, rounded controls, and spacing across the existing eight admin navigation groups. Member records, programs/events, applications/verification, EWAF/selection, announcements/CMS, reports, and Django administration share the same header and theme control. Detail/edit pages, status badges, tables, dialogs, and native Django widgets receive the same treatment.

The existing `santolan-dashboard-theme` preference is reused across all admin destinations and related-object popups. First visits follow the system preference. The sidebar uses the dashboard's compact disclosures while retaining permission-aware destinations and existing section labels. Display preferences remain visible and readable in both themes.

The dashboard retains its compact layout, live queries, twelve charts, scrollable eligibility chart, stable scatter tooltips, and data dialogs. Public templates/styles, operational views/services, permissions, data, and feature availability were not changed for this extension. No dependencies or migrations were added.

## Files changed for this extension

- `static/css/admin-theme.css`: shared tokens, shell, controls, forms, panels, tables, feature-specific theme adapters, native admin widgets, responsive and accessibility rules.
- `static/css/dashboard.css`: moved shared theme/shell rules into the new common stylesheet; chart-specific rules stay here.
- `static/js/dashboard-theme.js`: retained theme behavior and preference key; clarified its shared-admin role.
- `templates/admin_portal/base.html`: loads the shared theme after feature styles and uses compact navigation.
- `templates/admin/base_site.html`: applies the same theme to native Django tools and related-object popups.
- `templates/partials/workspace_header.html` and `templates/admin_portal/dashboard_topbar.html`: one consistent header with visible theme and public-site buttons.
- `templates/admin_portal/dashboard.html`: inherits shared theme initialization without loading it twice.
- `scripts/admin_theme_fixtures.py`: disposable synthetic renders covering all groups, details, forms, native screens, and public isolation.
- `scripts/admin_theme_browser.cjs`: GET-only responsive, contrast, theme, keyboard, Display, and native-widget checks.
- `scripts/dashboard_themes_browser.cjs`: optional evidence output directory for the existing chart regression checks.
- `core/tests/test_workspace_navigation.py`: follows the already-existing notices redirect before asserting navigation permissions. No production routing change.

## Verification

- Django `check --database default --settings=config.current_development_settings`: passed.
- 45 tests passed in a fresh disposable MySQL instance: analytics, workspace navigation/permissions, shared theme rendering, and public-page isolation.
- 55 synthetic admin screens checked in dark and light themes at 1440, 1024, 768, 390, and 320 pixels: 550 layout checks with no page overflow or JavaScript errors.
- Final search-field spacing correction verified on six affected screens in both themes at the same five widths: 60 additional checks, including icon/text separation. [Full browser results](browser-results.json) and [final control checks](controls-results.json) are retained here.
- Text/control contrast checks cover theme/public-site/Display buttons, primary buttons, form controls, table headings, and status badges. Color-mixed surfaces are resolved as sRGB before comparison.
- Saved theme survives navigation between custom and native admin pages and reloads. Focus outlines, the native dual-list permission picker, Display high contrast, enlarged text, reduced motion, and mobile navigation were exercised without saving operational forms.
- Existing dashboard browser regression passed: chart/table aggregate consistency, modal focus/close behavior, five-row scrolling, scatter stability, responsive layouts, high contrast, reduced motion, 200% text, forced colors, and JavaScript-disabled fallback.
- Additional read-only renders of 43 screens against the retained local database passed both themes and five widths. Audited report/announcement views were tested in the disposable database instead of bypassing their audit behavior. Private captures remain in ignored `.local/`.
- `collectstatic --noinput` completed with an isolated `.local/admin-theme-static-build` destination. JavaScript syntax checks and `git diff --check` passed.
- Local web process refreshed on port 8013. Its existing database process and connection stayed running. The public homepage returned HTTP 200 without admin theme assets.

The application is Django; its deployment asset command is `collectstatic`, not a Vite/TypeScript build. An actual screen reader was not used. Screenshots below use fictional records from the disposable test database.

## Reproduce

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test analytics core.tests.test_workspace_navigation scripts.admin_theme_fixtures --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
$env:ADMIN_THEME_FIXTURES = '.local/admin-theme-synthetic'
$env:ADMIN_THEME_OUTPUT = '.local/admin-theme-synthetic-review'
node scripts/admin_theme_browser.cjs
$env:DASHBOARD_QA_OUTPUT = '.local/admin-theme-dashboard-regression'
node scripts/dashboard_themes_browser.cjs
```

The browser harness uses the existing local server at `http://127.0.0.1:8013` for static files only; document requests are fulfilled from synthetic fixtures. `ADMIN_THEME_BASE_URL` and `DASHBOARD_BASE_URL` can override that server.

## Synthetic screenshots

- [Programs — dark](programs-dark.png)
- [Programs — light](programs-light.png)
- [Members — mobile](members-mobile.png)
- [Administration — dark](administration-dark.png)
- [Reports — dark](reports-dark.png)
- [Membership reviews — light](membership-reviews-light.png)
