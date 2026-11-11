# Readable Administration changes — November 9, 2026

The owner requested understandable descriptions of administrator actions and matching audit filters, including program changes, membership approval, eligibility, selection, assistance approval, and result publication.

## Implemented behavior

`/admin/admin/logentry/` now presents a combined, read-only activity list. Each entry shows a plain-language action, affected record, administrator, date/time, and a Details link. Recorded notes are available in a disclosure on the detail page.

The list reads the existing histories for programs, EWAF, immutable selection decisions, eligibility/assistance, membership, registration review, member changes, information review, PDAO applications, announcements/results, events, attendance, annual observances, website content, portal edits, Assistance Desk requests/settings, and Django administration actions. Public submissions without an administrator are not presented as administrator actions. Unknown action codes remain visible under a readable source-specific fallback.

Examples: **Program changed**, **Member approved**, **Member marked eligible**, **Member marked ineligible**, **Member selected**, **Assistance approved / member selected**, **Assistance released**, and **Results published**. Non-EWAF assistance approval denotes selection; it remains distinct from actual release. PDAO forwarding remains forwarding, not government approval.

Filters use the exact same action expressions as the list. Search, section, action, administrator, and inclusive local date ranges combine; pagination retains the filters. Search also supports the original permitted notes. Native GET submission works without JavaScript, and the existing admin filter enhancement handles automatic submission.

Historical eligibility and non-EWAF decisions use their stored snapshots, and EWAF selection uses its immutable decision record. They do not use the current application outcome. The display does not duplicate the mandatory EWAF digest companion or mirrored membership-approval/verification entries. Original records remain stored in their original tables.

The existing audit-view gate remains required. Each additional domain source also requires its record-view permissions; direct detail URLs enforce the same source boundary. Existing native administration entries retain their original audit access. Source notes are escaped, private snapshots are not dumped into the list, and list/detail views accept only GET/HEAD. There are no schema migrations, audit rewrites, backfills, approval changes, or calculations triggered by viewing the history.

## Validation

- **12 focused tests passed**: existing sign-in/native-audit protections, shared action/filter labels, historical outcome accuracy, combined filters, invalid filters, inclusive dates, permissions, direct detail access, read-only behavior, pagination, unknown actions, deleted-actor labels, escaping, and real service-created EWAF selection history with the digest companion omitted.
- Browser checks passed at **1440, 768, 390, and 320 pixels in both themes**, with no page overflow. Also checked automatic action filtering, search, pagination reset/preservation, Details, expandable notes, and no-JavaScript filter submission. No browser mutations or JavaScript errors occurred.
- Visually inspected the desktop light and mobile dark captures; screenshots contain fictional disposable test records only. `results.json` records browser outcomes.
- A read-only render against the retained development database displayed 30 of 1,368 existing activity records, used **5 queries**, and took **0.223 seconds** locally. Captured queries contained no writes. This is a local measurement, not a production benchmark.
- Application/database configuration check and `git diff --check` passed. The local web process was refreshed to use the new list and templates.

Command:

```powershell
.venv/Scripts/python.exe scripts/g12_test_runner.py test audit scripts.admin_activity_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Tests used a fresh disposable MySQL instance and temporary private media under `santolan-g12-tests-4zftb_0o`. The test schema was synchronized from models; historical migrations and retained application data were not used as test targets.
