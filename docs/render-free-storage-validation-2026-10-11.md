# Render Free / Aiven / Supabase preparation validation — 2026-10-11

> This records the initial preparation run. The later owner-authorized publication and fresh isolated validation are documented in [final release review](render-free-final-review-2026-10-11.md). The initial no-push status and test timings below remain historical evidence.

**Status: prepared and locally tested; hosted acceptance pending.** No live services, paid resources, commits or pushes were created. Started with a clean working tree on `feature/events` at `6af644a3aa6ff0062d158a3f480a92169eead8cb`. Changes remain unstaged for owner review. See the [current deployment and migration runbook](render-free-aiven-supabase.md).

## Reviewed changes

Modified existing files:

- `config/settings_production.py`: explicit Supabase backend required; remove production filesystem-media fallback, retain MySQL TLS and HTTPS controls.
- `requirements-production.txt`: pinned django-storages, boto3, botocore and s3transfer; local requirements unchanged.
- `scripts/render-build.sh`: native MySQL/Gunicorn/storage import check; no migrations or account creation.
- `announcements/views.py`: use neutral `image.png` Content-Disposition filename for existing announcement/event image responses. No publication or permission changes.
- `core/tests/test_deployment.py`: production storage selection/configuration guards; existing health/static/HTTPS tests retained.
- `docs/render-deployment-preparation.md`: link the current free-service handoff and label the older disk proposal historical.

New files:

- `config/storage_configuration.py`: validated explicit server environment inputs and fixed hosted endpoint construction.
- `documents/storage.py`: private S3 adapter, live bucket privacy checks, disabled URLs, bounded temporary buffering, sanitized failures; no filesystem fallback.
- `documents/test_storage.py`: actual SDK request stubs plus reused membership/program acceptance workflows against mocked remote storage, publication/image cleanup tests.
- `docs/render-free-aiven-supabase.md`: build/start/environment/free-tier/hosted acceptance and controlled external migration procedure.
- `docs/render-free-storage-validation-2026-10-11.md`: this report.

## Actual validation

Commands run from the repository root with its existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install 'django-storages[s3]==1.14.6'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test documents.test_storage core.tests.test_deployment --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test membership members documents core accounts programs announcements assistance events --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py check --deploy --settings=config.settings_production
.\.venv\Scripts\python.exe -m pip check
git diff --check
git diff --stat
git status --short
```

- Django system check: no issues.
- Final focused suite: **72 passed, 0 failed, 0 skipped**, 6.973 seconds.
- Affected-app suite: **383 passed, 0 failed, 0 skipped**, 78.028 seconds. Includes the focused tests; counts are not additive unique coverage.
- Production-like `check --deploy`: **0 errors, 2 warnings**, `security.W005` and `security.W021`. HSTS subdomain/preload remain false pending domain review; warnings are not hidden.
- `pip check`: no broken requirements.
- `git diff --check`: no whitespace errors; Git reports normal LF/CRLF conversion notices for existing text files.
- SDK-only diagnostic run: six tests passed after correcting the mocked ranged-download response sequence. Initial focused attempts had one SDK fixture failure, corrected before both final suites; no application tests were weakened or removed.

The deploy check ran in a subprocess with generated synthetic credentials, invalid test hostnames and a temporary CA-path fixture supplied by `ProductionSettingsTests`. It did not connect to Aiven/Supabase or the normal DB. The dummy CA is not evidence of a real TLS handshake. Static collection and serving were exercised in the deployment tests with temporary STATIC_ROOT and media, including private-media 404s. Browser QA was not rerun: no UI assets/templates/navigation changed.

Tests used the separate disposable native MySQL `test_santolan_pwd` database, with temporary filesystem media or an in-memory remote object dictionary. Django created/destroyed only that test database. No migrations were applied to the owner's normal development database. No actual PWD records or cloud credentials were used.

## What the tests establish

- Real adapter and boto3 request construction work with mocked Supabase-compatible responses, with path-style S3v4, no ACL headers, private/no-store object metadata and sequential transfers.
- Missing objects preserve missing-file behavior; public/unverifiable buckets and storage failures fail closed. Provider details and object URLs are not returned to clients. No automatic local fallback, presigned URL, public media route or in-place evidence write is available.
- Remote uploads can be reopened through a fresh adapter without local files. Larger reads use a closed temporary spool. This proves adapter independence, not hosted restart durability.
- Existing onsite membership intake, manual PRPWD/approval controls, evidence validation/limits, idempotency, protected downloads, audit rollback and official Member creation still pass against the remote adapter.
- Program submission/reference/photo-review/correction workflows pass against remote storage. Replacements retain historical photos and references; deleted evidence blocks downstream review.
- CMS image replacement/removal deletes obsolete objects after commit, and public access follows publication/withdrawal state. Served image headers do not reveal object filenames.
- Local regression suite covers accounts/RBAC, Members, DEC-027 guidance, public/admin navigation, program applications, assistance, announcement/result publication and public Results privacy. Existing services and permissions were reused unchanged.

## Security and unchanged scope

Only production settings select remote storage. `config/settings.py`, local DB configuration, ordinary FileSystemStorage behavior, all models/migrations, domain services, permission code, UI templates/styles/scripts and navigation are unchanged. Existing upload validation is retained. The approved Admin UI, eight Admin groups, seven public sections, DEC-025 and DEC-027 remain covered by current regressions. This does not claim complete OQ-27 evidence-policy enforcement.

Current changed/new source contains environment names and generated synthetic test credentials only. Private credentials, CA files, uploads, local databases and virtual environments remain excluded. The exact reviewed patch (including new files) is saved locally under ignored `.local/render-free-preparation/review.diff`; nothing is staged or published. The final file/path review confirms no UI, domain model, migration or development environment file changes.

## Remaining limits

- No installed local WSL distribution/running Docker Linux engine: Linux mysqlclient compilation, Gunicorn boot and Render memory consumption are unvalidated. Windows imports/tests do not prove those outcomes.
- No hosted credentials/resources used: Aiven TLS identity checks, bucket/API/S3 authentication, anonymous/RLS access tests, hosted migration plan, backup restore and restart persistence await controlled synthetic acceptance.
- Free-service quotas, inactivity and external network dependencies can interrupt the demonstration. No paid fallback or automatic upgrade is authorized.
- Provider outage returns existing generic error responses; no dedicated outage UX is introduced. Failed cleanup can leave private orphan objects requiring a reviewed reconciliation; do not delete historical/shared evidence automatically.
- Bucket metadata checks require an extra server-only Supabase secret API key; they do not audit all project RLS policies or eliminate concurrent owner changes. Restrict project administration and verify anonymous access during hosted acceptance.

**Development baseline: 70%, unchanged. Schema changes: NONE. New migrations: NONE. Normal development data modifications: NONE. Live deployment: NONE.**
