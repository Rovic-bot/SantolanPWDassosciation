# Start System launcher correction — October 16, 2026

Historical validation: the [October 17 observance startup correction](start-system-observances-fix-2026-10-17.md)
adds one separately fingerprinted deferral for `events.0006_annual_observances`, whose
public/Admin routes already handle missing storage. The EWAF fingerprint and operational
prohibition below remain intact. Other pending migrations still block startup.

The Windows launcher previously ran `migrate --check` and stopped for every pending
migration. That conflicted with the intentionally unapplied Stage 8 durable EWAF migration,
whose application is authorized only in disposable MySQL instances.

`Start System.cmd` still calls `scripts/run.ps1`. The PowerShell launcher now uses
`manage.py runlocal`, a local-server command inheriting Django's static-files development
server. It checks migration history and the actual pending plan before starting the server.
Only `ewaf.0005_durable_development`, with its reviewed content fingerprint, may be deferred.
The fingerprint normalizes CRLF/LF line endings so a Git checkout does not change policy.
Any other pending migration, a reversal, inconsistent history, or changed deferred migration
blocks startup. The command does not migrate, fake migrations, create EWAF tables, or grant
processing authority. Standard `manage.py migrate` and `runserver` commands are unchanged.

This supersedes the earlier durable-increment note advising against using the normal
launcher while 0005 was pending. The application-database migration restriction remains.
No operational database, .env, credentials or private uploads were accessed for this fix.
No scoring/ranking guard, membership/PDAO behavior, staged file or milestone changed.

Validation command (fresh disposable MySQL only):

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test core.test_local_startup --noinput --verbosity 2
```

The tests cover an up-to-date schema; the exact permitted deferral; refusal of earlier,
unrelated, future and reversed migrations; changed-file refusal; real MySQL pending-schema
inspection without writes; public home/login rendering without durable tables; and the
actual startup command reaching server dispatch. Server dispatch is mocked to avoid opening
a listener; migration inspection and page rendering are real. The operational EWAF guard
still rejects consumption. PowerShell parser validation and `git diff --check` also pass.

Final result: **5 tests passed in 4.203 seconds**, exit 0, no failures/errors/skips.
Disposable artifacts: `%TEMP%/santolan-g12-tests-_ujl3mr9/`; test output is in `django.log`.
The initial focused run also passed 5 tests in 4.155 seconds. The final run additionally
checks complete command dispatch and the newline-stable fingerprint. The earlier 898-test
full-suite result belongs to the durable increment, not this launcher fix; no new full-suite claim.
