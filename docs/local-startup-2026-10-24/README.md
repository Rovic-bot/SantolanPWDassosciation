# Authorized local database upgrade and startup

2026-10-24. **Completed for the separately authorized local migration/startup scope.** This does not complete institutional Phase 2B–5 acceptance or change the accepted 70% milestone.

The owner explicitly authorized backing up local `santolan_pwd` on `127.0.0.1:3307`, applying only the three reviewed non-EWAF migrations and starting the current website. Identity/datadir, unchanged migration fingerprints, dependency history, exact single-target plans and protected code/configuration were verified before writes.

## Backup and rehearsal

Private backup: `.local/backups/approved-startup-20261024-011118/`, including `santolan_pwd.sql`, schema-only SQL and the private-media copy. Native dump completed successfully; checksums and unchanged source-row fingerprints were verified. Copied private-file bytes match the originals. Backups/fingerprints/native logs remain ignored/private; no applicant records or credentials are included in this report.

The actual pre-upgrade schema-only dump and migration-history metadata were restored to a fresh G12 disposable MySQL instance. Only fictional content was inserted. The exact three migrations passed forward/reverse/forward, preserving the old synthetic content and existing schema data. The real unchanged startup guard accepted the remaining reviewed deferrals. Historical migration files were not applied; deferred schemas were not enabled. This closes the earlier schema-shape rehearsal gap for this identified local target. The full real-data backup was not restored into a testing database; no real-member-data test or production recovery claim is made.

## Applied changes

Applied individually, with each plan rechecked immediately beforehand:

1. `membership.0006_association_pending_intake`
2. `members.0006_private_information_review`
3. `core.0002_resource_publication_metadata`

No blanket migration, fake migration history, historical migration edit, startup bypass or EWAF migration was used. Existing table rows were compared using their original columns before/after. Old rows remain intact; migration/content-type/permission metadata may gain expected records, but old metadata and user/group permission assignments remain unchanged. Existing private-media bytes, `.env`, ordinary settings, startup guard and all 267 protected files match their pre-operation values. No database rollback was performed on the working database.

The one-time guarded operation script and private logs are under `.local/startup-approved-20261024/`. It refuses changed targets, hashes, dependency plans, configuration or data since backup; it is not a general migration utility. Do not rerun it as a routine launcher.

## Running website and checks

The previous port-8000 process served the older frozen fictional main-testing workspace. Only that web process was stopped; its database was not changed. The current checkout now runs with:

```powershell
.\.venv\Scripts\python.exe -B manage.py runlocal 127.0.0.1:8000 --noreload
```

It is a hidden background development server using the unchanged startup guard. `manage.py check` reported no issues. HTTP checks:

| Route | Result |
| --- | --- |
| `/` | 200 |
| `/membership/register/` | 200; latest Online membership registration section and unavailable status present |
| `/accounts/login/` | 200 |
| `/resources/` | 200 |
| `/membership/registration/apply/` | 503, correctly unavailable without an approved registration policy |

An initial smoke request guessed `/membership/` and received 404; the subsequent checks use Django's actual named route, `/membership/register/`. No route was changed to conceal that mistaken probe. No login attempt, member-data submission or live calculation was used for verification. Earlier automated regression counts remain historical; no new full suite is claimed here.

For a future normal restart, use `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1`. The existing `Start System.cmd` targets the older main-testing workspace; it was not rewritten under this narrow authorization. Do not launch both on port 8000. Current process details and stdout/stderr logs are in the ignored operation directory.

## Remaining boundaries

Association registration, private review operation, membership handoff, public tracking/recovery and PDAO remain disabled/unavailable as previously recorded. Working schema application does not supply institutional authority, privacy/retention procedures, staff assignments or approved security parameters. No new account, permission assignment, credential, content publication, production deployment, commit, push or merge occurred. The local site is running; real online intake is not activated.
