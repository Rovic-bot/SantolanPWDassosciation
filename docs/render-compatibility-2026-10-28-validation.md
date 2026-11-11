# Render compatibility validation — October 28, 2026

The owner requested publication of the main development system at
`http://127.0.0.1:8013/` to GitHub and deployment on Render. This record covers
local compatibility checks only. GitHub publication, hosted migrations and
Render deployment status are recorded separately. The owner-defined 70%
milestone and existing business rules remain unchanged.

## Current development and production configuration

The retained launcher selects `config.current_development_settings`, which
inherits the ordinary application settings through the isolated development
settings. Both development and production include the ordinary `config.urls`
routes and the same installed business apps. The main development system does
not use the older `main_testing` or patched `program_intake` runtime.

Production must use `config.settings_production`. Never import the development
settings on Render: those read a local connection manifest, disable historical
migrations, select local media, and add development identity routes. Production
already retains MySQL, verified database TLS, private object storage, HTTPS,
secure cookies, connection reuse and compressed static assets.

A settings-only import using the retained launcher's filtered environment
confirmed these actual values without opening a database connection:

| Setting | Main development value |
| --- | --- |
| `EWAF_VAULT_ENABLED` | `True` |
| `EWAF_DATASET_POLICY_ENABLED` | `True` |
| `EWAF_DATASET_SCORING_ENABLED` | `True` |
| `PROGRAM_APPLICATION_WORKFLOW_ENABLED` | `True` |
| `PDAO_ENFORCEMENT_ENABLED` | `True` |
| `PROGRAM_TRACKING_ENABLED` | `True` |
| `PROGRAM_TRACKING_QR_ENABLED` | `True` |
| `ONLINE_MEMBERSHIP_ENABLED` | `False` |
| `PDAO_REGISTRATION_ENABLED` | `False` |
| `SHORT_REFERENCES_ENABLED` | `False` |
| `REFERRAL_ENABLED` | `False` |
| `EWAF_FICTIONAL_DEMO` | `False` |

The current launcher disables `.env` loading. Earlier documentation describing
flags enabled in a local `.env` therefore does not establish their values on
port 8013. Set the corresponding supported deployment environment variables
explicitly to preserve this configuration; the presence of a feature in source
does not authorize activating a different workflow. These checks do not grant
any missing per-program or evidence-policy approval.

## Real migration rehearsal

**All 79 checked-in migrations applied successfully** to a newly initialized,
isolated native MySQL 8.4.11 instance. This used ordinary `migrate --noinput`,
including the full EWAF chain through `0012_dataset_policy_integration` and
membership through `0010_pdao_review_corrections`. No migration was faked and
model synchronization was not substituted for migration execution.

The existing `scripts/g12_test_runner.py` verified an empty loopback instance,
its new data directory and assigned port, then provisioned restricted grants for
its disposable databases. A task-local wrapper adapted Windows temporary-folder
ACL inheritance only under its own ignored directory. It disabled `.env`, used
generated test credentials and shut down the disposable server after completion.
The retained main database and hosted database were not targets.

Command:

```powershell
.venv\Scripts\python.exe -B .local\deploy-compatibility-20261028\run_tests.py migrate --noinput
```

Exit status: `0`. Private local log:
`.local/deploy-compatibility-20261028/tmp/santolan-g12-tests-wxquzhpp/django.log`.
The stopped rehearsal was not restarted for additional checks. This proves a
fresh schema can be built; an existing hosted database still needs a backup,
identity check and review of its own outstanding migration plan.

## Production configuration and static smoke checks

A separate process loaded `config.settings_production` with generated synthetic
secrets, invalid test hostnames, a synthetic CA-path fixture, and the current
development feature flags. No real database or storage credential was used.

- `check --deploy` completed with no errors. The existing `security.W005` and
  `security.W021` warnings remain visible because HSTS subdomain inclusion and
  preload are deliberately disabled. They were neither silenced nor enabled
  without a domain-policy decision.
- WhiteNoise static collection succeeded: 184 source assets and 176 compressed
  outputs, 360 files total, under the ignored task directory.
- The seven public navigation routes, Admin login and `/healthz/` resolved using
  production URLs. Membership's current route is `/membership/register/`.
- HTTPS `/healthz/` returned the minimal JSON response; HTTP redirected to
  HTTPS. A collected Admin stylesheet returned HTTP 200.
- `/media/private.pdf` returned HTTP 404. Development `/ewaf-demo/` and its
  identity-health route were absent. No demo middleware or disabled migration
  mapping appeared in production settings.
- Production retained the MySQL engine, `VERIFY_IDENTITY` TLS mode and an empty
  local `MEDIA_ROOT`; uploaded evidence has no local-filesystem fallback.

Command:

```powershell
.venv\Scripts\python.exe -B .local\deploy-compatibility-20261028\production_check.py
```

Final exit status: `0`. Private local log:
`.local/deploy-compatibility-20261028/production-check.log`.
An initial route assertion used `/membership/`; correcting the smoke harness to
the actual named route `/membership/register/` resolved that harness error. No
application URL was changed.

These Windows checks do not establish Linux/Gunicorn startup, live database TLS,
hosted bucket privacy, uploaded-file persistence or live latency/memory. Those
remain deployment acceptance checks. No application code or schema was changed
by this compatibility task.
