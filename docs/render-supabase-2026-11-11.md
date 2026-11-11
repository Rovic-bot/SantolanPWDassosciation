# Current Render and Supabase deployment

This deployment follows the owner's November 11 authorization to publish the current application and copy its existing local records and uploads. It supersedes the older Aiven/MySQL hosting instructions for this deployment only. Local development remains MySQL. The public repository stores source, never member records, credentials or private uploads.

## Source and services

- Repository: `Rovic-bot/SantolanPWDassosciation`, branch `deployment/free-render-supabase`, based on the complete `development` snapshot `ba1d2c6cde7f5d8ce3b30238d0e5642aa1bd5270`.
- Render: owner-approved **My workspace**, **Free**, Singapore; Docker runtime, service `srv-dbq0gdd6e07s73bol0l0`, live at <https://santolan-pwd-system.onrender.com>. Existing older Render services are separate and are not replaced.
- Supabase: **santolan-pwd-system**, Singapore, project `deetmrupqsyidjyeefui`, in **Rovic-bot's Org**, Free.
- Database: PostgreSQL through the IPv4 session pooler, verified TLS, application schema `santolan`.
- Private files: bucket `santolan-private`; existing Django permission-checked views remain the access boundary. No public `/media/` route or storage URL is introduced.
- Email: the saved Association Gmail account, through a private HTTPS-to-Gmail relay in Supabase Edge Functions because Render Free blocks SMTP. The relay authenticates a server-only random bearer token, accepts only the connected sender, uses Gmail port 465 with verified TLS, does not log credentials, and does not retry uncertain delivery automatically.

## Build and configuration

The `Dockerfile` installs Python 3.14.5, the pinned production requirements, LibreOffice Writer and fonts. It runs a fictional certificate PDF conversion during image construction. `scripts/render-start.sh` checks settings, collects static assets, then starts Gunicorn on `0.0.0.0:$PORT` with one worker and three request threads. Neither build nor startup runs migrations, imports data, seeds records or sends email.

Render environment variables are the configuration source of truth. Auto-deploy is disabled: push reviewed changes to the deployment branch and manually deploy the desired commit. Keep runtime secrets out of Docker build arguments, source and logs.

Required configuration names:

| Group | Names / settings |
| --- | --- |
| Django | `DJANGO_SETTINGS_MODULE=config.settings_production`, `PYTHON_DOTENV_DISABLED=1`, `DEBUG=false`, `SECRET_KEY`, explicit `ALLOWED_HOSTS`, HTTPS `CSRF_TRUSTED_ORIGINS` |
| PostgreSQL | `DB_ENGINE=postgresql`, `DB_NAME=postgres`, `DB_HOST`, `DB_PORT=5432`, `DB_USER`, `DB_PASSWORD`, `DB_SSL_CA=/app/deploy/supabase-ca.crt` |
| Storage | `DEPLOYMENT_STORAGE_BACKEND=supabase`, `SUPABASE_PROJECT_REF`, `SUPABASE_STORAGE_BUCKET`, `SUPABASE_S3_REGION`, `SUPABASE_S3_ACCESS_KEY_ID`, `SUPABASE_S3_SECRET_ACCESS_KEY`, `SUPABASE_SECRET_KEY` |
| Gmail | `EMAIL_HTTPS_RELAY_URL`, `EMAIL_HTTPS_RELAY_TOKEN`, `CERTIFICATE_EMAIL_PROVIDER=gmail`, `CERTIFICATE_EMAIL_BACKGROUND=true`, `EMAIL_TIMEOUT=30` |
| Certificates | `CERTIFICATE_OFFICE_EXECUTABLE=/usr/bin/soffice` |
| Current features | `EWAF_VAULT_ENABLED=true`, `EWAF_DATASET_POLICY_ENABLED=true`, `EWAF_DATASET_SCORING_ENABLED=true`, `PROGRAM_APPLICATION_WORKFLOW_ENABLED=true`, `REFERRAL_ENABLED=true`, `ONLINE_MEMBERSHIP_ENABLED=true` |
| Current policy | `PDAO_ENFORCEMENT_ENABLED=false`, `SHORT_REFERENCES_ENABLED=false`, `ASSOCIATION_REGISTRATION_POLICY_FILE=config/registration_policy.development.json` |

The migrated secret key must remain available to decrypt the existing saved Gmail app password and verify historical signatures. Future key rotation must preserve appropriate fallbacks or explicitly re-encrypt dependent values. Existing staff password hashes and permissions are transferred; no default account is provisioned.

The tracked Supabase CA is a public trust certificate downloaded from the project's Database settings, not a credential. Do not disable certificate or hostname verification. The runtime database role `santolan_app` has application DML/sequence access without schema ownership. A separate `santolan_migrator` role owns the private schema and is used only by the operator. Do not put migration credentials on Render. The schema is not granted to anonymous or authenticated Supabase API roles; all 140 application tables have RLS policies restricted to the server role, and Django enforces staff/member access rules. Apply the same grants and RLS policy to any new tables during future operator migrations.

## Migration and rollback

Before copying, the operator made a consistent private MySQL backup, a typed row snapshot and a ZIP of existing media with SHA-256 manifests. A disposable PostgreSQL preview restored all 140 tables and 1,175 rows with exact normalized row digests, checked foreign keys and reset identity sequences. File transfer verifies every object's content against the backup before completion.

The migration imports raw saved rows without calling model save hooks, recalculating rankings or replaying emails. Original identifiers, histories, certificate bytes, annual-observance records, password hashes and publication decisions remain intact. The source MySQL database and local media remain available as a separate backup. Once the online application accepts changes, its PostgreSQL database is authoritative for online activity: local and online databases do not synchronize automatically. Do not rerun the original restore over a used online database.

For future schema changes, back up PostgreSQL and private objects, review the migration plan, then apply it from a trusted operator environment with verified TLS and migration credentials. Test against a disposable database first. Free Render does not provide an interactive service shell. Restore a failed migration into a separate verified target; do not reset live data. Keep database backups, object manifests/content and the encryption secret available through separate protected backup channels. GitHub is not a database backup, and no automated backup schedule is established by this deployment.

## Validation and limits

- 130 focused tests passed on a separately created, network-restricted PostgreSQL test cluster. Coverage includes current household scoring and history retention, receipt/undo/publication gates, representative notifications, Gmail and pending/approval/PDAO decision emails, annual-observance editing, and the HTTPS email backend.
- PostgreSQL compatibility fixes retain row locks while avoiding a nullable outer join during result publication/release checks; a historical document migration flushes deferred constraint triggers before schema alteration.
- Production configuration passes checks apart from the intentionally unenabled HSTS subdomain/preload options. These require an explicit domain policy; HTTPS, secure cookies, exact hosts and HSTS for the assigned host remain enforced.
- Gmail authentication through the deployed relay is verified. After explicit owner approval, one self-addressed deployment test with a fictional PDF attachment was accepted by Gmail SMTP through the production-configured backend and relay. The local operator invoked this check using the same cloud configuration; it was not a member notification or a Render-originated business decision. The connected Gmail reader belongs to a different mailbox, so inbox receipt is not independently verified. Future recipient delivery and spam classification remain provider-dependent. No migration or deployment check sends notices to members.
- Build success and route checks do not establish a concurrency limit, full UAT, WCAG compliance or a security certification. LibreOffice batch conversion and concurrent requests still require measured capacity testing on the Free instance.
- Free service quotas and inactivity behavior apply. Render can cold-start after inactivity; Supabase may pause an inactive Free project. No paid worker, disk or database is provisioned. Existing in-process background email work is not a durable queue; interrupted delivery must be reviewed through the saved delivery status before retrying.

## Hosted activation evidence

Render deployment `dep-dbq0hp2jnfac73ene170` reached `live` on November 11, 2026, at 06:20 UTC, running commit `ab91723d3837f08a8091ca7ddbf6ef133b0078fe`. The first image passed Linux PDF conversion but startup could not create the static collection directory; the final Dockerfile explicitly creates it for the unprivileged runtime user and verifies writability during the build.

- Cloud transfer verified all **140 tables / 1,175 original rows** against normalized source-row digests, including identifiers, saved configuration and audit history. All **19 uploaded files / 13,810,107 bytes** matched their original SHA-256 hashes.
- A final source check found **no changed local tables or uploaded files** since the backup. The migration preserved the original local system.
- **157 hosted HTTP checks passed**, covering the health endpoint, 10 public routes, 78 referenced static assets, 8 published images, 3 published result pages, 23 Admin workspace pages, each saved program's management/application/EWAF/release views, all **12 saved annual observances**, a member record and CSV/XLSX/PDF report exports. These are availability/content checks, not exhaustive browser interaction or load tests.
- Additional hosted private-registration-file and retained-certificate downloads matched the original bytes for an authenticated staff session. Anonymous requests to those URLs and the dashboard reached the login page; `/media/` returned 404. The temporary verification sessions were deleted. Ordinary report/download access audits remain retained.
- The production storage adapter completed a fictional write/read/delete probe, and anonymous direct object access was denied. The original 19 files remained private. A Supabase security-advisor check reported no notices.
- A private PostgreSQL custom-format backup was created after activation, and its restore catalogue was verified. This complements the retained original MySQL dump and media archive; a full cloud-backup restore rehearsal and automated backup scheduling remain separate operational work.
- No runtime error logs were found during the hosted checks. A visible browser inspection confirmed the deployed public homepage and its artwork loaded.

The final verification notes may be committed after the live code commit; documentation-only commits do not require replacing a working deployment. Future functional changes still need review, appropriate tests, a backup where relevant and an explicit manual Render deployment.
