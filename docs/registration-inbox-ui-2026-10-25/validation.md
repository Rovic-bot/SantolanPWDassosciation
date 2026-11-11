# Pending Association registrations UI — 2026-10-25

The owner requested the supplied clean, formal inbox design. The implementation uses the existing Admin shell, with underlined member navigation, a process guide, onsite notice, combined search/filter card, counted status tabs, intake buttons, and a five-column registration table with status badges and pagination.

## Scope and behavior

- Default queue: awaiting a final membership decision. Completed includes the existing approved and rejected decisions; a pending linked membership review remains in the awaiting queue. No processing states or decision rules were added.
- Search supports applicant names from the current form revision and complete AMR references. Old corrected names do not remain searchable. Complete reference searches retain the existing precedence over stale filters, including for completed records. Status tabs return from an exact-reference lookup to the queue; ordinary name queries and filters are preserved across tabs.
- Tab counts reflect the current search and processing/channel filters before the tab is applied. Pagination retains the current query. Unknown filters or partial AMR references do not broaden results.
- Approved/rejected records display their actual decisions and a View link. Unfinished records retain Review links and their current processing labels. The initial received state is presented as Awaiting onsite.
- Existing category, staff, intake, encoding and decision permissions remain intact. GET/HEAD do not mutate registration records. Printed/walk-in buttons use the existing authorized routes. Approval, rejection, correction, attachments and immutable references are unchanged.
- CSS is scoped to this inbox, with wrapping controls, small-screen stacked filters, visible focus indicators and a keyboard-accessible table scroll region. No JavaScript dependency was added.

## Files

- `templates/membership/registration/inbox.html`: page layout, search, tabs, rows and pagination.
- `static/css/registration-inbox.css`: scoped presentation and responsive rules.
- `membership/registration_inbox.py`: read-only search, counts and presentation labels.
- `membership/registration_views.py`: delegates the authorized inbox GET to the query helper; removes its unused paginator import.
- `membership/test_registration_inbox.py`: six synthetic acceptance tests.

No models, migrations, settings, schedules, approvals or database records were changed.

## Validation performed

**59 tests passed in 4.604 seconds** against a freshly initialized, identity-verified disposable native MySQL 8.4.11 database (`test_g12_disposable`). The launcher disabled `.env`, used separate database grants/datadir and temporary uploads, and destroyed the test database afterward.

Command:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test membership.test_registration_inbox membership.test_registration_completion.RegistrationInboxCompletionTests membership.test_registration_intake.PendingRegistrationTests membership.test_registration_decisions --testrunner scripts.registration_handoff_test_runner.RegistrationHandoffTestRunner --noinput --verbosity 1
```

Coverage includes current-revision and case-insensitive name search, complete reference precedence, completed decisions/counts, empty and invalid filters, pagination, escaped search values, staff/encoding permissions, read-only inbox behavior, existing intake controls, corrections and approval/decline regressions. System checks reported no issues. Python syntax and whitespace checks passed.

Test artifacts: `.local/dual-registration-20261024/temp/santolan-g12-tests-p_jqbcog`.

## Local runtime installation

Four scoped files were installed into the existing ignored development runtime. Only the inbox function was replaced in its customized view module; unrelated runtime code was preserved. Original files and before/after hashes are retained in `.local/registration-inbox-ui-20261025/`.

A fresh process verified the installed runtime's database identity, enforced `SET SESSION TRANSACTION READ ONLY`, rendered all three tabs and exercised reference/name search without a session login or database writes. No private applicant values were saved in the report. See `runtime-verification.json` in that ignored artifact directory.

The identified website on port 8003 could not be restarted: Windows returned Access is denied when stopping its Python process. The owner must run `Restart System.cmd`, then refresh the inbox. No alternative process-control workaround was attempted.

Browser visual QA could not run because Chrome launch returned `spawn EPERM`. Template rendering is verified; pixel layout, keyboard interaction and responsive appearance have not been browser-verified in this session. No screenshots are claimed.

No commit, push or deployment was performed.
