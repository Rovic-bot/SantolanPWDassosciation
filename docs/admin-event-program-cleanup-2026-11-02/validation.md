# Events and program review cleanup — November 2, 2026

## Delivered

- Events shows three agenda cards at a time. Additional events scroll inside the list; annual observances stay directly below the workspace. The list recalculates its height after filtering and at different screen widths.
- Removed all four event summary cards, registration/capacity indicators, and the local readiness checklist. The mini calendar, next-event details, automatic filters, publication actions, and observance editors remain available.
- Manage Event now offers the existing edit/publication/status controls without Event attendance, Legacy registrations and attendance, or View public event links. Its schedule includes dates, times, and location.
- New events automatically use General Events. Category, target audience, participation guidance, capacity, and application-program inputs are absent from creation and ignored if submitted manually. Existing saved event configuration, historical registrations/attendance, and their protection/audit rules remain intact. Existing-event editing is preserved.
- In Applications & Eligibility, selecting a program title updates the preview. The separate **Review program** link opens that exact program's applicant-review workflow. Programs without applications have a disabled **No applications** action.
- Program Details has an inline desktop title, a wider right operations rail, and page scrolling that exposes the entire rail without an internally clipped panel. The empty requirements message spans the section width. The lifecycle now contains only **Draft / Created** and **Published / Public**; unpublished programs say **Not published**.
- Actual publication, withdrawal, authorization, eligibility, and EWAF rules were not changed. No completed-delivery status is fabricated. Public templates, dashboard, member pages, registration, and the program builder were not changed in this follow-up.

## Verification

- **85 focused Django tests passed** on a verified disposable MySQL instance: 33 workspace/form/detail tests and 52 event validation/publication/history tests.
- **Three browser harnesses passed**, covering **42 layout combinations** (each page at 1600, 1440, 1280, 1024, 768, 390, and 320 pixels in dark and light themes).
- Browser checks cover exactly three visible agenda cards, independent scrolling, automatic filters, calendar navigation, direct review navigation, preview selection, zero-application disabled actions, horizontal empty requirements, desktop title layout, accessible bottom rail actions, keyboard operation, large text/high contrast, and no horizontal page overflow.
- Event and application browser checks performed no writes. Program publication/withdrawal and a blocked EWAF publication were exercised only on synthetic records.
- Read-only rendering against the retained local database passed for Events, event creation, Program Details, and Applications & Eligibility. An SQL wrapper rejected any non-read operation.
- Django database/system checks passed; migration check reported **No changes detected**.
- Production asset collection passed: **205 static files** collected to `.local/admin-cleanup-static-build`.
- JavaScript syntax checks and `git diff --check` passed. Git emitted existing line-ending conversion notices only.
- The recognized local web process was refreshed at `http://127.0.0.1:8013`; the same MySQL process remained running. Retained business records were not changed by verification.

An initial browser run exposed a heading-name mismatch caused by the selector's accessible label; it was corrected with an accessible description and the application harness passed. Older event tests were updated to seed historical configuration explicitly, because new-event creation now intentionally ignores the removed fields. Historical validation, publication prerequisites, escaped public content, and audit rollback coverage still pass. The filtered-agenda test now checks the agenda rather than the independent next-event panel.

Commands (PowerShell, repository root):

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test events.test_workspace events.test_optional_event_details events.test_list_actions programs.test_detail_workspace programs.test_review_workspace --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test events.tests events.test_participation events.test_simple_publication --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.events_workspace_browser_qa scripts.application_workspace_browser_qa scripts.program_detail_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node --check static/js/events-workspace.js
node --check static/js/application-workspace.js
node --check static/js/program-detail.js
git diff --check
```

The corrected application browser harness passed in the subsequent 53-test run; the final 52 event checks passed after historical fixtures were updated. Artifact directories: `santolan-g12-tests-zlu7lmwx` (33 checks), `santolan-g12-tests-mfwcjfzs` (Events and Program Details browsers), `santolan-g12-tests-cw15_pia` (corrected application browser), and `santolan-g12-tests-xwxjcik4` (52 final event checks). These tests use the repository's disposable model-synchronized baseline, not historical migration replay.

## Files changed in this follow-up

- Events: `events/forms.py`, `events/views.py`, `events/workspace.py`; `templates/events/{edit,manage_list,manage_detail}.html`; `templates/events/workspace/{base,card,operations,results,schedule}.html`; `static/css/events-workspace.css`; `static/js/events-workspace.js`.
- Application chooser: `templates/programs/application_workspace/{page,card}.html`; `static/css/application-workspace.css`.
- Program Details: `programs/detail_workspace.py`; `templates/programs/manage_detail.html`; `templates/programs/profile/configuration.html`; `static/css/program-detail.css`; `static/js/program-detail.js`.
- Verification: `events/{tests,test_participation,test_simple_publication,test_workspace,test_optional_event_details}.py`; `programs/test_detail_workspace.py`; `scripts/{events_workspace,application_workspace,program_detail}_browser_qa.cjs`; this validation directory.

Earlier unfinished repository changes are preserved.

[Events, dark](events-dark-1600.png) · [Events, light](events-light-1600.png) · [Program Details, dark](program-detail-dark-1600.png) · [Program Details, light](program-detail-light-1600.png)
