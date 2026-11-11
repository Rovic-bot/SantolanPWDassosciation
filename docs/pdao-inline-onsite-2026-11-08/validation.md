# PDAO editing, preview and onsite registration — November 8, 2026

The owner's request authorizes this scoped PDAO change. The October 10 target documents, development guide, confirmed membership/PDAO amendment, Open Decisions and implementation-impact notes were reviewed alongside current PDAO, membership review and onsite validation. PDAO intake remains separate from Association membership and government ID approval.

Implemented behavior:

- PDAO review edits now appear directly inside Application details, using its existing eight keyboard-accessible category tabs. The separate edit disclosure and Submission and review history panel are removed. Original data, append-only saved revisions, references and protected processing events remain retained. Existing correction permissions, validation, stale-version protection, Ready-to-Received reset and forwarded-record locks still apply. Read-only staff retain the complete submitted-detail view. Validation reveals the affected tab; without JavaScript every section remains available.
- Print or save PDF opens a same-page dialog from both the review page and the standalone print URL supplied by the owner. The protected iframe uses the latest saved data, same-origin framing and no-store responses. The dialog offers Print / Save PDF and Close, supports Escape from inside the iframe and restores focus. Preview fitting does not change the original A4 output.
- The public PDAO form reuses the clean Association application surface, spacing, fields and guide rail. All existing PDAO fields, labels, options, required rules and submission behavior remain unchanged. The print-preparation fallback shares the same visual treatment.
- Members → Onsite PDAO registration and the PDAO inbox provide a new staff entry. It reuses the PDAO form fields, the onsite membership design, review confirmation and validation. New records enter the PDAO queue as Received with a recorded Walk-in channel and an attributed onsite event. Its acknowledgement describes staff-assisted onsite capture. Public and staff tokens have different signing salts, session contexts and privacy versions; staff tokens also bind the actor. Repeated identical submissions are idempotent. Corrections preserve the original channel. Public receipt access is disabled for staff-created onsite records.

Permissions and installation:

- Encoding requires active staff status, dashboard access, PDAO view access and the new `membership.add_pdaoregistration` permission. Printing, correction and forwarding continue to require their distinct existing permissions. No existing user or role grants were broadened. Superusers have the new permission through Django's existing permission model.
- Migration `0013_pdao_onsite_registration` contains only model permission metadata and a processing-event choice. Its collected schema SQL is empty, and migration drift checks pass.
- The retained development database uses a model-synchronized baseline without migration history. After verifying that identity and that no email was sending, the known web process was stopped and a private SQL backup was made. Only the new permission row was installed. All 130 other tables were fingerprint-identical; existing permission rows and all role grants were preserved. No schema changes or application edits occurred during installation. The local server was restarted at port 8013. Backup hash and preservation details are in `preservation.json`; private backup and activation helper remain under `.local/pdao-onsite-20261108/`.

Validation:

- 55 tests passed across onsite intake, existing PDAO registration/corrections, review layout, source printing and workspace navigation on disposable native MySQL. Coverage includes field parity, permissions/revocation, CSRF, private previews, cross-channel/session token rejection, unexpected/invalid fields, duplicate submissions, audit rollback, preserved originals, current print data, manual transitions and existing concurrency protections.
- The updated PDAO browser journey passed on disposable MySQL. It verified dark/light review layouts at 1600, 1024, 768, 390 and 320 px; eight keyboard tabs; inline corrections; absence of the removed panels; same-page preview from both entry points; no extra browser page; correct print dispatch to the iframe; mobile preview; onsite review and save; preserved original records; manual forwarding and forwarded edit locks; public form sections/options; no-JavaScript details; and zero JavaScript errors.
- Actual Chrome PDF output from a 390 px preview is two A4 pages (594.96 × 841.92 pt). Poppler rendered both pages for visual inspection. An embedded-preview print padding override prevents the screen inset from widening printed pages. Desktop/mobile screenshots and both printed pages were visually inspected.
- Fresh live rendering of the supplied application, its embedded print view and the onsite page returned 200 with no-store protections. This verification prohibited database writes and suppressed only audit/token side effects; no live application was edited or submitted.
- Django configuration/database checks, migration drift, JavaScript syntax and `git diff --check` passed.

Commands:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test membership.test_pdao_onsite membership.test_pdao_registration membership.test_pdao_review membership.test_pdao_record_layout membership.test_pdao_source_print core.tests.test_workspace_navigation --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.pdao_record_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/current_development.py check
git -c core.safecrlf=false diff --check
```

Backend artifacts: `santolan-g12-tests-8j47nu5y`. Final browser/PDF artifacts: `santolan-g12-tests-rmcglwrm/pdao-record-browser`. Screenshots copied beside this document contain fictional records. There were no commits, pushes, real applicant submissions, real emails or government-forwarding actions.
