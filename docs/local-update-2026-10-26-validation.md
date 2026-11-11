# Local development update validation — 2026-10-26

The owner requested installation of the newly pulled development update after being told its database migration and website restart were pending. Commit `80d87ba52fa0bed18e64827d5b6e181fb61eacb2` is now running from this `capstone-git` checkout at `http://127.0.0.1:8000/`.

## Database update and preservation

Verified local MySQL 8.4.11 on `127.0.0.1:3307`, database `santolan_pwd`, with its data directory under this checkout's `.local/mysql-data`. The complete pending plan contained only `ewaf.0012_dataset_policy_integration`. The migration adds two nullable configuration fields, two tables, and constraints; it contains no data backfill or policy approval.

After the disposable migration rehearsal passed, the identified local website process was stopped. A native database dump, checksum, media copy, and existing-row fingerprints were saved under ignored `.local/backups/update-80d87ba-20261026-122229/`. The dump completed successfully and the copied media hashes matched. No source records changed during backup.

Applied only:

```powershell
.venv\Scripts\python.exe -B manage.py migrate ewaf 0012_dataset_policy_integration --noinput
```

The guarded local operation verified all 386 pre-existing rows across 114 tables using their original columns after migration. Only migration/content-type/permission metadata could gain records; all other existing tables retained identical records. The new policy/review tables are empty, existing configuration fields were not populated, and `.env`, media, and the retained backup are unchanged. No migration remains pending.

Both `EWAF_DATASET_POLICY_ENABLED` and `EWAF_DATASET_SCORING_ENABLED` remain false. Installation does not adopt scoring rules, approve weights, bind programs, enable collection, or publish results. The accepted 70% milestone is unchanged.

## Test-helper portability correction

The published dataset-policy test runner pinned the migration's CRLF byte hash, while `.gitattributes` checks out Python files as LF. This caused a false rejection of the unchanged migration during the first schema rehearsal. The helper now normalizes text line endings before comparing the corresponding LF hash. The migration file, operation allowlist, disposable-database guards, and application startup guard are unchanged. Both newline representations match; substantive text changes still fail the checksum.

The first isolated run passed all 26 `ewaf.test_dataset_policy` workflow tests, with the single schema rehearsal failing at that checksum check. After the helper correction, the schema rehearsal passed independently, reversing and reapplying only 0012 while retaining synthetic legacy configuration payloads, calculations, and audits. Both runs used newly initialized disposable MySQL instances through `scripts/g12_test_runner.py`; the application database was never a test target.

```powershell
.venv\Scripts\python.exe -B scripts\g12_test_runner.py test scripts.dataset_policy_schema_tests ewaf.test_dataset_policy --testrunner scripts.dataset_policy_test_runner.DatasetPolicyTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe -B scripts\g12_test_runner.py test scripts.dataset_policy_schema_tests --testrunner scripts.dataset_policy_test_runner.DatasetPolicyTestRunner --noinput --verbosity 1
```

## Running website and checks

The website restarted with the normal `runlocal` migration guard and automatic code reload. Django database checks, missing-migration checks, and pending-migration checks passed. HTTP requests returned 200 for Home, Admin login, Programs, Announcements, Membership guidance, Resources, and Results. Updated page asset references were verified on the four redesigned public pages; both new Programs and Announcements stylesheet requests returned 200. HTTP evidence and process logs remain in `.local/update-80d87ba/`.

For future startup on this computer, use the configured local launcher from `capstone-git`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1
```

The separate `Start System.cmd` shortcut still targets an unavailable machine-specific demonstration runtime. No shortcut was changed by this update. No full-system test suite, authenticated end-to-end browser pass, visual review, public hosting deployment, commit, or push is claimed.
