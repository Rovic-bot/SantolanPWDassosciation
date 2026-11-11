# Events workspace — 1 November 2026

The private Events Calendar now follows the supplied light and dark references: a chronological agenda, four compact summaries, automatic filters, a sticky calendar and next-event panel, and four quarterly observance panels. It uses the existing Django application and live records. No dependencies, models, migrations, public-page styles, or event publication rules were added or changed.

## Routes and behavior

- `/admin/events` and `/admin/events/` open the workspace. `/events/manage/` remains available; `/events/observances/` uses the same quarterly presentation.
- Programs & Events retains Program Management and now links to Events Calendar. Existing view permissions control operational events and annual observances independently.
- Search matches title or location. Type, schedule, and publication status filters update protected HTML without a document reload. Results, empty states, pagination, calendar navigation, browser history, stale requests, composition input, and retry behavior are handled. A normal GET form remains available without JavaScript.
- The calendar marks actual event dates, including multi-day events, in Philippine local time. The next-event panel uses the next unfinished published event. Calendar navigation and active dates are keyboard accessible.
- Annual observances use saved titles, recurring schedules, and actual publication states. Existing authorized editor and publication actions remain available. Missing records and unavailable storage are stated explicitly; viewing this page does not seed or publish content.
- The readiness checklist is explicitly local to the current browser tab. It stores task identifiers under the staff and event identifiers in sessionStorage, with an in-memory fallback. It does not save shared readiness, send notices, or change event records.

## Data and scope

The retained General/Specific event classification is unchanged. Accent colors are decorative. Legacy registrations exclude cancellations; linked-program application demand is separately labeled and permission checked. Unallocated program places come from the existing allocation calculation, not application counts. Unknown capacities are not invented, and over-capacity demand is visible while progress bars are capped at their maximum width. Public RSVP remains retired.

The total-registration and average-capacity summaries explicitly identify their legacy-registration basis. Upcoming events cover the next 45 days. Observance totals include only currently published saved records. Reference examples were used exclusively as disposable browser-test fixtures, not written into the retained application database.

The public website, analytics dashboard, program portfolio, member directory, and onsite-registration interface were not redesigned by this change. The user's preceding removal of the program hero and Review approvals action remains intact.

## Verification

- The focused Django run passed 54 event, publication, permission, navigation, and presentation tests. The same run passed the existing automatic-filter browser regression across 25 admin pages and 44 workflows. Its new event-browser check initially used a scroll position beyond the sticky panel's containing section; the assertion was corrected to check inside that section's valid sticky interval.
- The subsequent focused run passed all 9 tests: the eight new event-workspace tests plus the complete Events browser harness. This also covered the final decorative accent and heading-encoding changes.
- Events browser coverage passed 14 combinations: dark/light themes at 1600, 1440, 1280, 1024, 768, 390, and 320 pixels. It checked overflow, duplicate IDs, theme persistence, sticky positioning, large text, high contrast, forced colors, reduced motion, keyboard calendar selection, the observance editor link, local checklist persistence, error recovery, and the JavaScript-disabled fallback. No JavaScript errors or POST requests occurred in this browser scenario.
- `manage.py check --database default`: no issues. `manage.py makemigrations --check --dry-run`: no changes detected.
- Deployment asset collection passed: 199 files in the isolated `.local/events-workspace-static-build` output. The final collection reported all 199 unchanged. This Django project has no Vite/TypeScript production build.
- `node --check` passed for the Events UI and browser harness. `git diff --check` passed.
- Database tests used a fresh disposable MySQL instance through `scripts/g12_test_runner.py` and `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`; historical migrations were not applied to the model-synchronized test schema. Application data was not used as a test database.
- The retained local web process was refreshed after verification. Its health check passed, and the retained MySQL process ID and live connection were unchanged. The workspace is available at `http://127.0.0.1:8013/admin/events`.

Browser evidence is saved beside this file: `events-browser-results.json`, `admin-filter-results.json`, and desktop/mobile/sticky screenshots in both themes. All screenshot records are synthetic.

## Files for this change

- Presentation and routes: `events/workspace.py`, `events/views.py`, `config/urls.py`.
- Navigation and top bar: `core/templatetags/workspace_navigation.py`, `templates/admin_portal/dashboard_topbar.html` (Events-only branches).
- Templates: `templates/events/manage_list.html`, `templates/events/observances.html`, and `templates/events/workspace/{base,filters,card,calendar,operations,results,quarters}.html`.
- Scoped assets: `static/css/events-workspace.css`, `static/js/events-workspace.js`.
- Tests: `events/test_workspace.py`, `events/test_list_actions.py`, `events/test_optional_event_details.py`, `events/test_observances.py`, `core/tests/test_workspace_navigation.py`.
- Browser verification: `scripts/events_workspace_browser_qa.py`, `scripts/events_workspace_browser_qa.cjs`, and the Events-compatible branch of `scripts/admin_filters_browser_qa.cjs`.
- Evidence: this directory. Earlier unfinished changes elsewhere in the working tree remain preserved.

## Follow-up: compact Events header

At the owner's request, removed the Events eyebrow, “Make every moment count.” title, and introductory description. Annual observances and Create event remain in a compact action row above the summaries. A visually hidden Community events heading preserves the page outline. Removed unused hero styles and bumped the stylesheet version. This follow-up changes only `templates/events/manage_list.html`, `templates/events/workspace/base.html`, and `static/css/events-workspace.css`.

Read-only rendering of `/admin/events`, `/admin/events/`, and `/events/manage/` confirmed the requested text is absent and the authorized actions remain. Django checks and `git diff --check` passed. Asset collection copied the updated stylesheet with 198 other assets unchanged. The local web process was refreshed; its health check passed with the retained MySQL process unchanged. The screenshots above document the initial redesign before this compact-header adjustment; the larger regression suite was not repeated for this presentation-only removal.
