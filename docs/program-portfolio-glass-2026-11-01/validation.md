# Program Management portfolio — November 1, 2026

Program Management now uses the supplied light/dark portfolio references within the existing Django admin workspace. `/admin/programs` and `/admin/programs/` are aliases of the existing protected `/programs/manage/` view. The native Django admin, analytics dashboard, member directory, registration workflow and public site retain their existing routes and presentation.

## Delivered behavior

- Shared admin shell, themes and permissions; portfolio breadcrumb and title; existing program creation action. A compact toolbar replaces the original introductory heading and description; the Review approvals shortcut has been removed at the owner's request.
- Four live summaries, compact labeled filters, a featured first result, aligned two-column cards, and a sticky operations panel. Mobile uses full-width actions and a single-column board, with operations below it.
- Real category, publication status, public code, registration period, optional schedule, application count and capacity on each card. Unknown capacity and dates remain explicitly unspecified.
- Application demand is applications divided by stated capacity. Above-capacity percentages remain visible while the progress drawing caps at 100%. Available places and allocations still use the existing permission-checked `capacity_context` / `reserved_slots` calculation; applications never become allocated slots through this presentation.
- Portfolio capacity aggregates known-capacity programs without inflating slot totals through application joins. Applications to programs without a set capacity remain included in the application summary and are identified separately from the capacity denominator.
- The next deadline comes from the existing `accepting_applications` queryset, including its policy/publication rules. Upcoming programs are published programs starting in the next 30 days. Draft attention links to an existing record.
- Publication statuses remain Draft, Published, Cancelled and Archived. “Registration closed” is a derived filter/count for published programs whose registration deadline has passed, not a new stored status. Zero Cancelled/Archived counts are omitted from the compact operations list.
- Search, category/status, registration, sort and with-applications filters update the protected server-rendered results immediately without a document reload. Search waits 300 ms after typing and respects IME composition. Focus stays in the control; stale requests are cancelled/ignored; reset clears pagination; result counts are announced. Pagination and browser history retain query state.
- Recoverable request errors keep the existing list visible and expose retry feedback. Without JavaScript the original GET form and Apply filters button still work.
- No models, migrations, dependencies, authentication, API endpoint, business rules or stored records were changed.

## Files changed for this task

- `programs/portfolio.py`: read-only portfolio summaries, capacity presentation and operations context.
- `programs/views.py`: Program Management uses the new presentation context.
- `config/urls.py`: Program Management alias only; earlier member aliases preserved.
- `core/templatetags/workspace_navigation.py`: Program Management link and active state for the alias.
- `templates/admin_portal/dashboard_topbar.html`: portfolio-specific breadcrumb/title branch.
- `templates/programs/manage_list.html`: portfolio page composition.
- `templates/programs/portfolio/{base,metrics,filters,card,operations,results}.html`: reusable scoped templates.
- `static/css/program-portfolio.css`: portfolio-only glass surfaces, spacing, responsive layouts and accessible states using shared tokens.
- `static/js/program-portfolio.js`: scoped automatic asynchronous filtering; other admin forms retain their existing handlers.
- `programs/test_portfolio.py`, `programs/test_reference_ui.py`: live data, capacity, route, permissions, filtering and shared-card regressions.
- `scripts/program_portfolio_browser_qa.py`, `.cjs`: disposable synthetic browser fixtures and interaction/layout checks.
- `scripts/admin_filters_browser_qa.cjs`: adapts the existing admin-filter harness to Program Management's asynchronous results; other pages retain their navigation checks.
- This validation record and synthetic screenshots/results.

## Verification

- Django application/database system check: passed against the verified retained development connection.
- `makemigrations --check --dry-run`: no changes detected.
- Production static collection: 197 files collected into isolated `.local/program-portfolio-static-build`.
- JavaScript syntax checks and `git diff --check`: passed.
- Existing automatic-filter browser regression: 25 admin pages, 44 workflows passed; no POST requests or JavaScript errors. Includes dashboard dates, retained tabs/context, reference-loading exclusions and no-JavaScript fallback.
- Final focused run: **33 tests passed** across portfolio behavior, shared program cards, workspace navigation and the portfolio browser harness. Covers combined filters/pagination, aliases and active navigation, denied/read-only actions, true allocations versus demand, excess/missing capacity, unavailable deadline exclusion and asset scoping.
- Portfolio browser: **14 responsive checks passed**, at 1600, 1440, 1280, 1024, 768, 390 and 320 pixels in both themes. Verified featured-card spanning, equal paired-card heights, sticky operations, no horizontal overflow/duplicate IDs, persisted themes, keyboard focus, large text, high contrast, forced colors and reduced motion.
- Search/code lookup, category/status, registration/sort, reset, delayed stale responses, IME composition, request-error recovery and no-JavaScript fallback passed. Filtering caused no document reloads, POST requests or JavaScript errors.
- Desktop and mobile screenshots were visually reviewed in both themes. Chrome's offscreen glass layers are warmed by scrolling before full-page captures after viewport resizing; separate mobile viewport captures also verify the actual visible controls/cards.
- The local web process was refreshed successfully to reload cached templates and routing. Its verified retained MySQL process stayed running; no database restart or migration was performed.

All database tests use a separately verified disposable MySQL instance with synthetic records and model-synchronized schemas. They do not test historical migrations or target retained application data. Earlier unfinished Git changes remain preserved.

Commands:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_portfolio programs.test_reference_ui core.tests.test_workspace_navigation scripts.program_portfolio_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_portfolio scripts.program_portfolio_browser_qa scripts.admin_filters_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node --check static/js/program-portfolio.js
node --check scripts/program_portfolio_browser_qa.cjs
node --check scripts/admin_filters_browser_qa.cjs
git diff --check
```

The build used `collectstatic --noinput` through Django's management API with `STATIC_ROOT` overridden to the isolated directory. This repository has no React/Vite/TypeScript production build.

[Dark desktop](portfolio-dark-1600.png) · [Light desktop](portfolio-light-1600.png) · [Dark mobile](portfolio-dark-390.png) · [Light mobile](portfolio-light-390.png) · [Mobile card](portfolio-mobile-card-light.png) · [Sticky operations](portfolio-sticky-light.png)

[Portfolio browser results](browser-results.json) · [Admin filter regressions](admin-filter-regression-results.json)

All screenshots contain fictional test records only.

## Compact header follow-up

The owner subsequently requested removal of “Programs with purpose.”, its supporting description and the Review approvals button. The page now uses a compact toolbar with the small section label and Create program action. The page retains a visually hidden main heading. Obsolete hero styles were removed, mobile wrapping retained, and the stylesheet version was updated to refresh cached CSS. This is a presentation change; approval workflows themselves were not changed.

Changed `templates/programs/manage_list.html`, `templates/programs/portfolio/base.html`, `static/css/program-portfolio.css` and the existing route expectation in `programs/test_portfolio.py`. Both Program Management routes were rendered successfully with a database wrapper allowing SELECT statements only. Removed content was absent; Create program, filters and results remained present. Django system check, static asset collection (1 updated file, 196 unchanged) and diff whitespace checks passed. The local web app was refreshed without restarting MySQL. The earlier full regression results and screenshots above document the initial redesign, before this small header cleanup.
