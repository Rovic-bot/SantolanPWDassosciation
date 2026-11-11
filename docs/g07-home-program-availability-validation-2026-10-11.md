# G07 — Accurate homepage program availability

Baseline: owner-defined **70%**, unchanged. Branch: `feature/events`. Starting
HEAD: `f1819e8` (the prior production-logging change); working tree was clean.
No commit, push, Render change or deployment is authorized by this increment.

## Behavior and scope

The homepage previously tested up to three publicly visible programs with a
future closing date. That included cancelled/upcoming programs and programs
without complete authorization/instructions, and the empty state incorrectly
said no programs were listed even when public programs existed.

`ProgramQuerySet.accepting_applications()` is the database-query equivalent of
the existing `Program.registration_available` property: published status,
publication timestamp reached, opening time inclusive, closing time exclusive,
recorded policy authorization, and both required instruction fields nonblank.
Its explicit whitespace pattern matches Python `str.strip()`, including Unicode
whitespace and ASCII separators. The existing property and application guards
are unchanged; no new business policy is introduced.

The homepage uses one `exists()` query (`SELECT 1 ... LIMIT 1`), without fetching
program rows or iterating through an unbounded Python collection. It reports
“Applications are open” or “No programs are accepting applications.” The Programs
link remains available in either case. Public listing/detail pages continue to
show upcoming, closed and cancelled programs under their existing rules.

Files: `programs/models.py`, `core/views.py`, `templates/public/home.html`,
`core/tests/test_home_program_availability.py`, and this validation note.
No schema, dependencies, navigation structure, CSS/JavaScript, Admin UI, EWAF,
application authorization, private evidence or audit workflow changes.

## Validation

Before database-backed tests, the operator harness created a fresh native MySQL
8.4.11 instance in an OS temporary directory outside the repository, bound only
to loopback on an unused port. It checked the server's actual data directory
against that newly created path. Django used only `test_g07_disposable`.
Credentials and records were synthetic; dotenv was disabled and DEBUG remained
false. Existing `.local` database files, development `.env`, real member data,
production credentials and hosted Aiven/Supabase were not used.

The 13 new tests cover authorized open programs, upcoming/closed/cancelled
programs, missing authorization, both missing/whitespace-only instruction fields,
every whitespace codepoint recognized by Python, padded nonblank instructions,
opening/closing microsecond boundaries, publication boundaries, drafts/archives,
no programs, mixed collections with the open program beyond the first three,
continued public browsing, and exactly one existence query with no program-row
materialization. Query results are checked against `registration_available`.

Executed commands, with synthetic settings supplied by the isolated harness:

```text
manage.py check
manage.py test core.tests.test_home_program_availability core.tests.test_public_portal programs.test_policy_authorization --noinput --verbosity 1
manage.py test --noinput --verbosity 1
python -m pip check
manage.py check --deploy --settings=config.settings_production
git diff --check
git diff --cached --name-only
```

- Focused tests: **24 passed**, 1.701 seconds.
- Complete Django suite: **407 passed**, 85.734 seconds; no failures or skips.
  This includes the focused tests; counts are not additive.
- Django system checks: no issues. Dependency check: no broken requirements.
- Synthetic production deployment check: no errors; existing `security.W005`
  and `security.W021` warnings remain for intentionally unenabled HSTS
  subdomain/preload options. No settings were weakened or changed for G07.
- Offline migration-state comparison: no model changes requiring migrations;
  `MigrationLoader(None)` was used without any database connection.
- `git diff --check`: passed. Staged index: empty, so no unexpected/private
  files, secrets or credentials are staged. Only the five listed G07 paths
  differ from the starting checkout; all synthetic fixtures are nonsensitive.
- Django removed its disposable test database and the isolated MySQL process
  stopped. Synthetic server artifacts remain outside the repository in the OS
  temporary directory. No existing local or hosted database was accessed.

## Limits and release

Availability is evaluated when the homepage is requested; existing application
guards still recheck policy on use. The SQL predicate must stay aligned if the
authoritative property changes; parity tests protect that boundary. This is a
native MySQL implementation and was not validated against alternative engines.
Browser visual QA and hosted acceptance are outside this increment; existing
markup/classes remain intact apart from the availability condition and text.

No migrations are required. Review this increment before any commit or push to
`feature/events`; never push to `main`. A Render deployment is a separate,
manual, owner-approved milestone, with no database migration or credential
change required by G07.
