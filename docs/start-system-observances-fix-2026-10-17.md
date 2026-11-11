# Start System observance compatibility correction

Date: October 17, 2026. Branch: `feature/events`. Milestone: **70%, unchanged**.

## Cause and correction

The owner reported Start System failing inside `runlocal.check_migrations()` with both
`events.0006_annual_observances` and `ewaf.0005_durable_development` pending. The earlier
startup rule permitted only the reviewed EWAF deferral, so adding the unapplied Events
migration prevented the whole website from starting. The observance implementation had
already implemented missing-table handling, but the startup guard blocked before reaching it.

`core/management/commands/runlocal.py` now also permits exactly the reviewed Events 0006
migration, pinned to its newline-normalized SHA-256. Existing EWAF fingerprint validation
is preserved. Changed migration contents, other/earlier/future migrations, reverse plans
and inconsistent migration history continue to block startup. A pending migration causes
clear feature-specific console messages. This does not run or fake migrations, relax EWAF
operational authorization, change permissions, or seed/publish records.

This is a reversible startup compatibility fix authorized by the owner's reported problem.
It is not approval to migrate the working database. Annual observance editing/photo uploads
remain unavailable until the separate working-database Events migration is approved and
applied. The public calendar safely shows empty months, Admin shows Setup pending, and
create/edit requests fail closed. Existing actual association Events continue to load.

## Validation

Disposable MySQL regression command:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test core.test_local_startup events.test_observances events.test_observance_workflow --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
git diff --check
```

The existing harness creates a fresh isolated MySQL instance with `.env` disabled and
restricted disposable database grants. All actors and Event fixtures are fictional.
The new database regression reproduces both missing migrations, verifies startup inspection
uses only SELECT/SHOW and leaves table/migration history unchanged, checks public home,
login, upcoming/past Events and Admin pending-storage behavior, and reaches the actual
runlocal server-dispatch boundary (listener mocked). Existing EWAF-disabled checks remain.
Policy tests cover the Events deferral alone/together with EWAF, changed fingerprints,
reversals and unrelated/future migrations.

Focused result: **47 passed, 0 failures/errors**, 40.377 seconds; exit 0. Django system
checks reported no issues. Artifact directory suffix: `hvu9tpsm`. `git diff --check`
passed with only existing line-ending notices.
The earlier **942 passing** full-suite result remains historical evidence for the
observance implementation; no new full-suite result is claimed for this startup correction.

The corrected startup migration check was also executed against the project-local
`127.0.0.1:3307` connection after asserting host and port. It exited 0, reported both
deferrals correctly, and reported that no migrations were applied or faked. This was
metadata-only inspection, not a test fixture run against application data. No application
records, permission grants, credentials or uploads were displayed or changed. No new
background website process was launched; the owner can restart their existing launcher.

## File inventory and preservation

- `core/management/commands/runlocal.py`: exact fingerprinted Events deferral and accurate
  console messages; preserves the existing EWAF deferral and consistency checks.
- `core/test_local_startup.py`: additional policy tests and real disposable pending-schema
  regression, retaining the previous startup checks.
- `docs/start-system-migration-deferral-2026-10-16.md`: historical note linking this update.
- `docs/annual-observances-persistence-validation-2026-10-17.md`: supersede its prior
  startup-blocking limitation without rewriting prior test evidence.
- `docs/start-system-observances-fix-2026-10-17.md`: this record.

Preservation baseline: 543 nonignored files, captured before edits in
`.local/observances-startup-20261017/baseline.json`. Final verification found only the four
intended existing files changed, this one new record added, and **539 baseline files
byte-for-byte unchanged**. Git index/HEAD are unchanged; branch remains `feature/events`.
Evidence: `.local/observances-startup-20261017/preservation.json`.
No EWAF source/migration, Start System.cmd, PowerShell launcher, operational database
schema, member record, .env or private upload was edited. No pull/reset/stash/clean,
staging/commit/push/merge/deployment occurred.

To retry: stop the failed launcher with Ctrl+C, close that window, and open
`Start System.cmd` again. The pending-feature notices are expected; they no longer stop
the existing website. Photo editing is not enabled by bypassing its storage requirement.
