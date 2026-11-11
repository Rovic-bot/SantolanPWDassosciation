# Fresh local development database — November 10, 2026

**Fixed scoring amendment (November 10):** EWAF scoring rules are now permanent source configuration; only editable weights and audited calculation/configuration snapshots depend on MySQL. Fresh databases must not seed scoring policies or demo data. Program publication applies the code rules after actual weights are approved. See [fixed scoring validation](fixed-ewaf-scoring-2026-11-10.md).

**Subsequent owner correction:** Fixed annual observances are calendar reference configuration, not scheduled operational events. The 12 previously saved entries were restored through the audited observance service after the reset, with their saved identifiers, recurrence rules and content. Admin can click each entry in `/events/manage/observances/` to edit and publish changes. Future fresh-development resets must preserve these entries and their reference-content revision/audit records alongside essential configuration. The zero-count report below is the historical reset snapshot, before this authorized correction and subsequent manual use. See [restoration record](annual-observances-restoration-2026-11-10.md).

The owner approved a fresh local development database with zero operational records for manual testing. The previous database remains intact as an archive. No automated tests, fixture loaders, data factories, demo seed commands, operational-data restores, emails, or automatic Django account creation were performed for this reset.

## Active environment

- Website: **http://127.0.0.1:8013/**
- Administrator login: **http://127.0.0.1:8013/accounts/login/**
- Database: **`santolan_pwd_development`**, MySQL 8.4.11 at **`127.0.0.1:3309`**.
- Settings: `config.current_development_settings`, delegating to `config.fresh_development_settings`.
- Private connection settings: `.local/development/connection.json` (ignored by Git and restricted by Windows ACL).
- Fresh uploads: `.local/development/private-media`. Only the existing public homepage artwork was copied here. Old private documents and generated files remain untouched in the archived storage and have no records in the fresh database.
- `Start System.cmd`, `Restart System.cmd`, `Stop System.cmd`, and normal `manage.py` commands use the fresh environment. Startup validates the exact database, server UUID, data directory, and loopback binding. It does not create/reset/seed a database or fall back to the archived database if configuration is missing.
- The original `.env` and retained connection files are unchanged. Their old database is not the active website connection. Explicit settings arguments/environment overrides still select their named environment, as in standard Django.

## Verified counts and schema

All **96 legitimate migrations** were applied normally. No existing migration was edited, faked, skipped, or replaced by model synchronization. Read-only migration inspection reports no pending migrations, graph conflicts, or model drift. Django system checks pass.

There are **140 tables**, of which **129 operational tables contain zero rows**. This includes zero members, Association membership applications, pending registrations, PDAO registrations, programs, events, program applications, assistance requests/cases/releases, referrals, beneficiaries/selections, EWAF configurations and calculation runs, announcements/results, certificate jobs, email jobs/attempts, operational history/audits, sessions, and Django users. No report records were imported.

The complete table counts are in [record-counts.json](fresh-development-2026-11-10/record-counts.json). The 11 populated metadata/reference/configuration tables contain:

| Table | Rows | Purpose |
| --- | ---: | --- |
| `django_migrations` | 96 | Applied migration history |
| `django_content_type` | 134 | Django model metadata |
| `auth_permission` | 175 | Django/application permission definitions |
| `members_disabilitytype` | 10 | Controlled disability reference catalog |
| `assistance_eligibilitystatus` | 4 | Eligibility status labels |
| `documents_documenttype` | 5 | Legitimate document capture definitions |
| `documents_membershipdocumentrequirement` | 5 | Inactive optional capture slots from migrations |
| `membership_membershipsettings` | 1 | Preserved PRPWD link and membership gate |
| `assistance_referralsettings` | 1 | Preserved encrypted Association mail connection |
| `core_portalpage` | 1 | Existing homepage branding only |
| `programs_programtermslock` | 1 | Technical concurrency mutex; no program or approval data |

Read-only MySQL introspection found 350 foreign keys, 304 checks, 281 unique keys (including primary keys), and 544 indexes. All expected current-model tables, columns, unique fields, declared indexes/constraints, and foreign keys are present. The new database account is restricted to the new schema; it cannot see the archived application database.

Existing models, views, templates, feature URLs, migration files, tests, and feature modules were preserved. The four existing files changed for the connection/startup switch are `manage.py`, `config/current_development_settings.py`, `scripts/current_development.py`, and the comment in `scripts/run-current-development.ps1`. Fresh settings, identity guards, launcher, local health route, and an administrator setup shortcut were added. All 137 archived media files retain their original size and modification time.

## Create the real administrator

Double-click **`Create Administrator.cmd`**, or run this from the project directory:

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
```

Django asks for the username, email, and a hidden password using its normal validation. No username/password is hardcoded, and no demo user or public member account was created. After creating the account, sign in at `/accounts/login/`. The authentication route and standard command are available; no account was created merely to verify them.

## Enter the first real records

1. **Member:** Sign in and open [onsite Association registration](http://127.0.0.1:8013/membership/registrations/new/onsite/). Enter the person's actual information, review the required documents and onsite findings, and complete the existing verification/approval workflow. Approval creates the member record. The public online registration form also remains available at `/membership/registration/apply/` for manually exercising the online process.
2. **Program:** Open [Create program](http://127.0.0.1:8013/programs/manage/new/). Enter its real title, assistance type, registration dates, required beneficiary slots and eligible disability types, then its actual requirements. Save/review and publish through the existing controls. All programs use EWAF. Enter and authorize actual EWAF configuration when required for calculations/selection; no fictional matrices, policies, applicants, scores, or decisions were carried forward.

No operational records were created by these instructions. Changes you make during manual use will naturally create records and their required audits/emails.

## Local registration configuration

The owner's existing public/staff/onsite/correction/handoff capabilities remain enabled. Their existing privacy notice and owner-confirmed office verification flow are retained. Fictional local procedure-reference text was replaced with references to this explicitly authorized local setup. The onsite method is in-person interview and review of original documents. This configures manual development operation; it does not claim that an outside institution approved a fabricated policy or that any person's evidence was verified. Staff must enter actual verification findings through the existing workflow.

The handoff fingerprint now matches the fresh legitimate document definitions. The old synthetic income/evidence document labels were not copied. The migration-created optional capture slots remain inactive; the Association form and physical checklist remain distinct. PRPWD remains the existing external-link/manual-verification workflow, without an API or invented registry verification.

## Backup and archive

The old database **`santolan_ewaf_twelve_demo`** remains intact and disconnected from the active application. No production, remote, staging, shared, or unrelated local database was modified.

Backups are outside Git under:

`C:\Users\rovic\Documents\Santolan Development Backups\before-fresh-20261110-135526\`

- Initial pre-confirmation backup: `santolan_ewaf_twelve_demo.sql`, 139 tables, 3,915 rows, 14,377,823 bytes; SHA-256 `a53ca54894ff1416ba6a221a4ec3096f3691e28a47dd5d7ab4ccb279e5ce36cc`.
- Final archived snapshot after the old web server stopped: `archive-at-switch\santolan_ewaf_twelve_demo.sql`, 139 tables, 3,916 rows, 14,378,009 bytes; SHA-256 `f28d0876dab1e1fa27d4fbbab971b703f8d91fa97aca291ff495451bc079b3bb`.

One Admin log row appeared between the initial backup and shutdown, so the additional backup preserves that final state too. Both native single-transaction dumps completed successfully; all tables and INSERT-row counts matched the source, and SHA-256 checksums were recorded. No restore rehearsal was run. The old database's final counts match the archived snapshot.

Private backup files also contain recovery configuration and should stay private. The detailed migration log, schema/count verification, source fingerprints, and media inventory are in that secured backup directory. No database password, Django secret, mail credential, or private record is included in this documentation.

## Read-only verification performed

```powershell
.venv\Scripts\python.exe manage.py check --database default
.venv\Scripts\python.exe manage.py migrate --check
.venv\Scripts\python.exe scripts/current_development.py status
git -c core.safecrlf=false diff --check
```

Additional verification used read-only SQL, migration-state inspection, URL resolution, filesystem fingerprints, and the local identity health endpoint. Full workflow testing is left for the owner's manual entries; no automated test suite was executed.
