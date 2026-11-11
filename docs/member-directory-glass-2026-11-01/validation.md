# Member directory — November 1, 2026

The directory now uses the supplied light/dark references: two compact summaries, an automatic search/filter toolbar, compact selectable rows, and a sticky member preview. The follow-up removes the introductory heading/copy and the Records for review and Renewals due cards, while retaining the registration action. It uses the existing Django application, shared admin theme, live registry, and permission checks. No dependencies, migrations, new API, or stored business fields were added.

## Routes and scope

- `/admin/members` and `/admin/members/` serve the directory through the existing authenticated member-list view. `/members/` remains available.
- The Members sidebar directory link targets `/admin/members` and remains active for member records.
- Register new member links to `/admin/members/registration`, which retains the existing redirect to the onsite form.
- The native `/admin/` administration tools, `/dashboard/` analytics, public website, and onsite registration design remain intact. Directory assets are loaded only by the directory template.
- The local web process was refreshed after verification. The retained MySQL process stayed running, and the new route retained its login guard.

## Data and behavior

- Summaries use actual registry counts. The original default Active filter, name/control-number search, archived records, and 20-record pagination remain available.
- Typing in search and changing status fetch the existing HTML GET view automatically, so searching includes records on later pages without a Search button. Typing is debounced; status changes apply immediately and stale responses are discarded. A submit button is available only when JavaScript is disabled. Selection updates locally without navigating away.
- Review is a separate flag for existing information reviews awaiting findings, not a replacement for a member's Active/Inactive status. The flag and filter honor the configured review policy, review permission, and existing program-related permission gate.
- The model does not track renewal dates or primary support needs. The list displays the actual disability classification. No values or mappings were invented.
- The preview shows existing contact details, join date, and last-updated time. Manual PRPWD information requires the existing membership-application permission; administrative notes require member-event permission. Unavailable fields are omitted from the serialized preview data. Edit and registration actions retain their permission gates; archived records have no edit action.
- Only the current page's preview data is serialized using Django's escaped `json_script`; updates use `textContent`. Personal details are not stored in browser storage. Birth dates, addresses, email, income, documents, and the raw registration profile are not serialized.
- Desktop uses a sticky right panel with a bounded height. Tablet moves the preview below the list. Mobile uses touch-friendly cards and focuses the selected preview. JavaScript-disabled rows still open the full record, and the search form still submits normally.

## Files changed in this task

- `members/directory.py`: typed, read-only directory projection, summaries, pagination, and permission-aware previews.
- `members/views.py`: existing member-list view supplies the new presentation context.
- `templates/members/list.html` and `templates/members/directory/{base,row,panel,results}.html`: directory layout and reusable fragments.
- `static/css/member-directory.css` and `static/js/member-directory.js`: scoped theme styling, responsive layout, filtering, selection, and keyboard behavior.
- `config/urls.py`: directory URL alias before the native admin route.
- `core/templatetags/workspace_navigation.py`: directory destination and active state.
- `templates/admin_portal/dashboard_topbar.html`: directory-specific breadcrumb/title when requested by its template.
- `members/test_directory.py`: privacy, permissions, real counts, routes, filtering, query behavior, escaping, and page-isolation checks.
- `core/tests/test_workspace_navigation.py`: directory destination expectation.
- `scripts/member_directory_browser_qa.py` and `.cjs`: disposable-data interaction and responsive browser checks.
- This validation note and its synthetic screenshots/results.

Other existing unfinished changes in the working tree were preserved.

## Verification

- Compact-layout follow-up: **all eight directory tests passed again**, including the browser workflow and all **12 responsive theme combinations**. The existing workflow changes search text/status directly without clicking a submit button. The two remaining cards fill their row, and no visible introductory heading or Search button remains. Django/database and JavaScript checks passed. Static collection updated two assets, with 191 unchanged. Screenshots below show this latest layout.

- Initial redesign: **40 distinct focused tests passed across the verification runs.** The first run passed all 32 existing member/navigation tests and six new directory tests. A too-long synthetic reference and an over-strict mobile scroll assertion were corrected in the test harness. The final run passed all eight directory tests, including the browser workflow.
- Browser checks passed at **1600, 1280, 1024, 768, 390, and 320 pixels in both themes**: 12 responsive combinations, no horizontal page overflow, duplicate IDs, or JavaScript errors.
- Verified full-registry name/control-number search, no-match and clear states, active/inactive/review/archived filters, pagination and browser Back, stale-request handling, immediate row selection, full/edit links, and registration destination.
- Verified keyboard selection, selected-state announcements, mobile preview focus/visibility, largest text, high contrast, forced colors, reduced motion, and JavaScript-disabled fallback. Sticky preview position was checked while scrolling in both themes. Desktop light/dark and mobile preview screenshots were visually reviewed.
- All database tests used fresh disposable MySQL instances with synthetic data and a model-synchronized schema. They did not modify the retained application database or validate historical migrations.
- Application/database check passed with zero issues using the running application's `config.current_development_settings` and verified database identity. The plain default-settings database check points to an inactive separate local MySQL endpoint; no configuration was changed.
- JavaScript syntax checks and `git diff --check` passed.
- Production asset collection (`collectstatic --noinput`) succeeded: **193 files collected** into isolated `.local/member-directory-static-build`.

Commands:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test members.test_directory members.tests core.tests.test_workspace_navigation scripts.member_directory_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test members.test_directory scripts.member_directory_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node --check static/js/member-directory.js
node --check scripts/member_directory_browser_qa.cjs
git diff --check
```

## Synthetic visual evidence

- [Desktop dark](directory-dark-1600.png) · [Desktop light](directory-light-1600.png)
- [Mobile dark](directory-dark-390.png) · [Mobile light](directory-light-390.png)
- [Sticky preview dark](directory-sticky-dark.png) · [Sticky preview light](directory-sticky-light.png)
- [Selected preview on mobile](directory-mobile-selected.png)
- [Browser results](browser-results.json)

Screenshots contain fictional test data only. Full-page captures include the fixed navigation and display control at their viewport position.
