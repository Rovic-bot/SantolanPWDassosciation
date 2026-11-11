# Render deployment preparation

**Current handoff (2026-10-11):** use [Render Free + Aiven MySQL + Supabase private storage](render-free-aiven-supabase.md), its [preparation validation](render-free-storage-validation-2026-10-11.md), and the subsequent [final release review](render-free-final-review-2026-10-11.md). The owner selected these free services for a synthetic-only demonstration and authorized publication after final checks. Production now requires an explicit Supabase backend; `PRIVATE_MEDIA_ROOT` is no longer a production configuration option. Local development remains FileSystemStorage. Live deployment and hosted migrations remain separate, unexecuted steps.

## Historical October 10 handoff — superseded deployment options

The material below records the previous disk-based proposal and its validation limits. Its persistent-disk, two-worker and undecided-provider instructions are superseded by the October 11 handoff above. Do not use the historical commands to configure this demonstration.

**Prepared configuration; live deployment is blocked pending database, persistent private storage, costs, access and domain approval.** The existing owner-defined 70% development baseline is preserved. No Render resource, database or billable service has been created. Do not copy real PWD records or uploads into a first deployment.

## Repository and service handoff

- Intended repository: `https://github.com/Rovic-bot/capstone.git`. The owner requested that it be private before pushing. See [publication validation](github-publication-validation-2026-10-10.md) for the actual push result.
- Reviewed project branch: `feature/events`. GitHub's existing `main` contains a separate initial README history and is not overwritten. Select the reviewed branch explicitly; do not deploy the initial `main` by accident.
- Service type: Render **Web Service**, Python runtime, after approval. No worker, cron, Gemini, government integration or additional service is required by this preparation.
- Repository root directory: leave blank / repository root (`.`), where `manage.py` lives. The vault and its parent paths are not a deployment root.
- Python: **3.14.5**, pinned by [.python-version](../.python-version), matching the validated local interpreter. An explicit `PYTHON_VERSION` must use the same fully qualified version. Render supports version selection through this file or environment variable. [Render Python version documentation](https://render.com/docs/python-version).
- Dependencies: [requirements-production.txt](../requirements-production.txt) includes the existing pinned dependencies, Gunicorn 26.2.0 on Linux and WhiteNoise 6.12.0. Existing local requirements are unchanged. Gunicorn is a Unix server; its execution is not validated by the Windows test environment. [Gunicorn package](https://pypi.org/project/gunicorn/).
- Build command: `bash scripts/render-build.sh`.
- Start command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60 --error-logfile -`. This is an initial configuration to validate against the approved service size, not a capacity guarantee. Request access logging is not enabled, avoiding routine logging of private query strings.
- Health-check path: `/healthz/`, available only through the production URL configuration. GET/HEAD return minimal process liveness, without member data or database queries. It is not proof of successful migrations or database TLS connectivity. [Render health checks](https://render.com/docs/health-checks).

Do not apply a Blueprint or create a service from this handoff until costs/storage/access have been approved. No `render.yaml` is supplied that would implicitly select a paid plan or database engine.

## Required environment names and secret files

Set these in the approved Render service's environment; do not commit actual values:

- `DJANGO_SETTINGS_MODULE=config.settings_production`.
- `SECRET_KEY`: new generated deployment secret, at least 50 characters, distinct from development and all synthetic tests. Do not rotate it casually after sessions are in use; plan rotations separately.
- `DEBUG=False`.
- `ALLOWED_HOSTS`: explicit comma-separated deployed hostnames; no wildcard. Include the assigned Render hostname and only approved custom domains.
- `CSRF_TRUSTED_ORIGINS`: matching explicit HTTPS origins for those allowed hosts.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: the approved deployment MySQL instance, never the owner's local development instance. Use a dedicated least-privilege application account and a separately controlled migration/operator account.
- `DB_SSL_CA`: absolute path to the database provider's trusted CA certificate supplied as a secret file, for example its assigned path under `/etc/secrets/`. The actual certificate must be available during both build and runtime. The settings require an existing file and configure `ssl_mode=VERIFY_IDENTITY`; a real handshake must still be validated before accepting the deployment.
- `PRIVATE_MEDIA_ROOT`: approved absolute mounted private path, suggested `/var/data/private-media`. Supplying a path alone does not create a persistent disk. The operator must verify that it actually points into the approved persistent mount.
- `SECURE_HSTS_SECONDS`: default 3600 for an initial reviewed HTTPS configuration; approve an appropriate long-term duration after hostname/TLS validation.
- `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`: default false. These are domain-policy decisions, not automatic production toggles. Enable only after confirming all affected subdomains support HTTPS and considering preload consequences.

Render supplies `PORT`; the start command binds to it. `PYTHON_VERSION` is optional because the checked-in version file pins the interpreter. `DB_TEST_NAME` is needed only for isolated acceptance runs, must start with `test_` and differ from `DB_NAME`; the production application account should not have test-database creation privileges.

Existing upload size, login/session and member-verification rate-limit environment options remain available. Reuse current approved defaults; do not disable limits to make deployment work. Credentials, certificates, private uploads and `.env` are excluded by Git rules. Production explicitly disables local `.env` loading and rejects DEBUG, wildcard hosts, insecure/unapproved CSRF origins, missing CA paths and media/static overlap.

## Database hosting and Linux build decisions

The system uses native **MySQL 8.4.11** locally with mysqlclient 2.3.0, strict SQL mode, utf8mb4 and InnoDB. Retain the MySQL engine and validate the approved hosted server version with the disposable regression suite. Do not automatically substitute Render Postgres, SQLite or MariaDB.

An external managed MySQL service with verified TLS is the simplest candidate to approve. Alternatively, Render documents self-managed MySQL as a Docker private service with its own persistent disk; that option adds operating, backup, certificate and cost responsibilities. Render's managed relational offering is Postgres, so its general Django example cannot be adopted verbatim for this project. [Render MySQL documentation](https://render.com/docs/deploy-mysql), [Render Django guide](https://render.com/docs/deploy-django).

Before approving the Python-native build, validate that its Linux build image provides mysqlclient's client development headers/libraries and `pkg-config`. If it cannot build the existing pinned mysqlclient, prepare and validate a Docker runtime with those OS dependencies as a separate packaging follow-up; do not change drivers/engine as a shortcut. This task has not run a Render or Linux build, and has not tested a production DB connection.

Confirm database location, access controls/network allowlisting, encryption/TLS hostname verification, backups, retention, restore procedures and costs. Start with an empty deployment database and synthetic acceptance records. No owner's local MySQL data directory, dump, root password or application records are included in GitHub.

## Private uploaded files and static assets

Existing FileSystemStorage and permission-checked attachment/image views are reused. No public `/media/` route is added. Private files use restrictive upload permissions; they are never included in `STATIC_ROOT`, WhiteNoise or a public CDN. The build only collects repository static files, including the approved Admin UI, public controls and vendored Bootstrap.

WhiteNoise uses `CompressedStaticFilesStorage` rather than a manifest backend: vendored Bootstrap references source maps that are absent, so manifest rewriting would fail or require changing approved assets. Existing stylesheet version query strings are retained. Static collection/serving and rejection of a synthetic private-media URL are tested with temporary files. [WhiteNoise configuration](https://whitenoise.readthedocs.io/en/stable/django.html).

The existing filesystem upload contract needs approved persistent private storage. Render disks attach to paid services, exist only at runtime and are available to a single instance. They are unavailable in build/pre-deploy compute. Do not write uploads to ephemeral storage, assume a free service preserves them, or use a public object bucket. Any alternative private object-storage backend would require separately scoped implementation and access tests. [Render persistent disks](https://render.com/docs/disks).

Approve disk size, region, encryption, access, backup/restore and cost. Verify a synthetic upload survives restart/redeploy and remains restricted to authorized views. Disk-only snapshots are not a complete database backup; self-hosted MySQL needs database-consistent backups. Public CMS images retain their existing approved publication gates even though they share underlying storage.

## Safe migration and release procedure

The [build script](../scripts/render-build.sh) installs reviewed requirements, runs `check --deploy` and `collectstatic`. It **does not migrate, seed users, publish content or copy data**. Gunicorn's start command also performs no migrations. No migration was created by this task.

After the database/storage/access approvals and a successful Linux build:

1. Create the approved empty deployment database using its operator procedure. Validate TLS identity, strict SQL, charset and InnoDB with synthetic data only.
2. Review existing migration files and `python manage.py migrate --plan` using production settings against the approved deployment instance. Establish a database-consistent backup and rollback plan before applying changes to an existing instance.
3. Execute `python manage.py migrate --noinput` once through an approved release/operator step. Do not run competing migration processes. Do not target the owner's development database.
4. Validate required reference configuration and account/role setup through existing authorized commands/Admin procedures. Do not invent fixture users or automatic publication. Create any first privileged account interactively with approved access; never commit its password.
5. Confirm `/healthz/`, HTTPS/proxy behavior, collected static assets, private download permissions, seven public sections, eight Admin groups and the relevant synthetic application/publication/membership regressions.
6. Confirm persistent upload retention and database backup restoration before any real-person data is separately approved for the deployment.

The proxy configuration trusts `X-Forwarded-Proto` from Render's TLS boundary. Do not expose Gunicorn directly or accept that header from an untrusted client/proxy. Production HTTPS/cookie controls are forced on even if development environment values say otherwise. [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## Local validation and remaining approvals

The publication report records actual commands, counts and security audit results. Production-like checks use generated synthetic secrets, a temporary CA-path fixture and an invalid test hostname; they make no production DB connection. The CA-path fixture is not a trusted issuing certificate and proves configuration validation only.

`check --deploy` reports **security.W005** and **security.W021** while HSTS subdomain/preload defaults are intentionally false. They are not silenced. Obtain domain-policy approval before changing those flags; an exit code of zero with these warnings is not an unconditional production-readiness pass.

GitHub privacy and source publication are verified in the publication report. Blocking deployment decisions remain: approved MySQL hosting/TLS/network/backup; persistent private media and cost; service size and region; domain/HSTS policy; Admin access and release credentials; Linux build and hosted synthetic acceptance. OQ-27 evidence-handling enforcement, controlled EWAF and reports remain unfinished and are not credited by deployment preparation.
