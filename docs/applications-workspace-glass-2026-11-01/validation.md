# Applications and Eligibility workspace - 1 November 2026

## Delivered behavior

`/admin/applications` and its trailing-slash variant now open the redesigned program-first workspace. The original `/workspace/applications/` route renders the same page. The existing Program Applications & Eligibility sidebar link points to the alias and remains active for the chooser and individual review routes. The eight existing admin groups, public site, dashboard, Program Management, Events, membership pages, program builder and native Django admin retain their existing layouts.

The page uses live Django records, shared light/dark theme tokens, a glass filter toolbar, four portfolio metrics, aligned two-column program cards and a sticky selected-program summary. The primary view contains programs and aggregate counts, never a combined list of unrelated applicants. Selecting a card immediately updates the preview, highlight, accessible pressed state and URL context. Review applications opens the existing selected-program review URL; it is a native disabled button for zero-application programs. Open program details retains the existing protected record route.

Search, assistance type and publication-status filters update via GET requests to the same protected HTML view without document reload. The existing additional registration, ordering and with-applications filters remain available. Text input is debounced and IME-aware. Obsolete requests are cancelled/ignored; errors retain visible results and offer retry. Matching counts are announced, selection is retained if still present in the filtered page, and a filtered-out selection falls back to a visible program. Empty results remove the preview and offer Clear filters. Pagination and browser history preserve filter/selection context. Native links and the GET form remain functional without JavaScript.

## Data and permission boundaries

- Total programs and applications cover all retained records, independently of current filters. Accepting applications uses the existing policy-aware `Program.objects.accepting_applications()` query.
- Eligibility rate is recorded Eligible outcomes divided by recorded Eligible plus Ineligible outcomes; pending/unreviewed cases are excluded from that denominator. Missing decided outcomes display an em dash. Rate and case-outcome details are omitted for users without `assistance.view_assistancecase` and labeled restricted.
- Application-status breakdowns retain current stored workflow states. New groups Pending Photo Verification; Under review groups Photo Verified and Eligibility Review; Eligible counts the stored Eligible state. Other nonzero states are shown under their existing labels, so all counts reconcile. Later states are not silently relabeled Eligible. Separate case-outcome text explicitly describes recorded findings.
- Applications divided by stated beneficiary capacity is labeled application demand. The true percentage/count remains visible above capacity while the bar/ring caps at 100%. Unallocated places use the same permission-checked reservation calculation as the existing portfolio and beneficiary-selection workflow. Submitting an application does not reserve a place. Missing capacity is explicitly unspecified, not zero. Actual unallocated places are never fabricated as capacity minus applications.
- Publication states remain Draft, Published, Cancelled and Archived. Registration closed is a derived filter on published programs with elapsed registration windows, not a new stored publication status. Philippine local dates are used for presentation.
- Existing route permissions are retained: workspace access, view program and view program application. Additional case/allocation data keeps its existing permission boundary. JSON embedded in the page includes only program metadata, aggregate counts and protected navigation URLs; no applicant identity, evidence, reference, review notes or tokens are serialized.
- No models, migrations, dependencies, authentication mechanisms, API endpoints, applicant-review decisions, eligibility policies, scores, rankings, selections or releases changed. This is a presentation change over existing data/services.

## Verification

- 34 focused Django tests passed: seven chooser tests, existing workspace-navigation tests and existing program-portfolio tests. Coverage includes aliases, GET/HEAD/no-store behavior, POST rejection, permissions, case/allocation privacy, totals and denominator accuracy, unavailable registration, demand versus allocation, complete status totals, zero-applicant actions, selection limited to current results, missing values, derived closed status, pagination, HTML/JSON escaping, and asset isolation on unrelated pages.
- The dedicated browser scenario passed at dark/light themes across 1600, 1440, 1280, 1024, 768, 390 and 320 pixels: 14 combinations. Mouse, Enter/Space selection, selected state, program-specific review links, zero-applicant disabled action, retained selection, search/code/category/status filters, empty states, over-capacity visuals, cancellation of stale results, IME, recoverable failures, history, keyboard focus, sticky preview, no horizontal overflow/duplicate IDs, high contrast/forced colors, reduced motion and JavaScript-disabled fallback were verified. No browser errors or write requests occurred.
- The existing global filter browser regression passed across 25 admin pages and 44 automatic-filter workflows, including the updated chooser. No POST requests or JavaScript errors occurred.
- Browser and Django checks used fresh disposable native MySQL instances via `scripts/g12_test_runner.py` with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`; all records/screenshots are synthetic. No tests were run against retained application data. The first chooser browser attempt exposed an incorrect test assumption about the existing downstream page heading; its program name is in the eyebrow. That assertion was corrected, and the complete scenario passed. The downstream review page was not changed.
- Read-only rendering returned HTTP 200 with no-store headers for all three chooser routes against the verified retained development database. An SQL wrapper blocked mutations during those checks.
- `manage.py check --database default`: passed. Migration drift check: no changes. Production asset collection: 203 assets into isolated `.local/application-workspace-static-build`. The repository is Django, so no Vite/TypeScript build applies.
- JavaScript syntax checks and `git diff --check` passed. Dark/light desktop and mobile screenshots were visually inspected. Full-page captures retain the fixed Display control at its viewport location.

## Files changed

- `programs/review_workspace.py`: typed, read-only program/capacity/status presentation and aggregate summaries.
- `core/workspace.py`: chooser renders the new page while keeping existing access decorators.
- `config/urls.py`: `/admin/applications` alias.
- `core/templatetags/workspace_navigation.py`: chooser link and active alias state.
- `templates/admin_portal/dashboard_topbar.html`: page-specific breadcrumb/title branch.
- `templates/programs/application_workspace/page.html`, `filters.html`, `results.html`, `card.html`, `selected.html`: scoped page components.
- `static/css/application-workspace.css`, `static/js/application-workspace.js`: scoped layout, themes, responsive behavior, selection and automatic filters.
- `programs/test_review_workspace.py`, `core/tests/test_workspace_navigation.py`: new coverage and updated empty-state text expectation.
- `scripts/application_workspace_browser_qa.py`, `scripts/application_workspace_browser_qa.cjs`: synthetic browser checks.
- `scripts/admin_filters_browser_qa.cjs`: recognizes the chooser's asynchronous filters in existing regression checks.
- This validation directory and screenshots/results. Earlier unfinished Git changes are preserved.

The local web process was refreshed after completion; its health check passed. The retained MySQL process ID and live connection remained unchanged. Open http://127.0.0.1:8013/admin/applications.
