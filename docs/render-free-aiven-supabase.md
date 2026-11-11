# Render Free + Aiven MySQL + Supabase private storage — 2026-10-11

Prepared for an **online capstone demonstration using synthetic records only**. Source preparation is validated locally; hosted acceptance is still pending. The owner subsequently authorized the final review and GitHub push; see [final release review](render-free-final-review-2026-10-11.md). No hosting resource or hosted migration is authorized by that publication. The development baseline remains **70%**; unfinished business features remain unfinished.

## Deployment settings

Use private GitHub repository `Rovic-bot/capstone`, branch `feature/events`, repository root (leave Root Directory blank), Python Web Service, **Free instance**. Keep auto-deployment off until migrations and hosted acceptance are reviewed. Do not select a trial that converts to a paid plan, persistent disk, Render Postgres, worker or cron service.

- Python: `3.14.5` from `.python-version`; requirements retain Django 5.2.17 and mysqlclient 2.3.0.
- Build: `bash scripts/render-build.sh`.
- Start: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --worker-class gthread --threads 2 --timeout 120 --max-requests 500 --max-requests-jitter 50 --error-logfile -`.
- Health check: `/healthz/` (minimal GET/HEAD liveness, no private data or database queries).
- Neither build nor startup runs migrations or creates users. Access logging is not enabled by this command; do not add logs containing evidence URLs, request bodies or credentials.

One worker and two request threads limit concurrency and DB connections. S3 transfers use no background transfer threads; reads spool beyond 1 MiB to secure temporary files that close with the response. These are transient buffers, not persistent evidence. Existing image decoding and upload limits are preserved. This is a conservative starting configuration, **not a measured Linux memory guarantee**. Measure RSS during simultaneous synthetic image uploads and downloads before accepting the demo. A health check alone proves neither DB availability nor storage privacy.

Render Free loses local files on restart/spin-down, has no persistent disk, shell or one-off jobs, and can suspend services for excessive outbound traffic. Expect cold starts after inactivity. Monitor build, bandwidth and instance-hour quotas; enforce available spend limits and do not approve overages or upgrades. [Render Free limits](https://render.com/docs/free).

## Environment names (never commit real values)

| Name | Purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings_production` |
| `DEBUG` | `False`; production refuses true |
| `SECRET_KEY` | Owner-provisioned deployment-only secret, at least 50 characters |
| `ALLOWED_HOSTS` | Explicit assigned Render hostname and any approved custom hostname |
| `CSRF_TRUSTED_ORIGINS` | Matching HTTPS origins, no wildcards |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Dedicated synthetic Aiven database and restricted runtime account |
| `DB_HOST`, `DB_PORT` | Exact Aiven hostname and port; never a local address or an IP substituted for the hostname |
| `DB_SSL_CA` | Absolute path to Aiven CA certificate; Render secret file available at build and runtime |
| `DEPLOYMENT_STORAGE_BACKEND` | Required, exactly `supabase`; unknown/missing values fail startup |
| `SUPABASE_PROJECT_REF` | Hosted project's 20-character reference |
| `SUPABASE_STORAGE_BUCKET` | Existing private bucket; lowercase DNS-safe name, 3–63 characters |
| `SUPABASE_S3_REGION` | Region shown in the project's Storage S3 settings |
| `SUPABASE_S3_ACCESS_KEY_ID` | Server-only S3 access key ID |
| `SUPABASE_S3_SECRET_ACCESS_KEY` | Server-only S3 secret, distinct from API key |
| `SUPABASE_SECRET_KEY` | Server-only `sb_secret_…` API key for read-only bucket-privacy checks |
| `SECURE_HSTS_SECONDS` | Default 3600; review domain/TLS before increasing |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | Default false; require domain review before changing |

Render supplies `PORT`. Optional `PYTHON_VERSION`, if set, must match `.python-version`. Existing upload/rate-limit settings retain approved defaults. `PRIVATE_MEDIA_ROOT` is obsolete for production; setting it cannot enable filesystem fallback. `DB_TEST_NAME` is only for an explicitly disposable test database; never run the suite using a hosted runtime account or the owner's normal DB.

No actual credential/certificate is supplied in source. **Previously exposed database credentials must be revoked/rotated before any actual hosted connectivity. Do not retrieve or reuse the old password.** Provision fresh runtime and operator credentials separately. Production disables `.env` loading, so missing deployment values cannot silently select local database credentials. Use Render secret environment values and a secret file for the downloaded provider CA, named `aiven-ca.pem`, with `DB_SSL_CA` pointing to `/etc/secrets/aiven-ca.pem`. Confirm its availability during build and runtime. Do not weaken `VERIFY_IDENTITY`, HTTPS, cookies or explicit-host checks to troubleshoot a connection. [Render secret files](https://render.com/docs/configure-environment-variables#secret-files).

## MySQL / Linux compatibility

Keep `django.db.backends.mysql`, utf8mb4, strict SQL mode, provider CA and `ssl_mode=VERIFY_IDENTITY`. Connection reuse is 60 seconds with health checks. Aiven requires its project CA for identity verification. Choose the Free MySQL service, compatible MySQL version, nearby region and the least-privilege runtime account; use a separately controlled migration account. Confirm provider-supported network restrictions for the operator and Render outbound addresses. [Aiven TLS](https://aiven.io/docs/platform/concepts/tls-ssl-certificates).

Aiven currently documents 1 GB storage and a 76-connection ceiling for Free MySQL; confirm quotas, backup retention and restore access in the selected account. Retain owner-controlled synthetic backups before schema changes. Do not assume a new hosted service already contains reference configuration. [Aiven Free MySQL](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier).

The native Linux build must compile/import mysqlclient using compatible MySQL/MariaDB client development libraries, a C compiler and `pkg-config`. A MariaDB client library does not change the database engine, but TLS identity verification must still be tested. The build script now checks native imports before Django/static checks. Render's documented toolchain does not promise all mysqlclient development libraries. A successful Windows install is not proof of a successful Linux build. If native build prerequisites are missing, stop and review a packaging fix; do not silently switch database engines, drivers or paid plans. [mysqlclient build prerequisites](https://github.com/PyMySQL/mysqlclient), [Render runtime tools](https://render.com/docs/native-runtimes).

No local WSL distribution or running Docker Linux engine was available during preparation. Gunicorn startup, actual Render image compatibility and Linux memory use remain unexecuted acceptance checks.

## Private object storage contract

Create a dedicated Supabase **Free** project and a **private** bucket only after owner review. Supabase is used for object storage, not Django's relational database or member authentication. Do not add anonymous/authenticated object-read policies or public bucket access. Keep all S3/API credentials server-side; no Supabase browser SDK or public upload route is introduced. Free currently includes 1 GB file storage and can pause for inactivity; monitor quotas and availability before a demonstration. [Supabase pricing](https://supabase.com/pricing).

The adapter uses django-storages 1.14.6 and pinned boto3/botocore, HTTPS certificate verification, path-style S3v4 requests, bounded retries and the direct storage endpoint derived from the project reference. Optional AWS checksum headers are restricted to required operations for compatibility. It sends no unsupported ACL header. Supabase S3 credentials bypass RLS: Django's existing permission and publication gates remain the access boundary. [S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication), [S3 API compatibility](https://supabase.com/docs/guides/storage/s3/compatibility).

Because Supabase does not support S3 ACL inspection, every adapter read/write/existence/delete/size operation first retrieves `/storage/v1/bucket/{bucket}` using the server API key and requires the matching bucket ID with `public: false`. No positive privacy result is cached. Redirects, malformed metadata, public buckets and network/authentication failures block the operation. The API key is an additional credential for this check, not the S3 secret. Project owners must protect settings and RLS from out-of-band changes; a bucket flag check cannot prove the absence of permissive RLS policies or eliminate a concurrent configuration change. [Bucket metadata API](https://supabase.com/docs/reference/python/storage-getbucket), [server API keys](https://supabase.com/docs/guides/getting-started/api-keys).

`storage.url()` is disabled, including signed URLs. `path()` and application object listing are unsupported. There is no public media route or CDN media mapping. Existing Django membership/member/program document downloads, photo previews, and announcement/event image publication gates stream through server-side storage reads. Public images use a neutral `image.png` response filename. Templates do not receive storage URLs or credentials. Object keys remain internal DB references.

Existing code uses storage `open/save/exists/delete`, not runtime `FileSystemStorage.path()`. No domain-service rewrite was needed. Existing missing-file 404s, evidence digests, required-evidence approval blocks and audit events remain. Provider failures are sanitized OSErrors, never successful uploads or local fallback. Some existing views return a generic 500 on provider outage (photo views may return 404); retry only after checking service health. Do not approve evidence while storage is unavailable.

Photo/document corrections retain historical evidence. CMS image replacement/removal deletes the old object only after DB commit. Failed intake/audit work rolls back DB rows and attempts uploaded-object cleanup. Object storage and MySQL are not one distributed transaction: an interrupted transfer/failed cleanup can leave a private orphan. Review keys against current **and historical/shared** references before any separately approved cleanup; never mass-delete the bucket or enable an automatic lifecycle that removes evidence history. Bucket/database backups must be coordinated.

Static assets remain in WhiteNoise `CompressedStaticFilesStorage`. It collects only repository static assets, preserving approved UI files; media never enters STATIC_ROOT. Local development still uses `config.settings` and FileSystemStorage with no cloud credentials needed.

## Controlled external migration procedure (not executed during preparation)

Render Free cannot run a shell or one-off job. Use the owner's trusted computer in a **new temporary PowerShell process**, or another separately approved controlled environment. Use a reviewed checkout of `feature/events`; no real records, local dumps or local media are copied.

1. Owner approves the reviewed diff and deployment settings first. Create/choose the free Aiven service and a dedicated empty synthetic DB, obtain the exact hostname/port and CA through Aiven, restrict operator access, and review all existing migration files. Back up any existing synthetic hosted data and document rollback; MySQL DDL is not generally transactional.
2. Install `requirements-production.txt` in a trusted virtual environment. Inject the environment names above through a secret manager or session-only prompts. Use hosted migration credentials temporarily; do not edit the normal development `.env`. Set `DB_SSL_CA` to the absolute local CA path. Do not put passwords on a command line, in a transcript or in Git. For secret prompts use `Read-Host -AsSecureString` and pass the resulting value only through process environment, then close the process when finished.
3. Before any write, verify the target from production settings and prove an encrypted connection. The following read-only command refuses local/non-Aiven hosts. Compare the host and database it prints with the owner-approved service, **not** the local `santolan_pwd` database:

   ```powershell
   .\.venv\Scripts\python.exe manage.py shell --settings=config.settings_production -c "from django.conf import settings; from django.db import connection; d=settings.DATABASES['default']; assert d['HOST'].endswith('.aivencloud.com'), 'Expected approved Aiven host'; print('Target:', d['HOST'], d['PORT'], d['NAME']); c=connection.cursor(); c.execute('SELECT DATABASE(), @@version, @@sql_mode, @@character_set_connection, @@default_storage_engine'); print(c.fetchone()); c.execute('SHOW SESSION STATUS LIKE '+chr(39)+'Ssl_cipher'+chr(39)); row=c.fetchone(); assert row and row[1], 'TLS required'; print('TLS cipher:', row[1]); c.close(); connection.close()"
   ```

   Identity verification is enforced by the configured CA and `VERIFY_IDENTITY`, not inferred from cipher presence alone. Stop on any mismatch, missing strict mode/utf8mb4/InnoDB, or connection warning. In an isolated hosted acceptance session, also verify a wrong CA and wrong hostname fail; never turn verification off.
4. Verify bucket privacy without uploading anything:

   ```powershell
   .\.venv\Scripts\python.exe manage.py shell --settings=config.settings_production -c "from django.core.files.storage import default_storage; default_storage.check_private_bucket(); print('Private bucket metadata verified')"
   .\.venv\Scripts\python.exe manage.py check --deploy --settings=config.settings_production
   .\.venv\Scripts\python.exe manage.py migrate --plan --settings=config.settings_production
   ```

5. Review the plan and exact target; get the owner's release approval. With a single operator, no competing workers/migration process and hosted application writes disabled, run **once**:

   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate --noinput --settings=config.settings_production
   .\.venv\Scripts\python.exe manage.py migrate --check --settings=config.settings_production
   ```

6. For the empty demo only, provision the first authorized administrator interactively with `manage.py createsuperuser --settings=config.settings_production`. The operator chooses the credential; no automatic account/password is generated. Configure existing roles/reference data through approved Admin procedures. Do not automatically seed policies, publish results or enable unfinished EWAF.
7. Close the credential-bearing shell; revoke temporary migration privileges/access. Render receives the restricted runtime DB account, never a schema-owner/root account. Deploy only after approval, with the build/start commands above. Validate authentication, restricted staff access, masked Results and synthetic evidence download. Confirm anonymous bucket/object access is denied, uploads survive restart/redeploy, and withdrawal stops published image/result access. Keep application accounts restricted to the demonstration audience.

No automatic migration is added to Gunicorn, WSGI, build, health checks or request handling. Do not run tests or `flush` against the hosted demonstration DB. A separate empty disposable database is required for any hosted regression run.

## Acceptance still required

- GitHub publication is authorized after the final review; confirm the remote commit before selecting it for deployment. Hosting creation and migrations remain separate operator actions.
- Free account/project availability, region/network restrictions, actual credentials and CA delivery at build/runtime, private bucket/RLS verification.
- Linux native build and Gunicorn boot; verified Aiven TLS including negative verification checks; reviewed hosted migration plan.
- Synthetic restart persistence, unauthorized direct-object rejection, public/private download behavior, runtime memory/latency and quota checks.
- Domain/HSTS decisions: `security.W005` and `security.W021` remain visible; do not enable preload/subdomains without review.

See [actual local validation](render-free-storage-validation-2026-10-11.md). OQ-27, EWAF, reports and other unfinished features remain outside this deployment scope.
