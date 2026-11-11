# G06-B0 — Remove Association Program Budget Editing

Date: 2026-10-12. Branch: `feature/events`.
Starting commit: `5ae11fe33162f01a510e37dc53021fca863cd98b`.
The starting branch and commit were verified and the working tree was clean.
The owner-defined development baseline remains **70%**.

## Confirmed decision and scope

The owner confirmed that the Association does not manage program budgets.
Budget is removed from Admin Create Program and Edit Program. Future PDAO
approval records must **not include Approved Budget**, including in approved-term
snapshots. This decision supersedes earlier budget-editing descriptions in
historical program documentation and any proposed Approved Budget field in the
G06-A design. Existing historical documentation and audit records are retained.
No PDAO approval model, workflow, permission or migration is implemented here.

`Program.budget` remains in the database with its existing type, constraints and
historical values. The permission-controlled Admin detail page retains its
existing read-only historical budget display; public pages still do not expose
it. Beneficiary slots and Amount per Beneficiary are unchanged.

## Implementation

- `programs/forms.py`: remove `budget` from `ProgramForm.Meta.fields`, its label
  and help text. Document why it is intentionally excluded. Both Create and Edit
  render this shared form, so no template or layout change is necessary.
- `programs/tests.py`: add seven focused regression tests and remove the obsolete
  expectation that a negative Budget submission produces a form validation error.
  Negative slots and Amount per Beneficiary validation remain tested. The model's
  budget validation and database constraint remain unchanged.
- `docs/g06-b0-program-budget-validation-2026-10-12.md`: record the decision,
  implementation boundaries and validation evidence.

Previously, including Budget in the ModelForm allowed omitted optional input to
clear an existing value and accepted submitted budget changes. It is now outside
the form's explicit editable-field list. Django ignores forged Budget keys and
does not assign omitted/excluded fields to the loaded instance. The existing
transactional save service reloads and locks the record, preserves its budget,
and records changes only for permitted form fields. New programs retain the
existing NULL budget default. Existing audit entries are not rewritten.

The Program model, migrations, services, permissions, application snapshots,
publication rules, selection/EWAF behavior, G07/G07-B availability logic, Admin
navigation, shared styling and accessibility templates are unchanged.

## New regression coverage

Seven new test methods in `ProgramTests` cover:

1. Create/Edit form exclusion, with slots and Amount per Beneficiary retained.
2. Authenticated Create/Edit HTML without Budget controls and with slots/amount.
3. Forged creation POSTs (positive, negative, nonnumeric and empty): successful
   draft creation with NULL budget and no budget audit change.
4. Omitted Budget on edits preserves NULL, zero, a positive decimal and the
   maximum supported decimal; ordinary name, slot and amount changes still save.
5. Forged edit POSTs (positive, zero, empty, negative, nonnumeric and oversized)
   preserve the historical value and the complete previous budget audit entry.
6. Forged input cannot populate a previously NULL budget through the save service.
7. Editing a program with a submitted synthetic application preserves its entire
   application record, configured requirements, historical budget and old logs.

All fixtures are synthetic. No real member information is used.

## Validation environment and results

Before test setup, the shell was verified to contain no `DB_*`, `SUPABASE_*`,
`AWS_*` or `DJANGO_SETTINGS_MODULE` variables. The existing isolated-test harness
was adapted in memory, without changing its file. Native MySQL 8.4.11 was started
on loopback with a fresh Windows-temp data directory and an unused local port.
`SELECT @@datadir` was checked against that newly created directory before any
Django database command. Credentials were generated solely for this instance;
`.env` loading was disabled with `PYTHON_DOTENV_DISABLED=1`. Neither development
nor production credentials were read.

The application connection used a fresh empty `review_unused` schema; Django
tests used the separate disposable `test_g06b0_disposable` schema. Only synthetic
fixtures were inserted. Existing migrations ran only to construct that test
schema. No migration command targeted an existing application database.

Commands executed with the virtual-environment Python and isolated environment:

```text
manage.py check --database default
manage.py makemigrations --check --dry-run
manage.py test programs core.tests.test_home_program_availability --noinput --verbosity 1
manage.py test --noinput --verbosity 1
```

Results:

- Django system/database checks: no issues.
- Migration drift: **No changes detected**. No migration created or required.
- Focused suite: **97 passed** in 21.843 seconds, including all seven new tests,
  the existing program tests and the 13 G07 homepage tests.
- Complete Django suite: **432 passed** in 86.879 seconds (425 existing plus
  seven new), with no failures or skips. Focused tests are included in this total.
- Django destroyed the disposable test schema after each suite. The isolated
  MySQL process stopped successfully. Synthetic logs/data remain in Windows temp
  outside the repository; no existing `.local` database was used or modified.
- `git diff --check` and the equivalent check of the untracked report passed.
  The full tracked diff and new report were inspected: only the three files above
  changed, with no credentials, secrets, real member data, generated artifacts,
  database files, migrations or unrelated changes included. The index is empty.

The branch and HEAD remain at the verified starting point. Historical Budget
values were validated using synthetic records; real records were not inspected.

## Limits and release

This removes editing through the supported Admin forms/service; it does not make
the retained column immutable to separately privileged direct database access.
Read-only historical display remains intentional. Hosted and visual browser QA
are outside this increment; rendered Create/Edit HTML is tested automatically.

No unresolved policy decision blocks G06-B0. The remaining PDAO approval and
reapproval workflow, document preservation, processing pause and reassessment
design remain separate work requiring owner-approved scope. No real application
database, hosted Aiven/Supabase data or Render service is accessed or modified.
No schema migration, new dependency, staging, commit, push or deployment is part
of this increment. Owner review is required before publication.

Suggested commit message: `Remove Association program budget editing`.
