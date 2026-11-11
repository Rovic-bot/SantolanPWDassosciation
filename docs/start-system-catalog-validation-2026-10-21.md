# Local startup catalog repair — October 21, 2026

The reported launcher failure was caused by the unapplied
`members.0005_controlled_disability_catalog` data migration. The startup guard correctly
blocked an application migration. No change to the guard or launcher was required.

The existing migration only creates missing catalog names. It does not rename, remove,
merge or reactivate existing classifications, or reclassify members.

## Verification and application

- Added `members/test_catalog_migration.py` to verify the exact single-migration plan,
  preservation of existing catalog identities and inactive choices, completeness and
  idempotence. Existing startup regressions also ran in fresh disposable native MySQL.
- Command: `.venv/Scripts/python.exe -B scripts/g12_test_runner.py test members.test_catalog_migration core.test_local_startup --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1`.
- Result: **12 tests passed**, 48.453 seconds. The initial sandbox attempt could not
  write the temporary MySQL configuration; the approved retry completed successfully.
- Created a native SQL backup with SHA-256 verification under ignored
  `.local/backups/catalog-startup-20261021-132943/`. Credentials and records were not
  printed. Private repair evidence is in `.local/catalog-startup/state.json`.
- Restored the backup into a fresh isolated MySQL instance, verified all table/row
  fingerprints, and rehearsed only `members.0005_controlled_disability_catalog`.
- Applied that same exact forward plan to the verified project-local database on
  `127.0.0.1:3307`, using Django's MigrationExecutor inside a transaction. Before commit,
  verified that all **653 original rows across 91 tables** remained unchanged.
  The only additions were **10 catalog entries** and this migration's history row.
  No EWAF or Events migrations were applied, and no migration was faked.
- `manage.py check --database default` passed. `git diff --check` passed, with existing
  line-ending notices. The real `runlocal 127.0.0.1:8000 --noreload` server started and
  returned **HTTP 200** for `/`. The temporary verification server was then stopped so
  the owner can use `Start System.cmd` normally.

The remaining annual-observance setup notice is nonblocking and preserves its existing
scope restriction. Earlier staged/unstaged/untracked implementation work was retained;
no existing application source, migration, settings, or launch script was edited.
The owner-defined 70% milestone is unchanged. This is a local startup repair, not a
new claim of complete feature or production readiness.
