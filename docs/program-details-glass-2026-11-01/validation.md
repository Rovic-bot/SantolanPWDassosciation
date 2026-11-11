# Program Details operations profile - November 1, 2026

The existing protected Program Details view now follows the supplied operations-profile reference. It uses the project's Django templates, shared admin shell and theme tokens, with live program data. No dependencies, models, migrations, APIs or authentication systems were added.

## Delivered

- Program title/category/code, publication badge, updated time, existing edit action, real proposal PDF download and program-specific applicant review links.
- Four aligned summaries: application demand versus capacity, applicant count, registration dates/times and optional delivery dates/times. Philippine Standard Time is explicit.
- Five-stage lifecycle, grouped overview, structured eligibility/evidence requirements, expandable permission-checked history, and a sticky operations rail. History retains dates, actors, reasons, changes and pagination; it also works without JavaScript.
- Publication readiness, actual EWAF model/configuration/source/shared policy revision, and publication/status controls in the rail. Light/dark themes, keyboard focus, responsive stacking, readable status text and reduced-motion support use the existing admin system.
- `/admin/programs/detail?program=<uuid>` is an additional protected entry point, with or without the trailing slash. Missing selection returns to the portfolio; an invalid identifier returns 404. Existing named `/programs/manage/<uuid>/` routes and links from the portfolio and application chooser render the same redesigned page. Existing edit/review URLs retain the correct program context.
- Public pages and other admin designs are unchanged. The top-bar and navigation additions are scoped to this page/alias. Earlier unfinished Git work remains intact.

## Workflow and data boundaries

- All publication, withdrawal, authorization recovery, CSRF, permission, version, prerequisite and audit controls still use the existing forms/services. The primary button is labelled **Approve and publish**, submitting the existing `published` action. It does not simulate a publication in browser state. Other status changes still require their recorded reason and confirmation.
- Application demand is not allocated capacity. The progress bar caps at 100%, the real demand percentage and excess remain visible, and unallocated places come from the existing permission-checked reservation calculation.
- Readiness is a presentation summary, not a replacement for the authoritative publication service. Authorization is recorded by the existing publication action. Missing optional delivery dates and an unrestricted disability profile are not silently made mandatory. Conditional external approval stays hidden when enforcement is disabled.
- EWAF metadata is permission gated and read from the validated configuration. No sample 70-point eligibility threshold, tie breaker, scoring policy or government approval was invented. Approved weights with pending scoring rules retain that distinction.
- The model has no program-level Completed state. That lifecycle stage is explicitly labelled **Not tracked at program level**; elapsed dates and archived/cancelled status never fabricate completed delivery.
- GET rendering and verification made no business-record changes. Browser publication/withdrawal exercised only synthetic records in a verified disposable MySQL instance.

## Verification

- **18 focused Django checks passed**: seven new program-profile checks plus the 11 existing one-click publication checks. Covers route aliases, access/history privacy, retained action links, over-capacity, missing capacity, live publication and stale requests, blocked EWAF, unknown identifiers, escaping, optional schedules and asset scoping. The publication suite additionally covers CSRF, prerequisites, concurrency, central policy binding and audit rollback.
- **Final browser harness passed** with 14 combinations: dark/light at 1600, 1440, 1280, 1024, 768, 390 and 320 pixels. Verified no horizontal page overflow or duplicate IDs, sidebar state, correct review links, capacity cap, sticky rail, clearance from the Display button, responsive stacking, persisted theme, high contrast/forced colors, keyboard/native history, no-JavaScript history, real synthetic publish/withdrawal and the EWAF prerequisite error. No JavaScript errors.
- Visually reviewed dark desktop, light mobile and light sticky screenshots. Screenshots/results below contain synthetic data only.
- Retained-data read-only probe: six successful renders across three existing programs and both detail entry points; a second probe rendered all nine EWAF program profiles and their configured summaries. SQL writes were rejected by the probes.
- Django/database system check passed. `makemigrations --check --dry-run` found no changes. Production static collection: 205 assets into isolated `.local/program-detail-static-build`; the final spacing adjustment recollected one asset, with 204 unchanged.
- JavaScript syntax and `git diff --check` passed. No TypeScript/Vite build exists in this repository.
- The local web app on port 8013 was refreshed and passed its health check. The verified retained MySQL process ID and live connection remained unchanged; no migration or database restart was performed.

### Recorded test limitations

The first broad run also included `programs.test_policy_authorization`. Its four direct authorization tests passed, but `test_announcement_warning_provides_the_recovery_path` failed: it expects an older authorization-warning screen, while the current unchanged announcement endpoint renders the recorded-results publication dialog. That expectation is outside Program Details and was not rewritten. The full project suite was not run.

Two initial synthetic fixture mistakes (an unapproved category label, then an omitted required benefit) were corrected. The first combined run after the category correction passed all 18 focused checks; its browser setup failed on the missing benefit. The corrected browser harness subsequently passed, and passed again after the final Display-button clearance adjustment.

Commands used:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_detail_workspace programs.test_one_click_publication programs.test_policy_authorization --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_detail_workspace programs.test_one_click_publication scripts.program_detail_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.program_detail_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node --check static/js/program-detail.js
node --check scripts/program_detail_browser_qa.cjs
git diff --check
```

Final browser artifact source: temporary directory `santolan-g12-tests-_fls0ip8`. Focused checks: `santolan-g12-tests-d4uk87q_`. All database tests used the established disposable, model-synchronized baseline, not historical migration replay.

## Files changed

- `programs/detail_workspace.py`: typed read-only readiness, lifecycle, capacity and EWAF presentation.
- `programs/views.py`: detail alias selection and presentation context; original mutation flow retained.
- `config/urls.py`, `core/templatetags/workspace_navigation.py`: optional detail alias and active navigation.
- `templates/admin_portal/dashboard_topbar.html`: scoped program name/breadcrumb/title.
- `templates/programs/manage_detail.html`, `templates/programs/profile/{metrics,configuration,operations}.html`: page layout and reusable detail sections.
- `static/css/program-detail.css`, `static/js/program-detail.js`: scoped theme/layout, accessible disclosure state and error focus.
- `programs/test_detail_workspace.py`: profile coverage.
- `programs/test_one_click_publication.py`: one existing button-label assertion updated.
- `scripts/program_detail_browser_qa.py`, `.cjs`: disposable browser fixture and checks.
- This validation directory and synthetic screenshots/results.

[Dark desktop](program-detail-dark-1600.png) | [Light desktop](program-detail-light-1600.png) | [Dark mobile](program-detail-dark-390.png) | [Light mobile](program-detail-light-390.png) | [Sticky rail](program-detail-sticky-light.png) | [Browser results](results.json)
