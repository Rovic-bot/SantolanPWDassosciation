# Short application references — October 26, 2026

The owner requested easy-to-type, unique references for filtering, explicitly selected **existing and new applications**, and extended the request to program applications and all application services. This authorizes additive aliases. Original issued references, URLs, publication history, member numbers and external release references remain intact.

The parent specification, development guide, Open Decisions and implementation impact files required by AGENTS.md were checked again and are absent at the supplied paths. This work implements the owner's specific request and makes no claim that the other TARGET workflows are available.

## Behavior

| Record | Short reference example |
| --- | --- |
| Association registration | `AMR-000123` |
| Onsite membership application | `MEM-000124` |
| PDAO registration | `PDAO-000125` |
| Program application | `PRG-000126` |
| Event registration | `EVT-000127` |
| Attendance record | `ATT-000128` |
| Assistance/referral request | `REF-000129` |

One MySQL BigAutoField sequence supplies all seven types. Values have a minimum of six digits, expand beyond six digits and do not reset annually. Database uniqueness prevents concurrent duplicate allocation; a unique type/object constraint makes retries idempotent. Issued mappings cannot be edited or deleted through the application. New records and their aliases commit or roll back together. Existing production writers use ordinary model saves; the alias service is not a general bulk-import API.

Receipts, relevant Admin application lists/details and print views show short references. Event and attendance lists now include reference columns. Matching Admin searches accept the full code, case-insensitive prefix, or just its numeric part, including without leading zeros. Original references continue to work. Program Photo Verification also accepts the same aliases. Existing query scope, permissions, processing filters and Association exact-reference search behavior are retained.

Aliases are search keys, not credentials. Private receipt sessions, expiry, CSRF, staff permissions and program identity verification remain required. Program short and original references share the same verification rate-limit key. No public tracker or QR feature was enabled. New referral email content uses the short code; stored email history was not rewritten and no real emails were sent during validation.

Historical EWAF/publication references and manually entered disbursement references are retained. No eligibility, ranking, approval, PRPWD, release or source-history rule changed. PDAO registrations still create no Member records.

## Validation

146 backend tests passed in disposable native MySQL, including nine new alias tests, Association decisions/inbox, PDAO workflow, private membership printing, program verification, events and referrals. Artifacts: `santolan-g12-tests-knonp0l6`.

New coverage includes all seven allocation paths and original-reference compatibility; all seven Admin filters and permission denial; program scope and service boundaries; immutable mappings; rollback on allocation/audit failure; concurrent submissions and duplicate allocation; private receipts; generated email references; shared verification rate limits; and an explicit rehearsal of only the new migration. The rehearsal populated all seven historical record types, verified their complete rows were unchanged and verified backfill idempotence. It did not run or reverse historical migrations. A follow-up focused test covers short, numeric and original program references in Photo Verification.

Chrome passed on a separate disposable MySQL instance, checking short, numeric and original searches for Association, PDAO and programs, applicant submission, Association approval, PDAO review/print/forwarding and desktop/mobile overflow. Artifacts: `santolan-g12-tests-lukook2g`; copied screenshots and PDF are in `.local/short-references-20261026/browser/`. Program and PDAO inbox screenshots were visually inspected. The first browser run exposed a harness wait that compared a query string against pathname alone; the harness was fixed and the full workflow passed.

Django configuration/database checks, migration drift and whitespace checks passed. Browser harness JavaScript syntax passed.

## Local database update and availability

Only `core.0003_short_application_references` was applied. It creates the alias table and populates aliases without altering source records. Its data operation is deliberately irreversible to avoid invalidating issued codes. Normalized migration SHA-256: `a5b89f48621096db6fbeade94120a42cb19f03762770191f7d7498732a70ccd0`.

Before application, the helper verified the exact database name, port, MySQL data directory, pending migration plan and migration checksum; stopped-site state; a complete SQL dump; environment backup; and private-upload backup. Backup: `.local/backups/short-references-20261026-20261026-152902/`. SQL SHA-256: `3827623a4c5bd2a0a43c19eb35f291f90147f3f28ce82fe49739c025a6c91b54`.

After application, fingerprints verified all 449 pre-existing rows across 118 tables and the private upload unchanged. Only permitted migration metadata and the new alias table were added. All four existing application records received aliases: two Association registrations and two membership applications. The local database had no records in the other five categories; their new-submission behavior was exercised in disposable tests. No migrations remain pending; EWAF policy/scoring flags remain disabled.

`SHORT_REFERENCES_ENABLED=True` was then added to the local `.env`, preserving every other setting. The committed example defaults to false so another deployment must back up, apply the reviewed migration/backfill and enable the setting deliberately. The website was restarted hidden at `http://127.0.0.1:8000/`; HTTP checks passed for the public home and both registration forms, and Admin Membership Reviews redirected unauthenticated access to login. No changes were committed or pushed.
