# Program draft and EWAF publication guidance - 24 October 2026

## Report and diagnosis

The owner reported that creating a program displayed `configuration: no program-specific scoring configuration has been recorded`. Inspection confirmed that the program already existed as an authorized private draft with EWAF enabled and no operational scoring configuration. The error originated from the publication guard, not draft creation. The create form and publication page did not make that distinction clear, and the shared error summary directed an administrator to the public Help Desk.

## Scoped correction

- The enabled workflow labels creation **Save program draft** and explains the later approval/configuration steps. The program review page explicitly confirms a saved draft.
- The publication guard retains its existing requirements, with actionable messages for missing/invalid, unlocked and stale EWAF configurations. The same read-only check supplies the setup guidance beside publication controls.
- Authorized staff have a **Complete EWAF settings** link directly to the program's scoring settings. Staff without those permissions receive appropriate administrator guidance. The existing permissions continue to protect the destination.
- EWAF provides a return link to program review and a permission-checked link to its existing evidence-definition editor. Evidence definitions, approved scoring rules/weights and explicit locking remain required; no policy values or approvals were supplied automatically.
- Publication errors confirm that the saved program is retained. Public application error guidance remains unchanged.
- Source audit-history rendering was aligned with the already-existing runtime handling of structured/list audit values, after the source regression suite exposed that discrepancy. This is a display-only correction; historical audit rows are untouched.

No migration, publication, authorization, member update, scoring calculation, beneficiary decision or release was performed on the populated development database. Seven scoped files were synchronized to the running local workspace, preserving its integration hooks and unrelated files. The source-only audit display correction was already present there.

## Validation

- Source: **64 tests passed** (`programs.test_application_workflow` and `programs.tests.ProgramTests`) against a guarded disposable MySQL schema. Log: `.local/dual-registration-20261024/temp/santolan-g12-tests-cvgy9btr/django.log`.
- Runtime: **64 tests passed**, same suites against a separate disposable MySQL database with runtime migrations. Log: `.local/household-criteria-20261024/temp/santolan-g12-tests-zyz5fgvv/django.log`.
- Regression coverage includes actual Admin draft creation without a configuration, navigation to settings and evidence definitions before publication, blocked publication retaining program/history exactly, denied access for staff without EWAF permissions, and the existing approved-lock/publication/source-freshness checks.
- Read-only live-runtime rendering verified the owner's existing draft, setup link, settings/evidence forms, create page and return link. This did not log into an account or write business data.
- Django database checks passed; no pending migrations or model changes were detected. `git diff --check` passed.
- Preservation check: **81,278 existing rows across 107 business tables unchanged**, including program, application, member, configuration, score, selection, release and audit data. Only session/throttle tables are excluded from comparison. Private baseline hashes and scoped file backups are retained in `.local/program-publication-help-20261024/`.
- The identified local development server on port 8003 was restarted with the updated code. Browser visual QA was not performed; a previous browser-launch approval rejection was respected.

The program still needs its actual approved EWAF configuration before it can be published. This correction makes that requirement and the setup route explicit; it does not authorize missing policy values or claim production acceptance.
