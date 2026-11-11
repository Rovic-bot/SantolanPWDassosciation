# Automatic admin filters — November 1, 2026

Admin list filters now apply when a dropdown, checkbox, or date changes. Text searches apply after a 400 ms typing pause. Enhanced forms hide their Search/Apply buttons; the original buttons and GET submission remain available without JavaScript.

## Scope and behavior

- Covers dashboard activity, program management and application lists, membership/review queues, assistance and releases, event management/attendance/registrations, announcements, EWAF program and saved-calculation selectors, reports, and native Django administration searches.
- Uses explicitly marked GET forms and Django's changelist search form. Native administration sidebar filter links already apply immediately. Existing member-directory and EWAF applicant-list AJAX filtering keep their own handlers; no duplicate handler is attached.
- Each enhancement submits the original GET form. Existing query semantics, access controls and server validation remain authoritative. No backend, models, migrations, dependencies, calculation rules or write actions were changed.
- Dropdown filtering retains the Association inbox's current tab through its existing named submit button. Existing text/reference search semantics remain intact. Other hidden context fields, including program and saved calculation, are retained; pagination resets when filters change.
- Dashboard Custom range waits for both dates. Selecting a preset hides/disables its custom dates, preventing incomplete or obsolete dates from blocking the preset.
- Focus, caret and scroll position are restored after filter navigation. Short-lived session storage contains only the control name, path, coordinates and timestamp; no query text, reference numbers or applicant values are stored. Metadata is removed after navigation.
- IME composition waits for committed text. Reset and other navigation cancel a pending search. A delayed navigation check confirms that Reset cannot be overridden by an old queued search.
- Record editors, approvals, publication, selection, releases, exports and explicit online-application loading stay on their existing actions. Public pages do not load the enhancement.

## Changed files

- `static/js/admin-filters.js`: scoped automatic GET submission, debounce/composition handling, date readiness, context preservation, focus restoration and pending-search cancellation.
- `static/css/admin-filters.css`: hides enhanced filter controls reliably and fills space left by removed submit buttons.
- `templates/admin_portal/base.html`, `templates/admin/base_site.html`: load the shared enhancement only in the admin workspace.
- Explicit GET-form annotations in:
  - `templates/admin_portal/{application_programs,dashboard}.html`
  - `templates/announcements/manage_list.html`
  - `templates/assistance/queue.html`, `templates/assistance/referrals/inbox.html`
  - `templates/events/{attendance_list,manage_list,registrations}.html`
  - `templates/ewaf/{calculation_context,operational_programs,score_breakdown}.html`, `templates/ewaf/revised/preview.html`
  - `templates/membership/list.html`, `templates/membership/pdao/inbox.html`, `templates/membership/registration/inbox.html`
  - `templates/programs/{applications,card_filters,photo_queue}.html`
  - `templates/reports/report.html`
- `scripts/admin_filters_browser_qa.py` and `.cjs`: synthetic browser validation on a fresh disposable database.

All earlier unfinished changes remain preserved. The existing EWAF applicant picker delegates to the shared handler instead of attaching its older separate auto-submit hook.

## Verification

- **25 admin pages and 44 automatic-filter workflows passed** in headless Chrome against the actual Django views. This includes search/dropdown navigation, request counts, focus restoration, checkbox filtering, pagination reset, complete custom ranges, retained program/tab context, IME composition, delayed Reset, explicit POST/reference-loading behavior, and JavaScript-disabled fallback.
- **16 responsive checks** passed across program, Association inbox, Assistance Desk and dashboard pages at 1440 and 390 pixels in both themes, with no horizontal page overflow. The program-filter screenshot was visually reviewed.
- No POST requests or JavaScript errors occurred during the automatic-filter browser run.
- The existing member-directory browser regression passed again, including its **12 responsive checks**, automatic AJAX search/status filters, keyboard selection and sticky preview.
- All browser fixtures used verified disposable MySQL instances with synthetic records and model-synchronized schemas. No tests targeted the retained application database; historical migrations were not tested.
- Application/database system check passed using the running application's verified `config.current_development_settings` connection.
- JavaScript syntax checks and `git diff --check` passed.
- Production asset collection succeeded: **195 files** in isolated `.local/admin-filters-static-build`; the final cancellation adjustment updated one asset with 194 unchanged.
- The local web process was refreshed to reload cached admin templates. The retained MySQL process stayed running.

Commands:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.admin_filters_browser_qa scripts.member_directory_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.admin_filters_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node --check static/js/admin-filters.js
node --check scripts/admin_filters_browser_qa.cjs
git diff --check
```

The initial browser harness used an incorrect synthetic channel option (`onsite`); it was corrected to the existing `walk_in` value. The final run passed.

[Browser results](browser-results.json) · [Program filters screenshot](automatic-program-filters.png)

The screenshot contains fictional test data only.
