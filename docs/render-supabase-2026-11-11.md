# Current Render and Supabase deployment

This deployment follows the owner's November 11 authorization to publish the current application and copy its existing local records and uploads. It supersedes the older Aiven/MySQL hosting instructions for this deployment only. Local development remains MySQL. The public repository stores source, never member records, credentials or private uploads.

## Source and services

- Repository: `Rovic-bot/SantolanPWDassosciation`, branch `deployment/free-render-supabase`, based on the complete `development` snapshot `ba1d2c6cde7f5d8ce3b30238d0e5642aa1bd5270`.
- Render: owner-approved **My workspace**, **Free**, Singapore; Docker runtime. Existing older Render services are separate and are not replaced.
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

The tracked Supabase CA is a public trust certificate downloaded from the project's Database settings, not a credential. Do not disable certificate or hostname verification. The runtime database role `santolan_app` has application DML/sequence access without schema ownership. A separate `santolan_migrator` role owns the private schema and is used only by the operator. Do not put migration credentials on Render. The schema is not granted to anonymous or authenticated Supabase API roles; Django enforces staff/member access rules.

## Migration and rollback

Before copying, the operator made a consistent private MySQL backup, a typed row snapshot and a ZIP of existing media with SHA-256 manifests. A disposable PostgreSQL preview restored all 140 tables and 1,175 rows with exact normalized row digests, checked foreign keys and reset identity sequences. File transfer verifies every object's content against the backup before completion.

The migration imports raw saved rows without calling model save hooks, recalculating rankings or replaying emails. Original identifiers, histories, certificate bytes, annual-observance records, password hashes and publication decisions remain intact. The source MySQL database and local media remain available as a separate backup. Once the online application accepts changes, its PostgreSQL database is authoritative for online activity: local and online databases do not synchronize automatically. Do not rerun the original restore over a used online database.

For future schema changes, back up PostgreSQL and private objects, review the migration plan, then apply it from a trusted operator environment with verified TLS and migration credentials. Test against a disposable database first. Free Render does not provide an interactive service shell. Restore a failed migration into a separate verified target; do not reset live data. Keep database backups, object manifests/content and the encryption secret available through separate protected backup channels. GitHub is not a database backup, and no automated backup schedule is established by this deployment.

## Validation and limits

- 130 focused tests passed on a separately created, network-restricted PostgreSQL test cluster. Coverage includes current household scoring and history retention, receipt/undo/publication gates, representative notifications, Gmail and pending/approval/PDAO decision emails, annual-observance editing, and the HTTPS email backend.
- PostgreSQL compatibility fixes retain row locks while avoiding a nullable outer join during result publication/release checks; a historical document migration flushes deferred constraint triggers before schema alteration.
- Production configuration passes checks apart from the intentionally unenabled HSTS subdomain/preload options. These require an explicit domain policy; HTTPS, secure cookies, exact hosts and HSTS for the assigned host remain enforced.
- Gmail authentication through the deployed relay is verified. Real recipient delivery, recipient inbox placement and every provider rejection cannot be proven by mocked tests. No migration or deployment check sends notices to members.
- Build success and route checks do not establish a concurrency limit, full UAT, WCAG compliance or a security certification. LibreOffice batch conversion and concurrent requests still require measured capacity testing on the Free instance.
- Free service quotas and inactivity behavior apply. Render can cold-start after inactivity; Supabase may pause an inactive Free project. No paid worker, disk or database is provisioned. Existing in-process background email work is not a durable queue; interrupted delivery must be reviewed through the saved delivery status before retrying.

Hosted activation and final verification evidence should be added after the actual deployment completes. Do not interpret this preparation note as proof that a service is already live.
