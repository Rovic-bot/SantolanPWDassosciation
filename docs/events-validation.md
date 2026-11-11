# Events milestone validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


## Original Milestone Evidence

Date: September 27, 2026 (Asia/Manila). Branch: `feature/events`. Milestone 40% to 50% is complete and locally validated; this is not production deployment or association UAT.

## Delivered behavior

Admins create event drafts with schedule, venue, registration window, optional capacity, and validated image/description. Separate publication permission controls publish/withdraw/cancel/archive; live edits also require it. Cancellation retains a public notice, while drafts/archives and their images are private. Registrations and audit history are preserved.

Public upcoming/past event lists, event details, and the homepage use actual published records. Members register without accounts using their control number, name, birthdate and contact number against active membership. User-confirmed normalization preserves name accents/order, ignores case/repeated whitespace, equates formatted Philippine +63/0 numbers, and requires exact birthdate. Mismatches share a generic error; HMAC counters enforce configurable network/control-number limits. No PRPWD API or EWAF is involved.

Event-level row locks serialize public registration, capacity edits and attendance changes. Uniqueness prevents multiple registrations per member/event. Repeated valid submissions return the existing record. Cancelled registrations need admin restoration with active-member/capacity checks. Registration and audit writes commit together; stale forms are rejected. Registration opens inclusively and closes exclusively by the event start; attendance can be recorded after that start.

The private roster supports search, filters and pagination. Authorized admins record Registered, Confirmed, Attended, Absent or Cancelled with a reason and before/after history. Member records now show event participation with separate permissions. Session receipts expose a random reference and current status, not member profile fields; only the most recent receipt is retained in that submitting session. There is no public lookup by reference, member account or notification service.

## Database and preservation

Applied one additive migration, `events.0001_initial`, after a verified native-MySQL dump. Four new tables:

- Event: UUID, title/description/venue, start/end and registration times, optional capacity/image/description, publication state/time, actors, timestamps and version.
- EventRegistration: UUID reference, protected event/member relationships, constrained status, timestamps/version, unique event/member pair.
- EventLog: protected event and optional registration, nullable actor plus retained actor label, action/reason, before/after JSON, timestamp and optional admin network address.
- VerificationWindow: HMAC key, window start and attempt count; no raw verification fields. An explicit cleanup command removes expired counters.

Database constraints validate date ordering, positive-or-unlimited capacity, allowed states, publication timestamps, and registration uniqueness. No existing table schema changed. Permissions were added; existing user/group assignments were preserved. No new dependency, `.env`, database-provider or authentication change.

Original rows/columns matched before and after across **17 existing tables**, covering users, role assignments, members, applications, documents/configuration, member/announcement history and administration/security logs. They matched again after validation. No synthetic events or registrations were added to the normal database. Source, database and vault-note backups plus fingerprint evidence are private in ignored `.local/milestone50/`; never publish that directory.

## Validation evidence

Final outcome: **136 automated tests and all four Chrome workflow tests passed** across the full run and focused rerun. The 140-test run passed 138 cases; the two failures were older portal checks assuming one `aria-current` marker across the entire page. Events has separate main and period navigation. Both checks now scope that assertion to main navigation; the affected four-test portal group and browser workflow passed on rerun. No unresolved test failure remains.

New Events coverage: 34 tests for publication/withdrawal/cancellation/archive, schedule and capacity validation, every incorrect verification field, conservative normalization and MySQL collation behavior, inactive/archived members, date boundaries, duplicates, restoration, attendance timing/corrections, stale forms, permissions, CSRF, XSS/privacy, session receipts, rate limits/expiry/cleanup, search/filter/pagination, image validation/limits/cleanup, missing-file blocking, protected histories and transaction rollback.

Three native-MySQL concurrency tests passed: two different members competing for the last slot, duplicate simultaneous registration by one member, and cancellation restoration competing with a new registration. Only one slot is occupied and duplicate submissions create one registration/audit record.

Events Chrome workflow passed **60 responsive checks** (12 routes at 320/390/768/1024/1440 pixels), **12 enlarged-text checks**, labels/duplicate IDs, focus and reduced motion, with no browser/resource errors. It exercised draft/image/publication, incorrect verification, normalized successful registration, receipt, confirmation/cancellation/restoration, attendance, member history, past events, event cancellation and archive. Desktop public detail and mobile registration/attendance screenshots were inspected. Evidence: `.local/qa-milestone50/results.json` and screenshots.

The existing member/announcement workflow again passed 50 responsive and 10 enlarged-text checks. Existing membership submission/manual verification/approval/rejection/private-document and authentication/role/password/logout browser workflows also passed.

System/database checks, pending-migration/model consistency, dependency consistency, static collection, JavaScript syntax, compilation of all 45 project templates, and whitespace checks passed. Normal-database HTTP smoke checks passed for public home/events/past-events/announcements and protected events/member redirects.

## Source scope and use

New: `events/` models/forms/services/views/URLs, migration, tests and counter cleanup command; `templates/events/`; event browser harness; plan/validation documents. Existing integrations: settings/routes/homepage, member view/history, public/admin navigation and dashboard, small event CSS additions, README, optional image-limit parameters preserving announcement defaults, and the two portal test assertions. The completed design and unrelated modules were preserved; work remains uncommitted and undeployed.

Use **Dashboard → Manage events → Create event**, then review and publish. Superusers have access; ordinary staff need the explicit event permissions listed in [README](../README.md#publish-events-and-record-attendance). Official association content and business roles remain administrator choices. Test actors/content were synthetic and confined to the disposable database and temporary files.

## Remaining boundaries

Programs, eligibility, assistance, EWAF, analytics and exports remain later milestones. Production hosting/storage/retention, proxy/shared-network rate tuning, backup restoration drills, Firefox/Safari, real-device assistive technology and association UAT remain future validation. No automated email/SMS is sent; administrators communicate changes through existing official channels. Application audit protection does not claim database-administrator-proof immutability. A process crash around a file/database boundary can leave an orphan image requiring storage reconciliation.

## Reproduce

```powershell
.venv\Scripts\python.exe manage.py test accounts core membership members announcements events --noinput
.venv\Scripts\python.exe manage.py test scripts.milestone50_browser_qa scripts.milestone40_browser_qa scripts.membership_browser_qa scripts.browser_qa --noinput
.venv\Scripts\python.exe manage.py check --database default
.venv\Scripts\python.exe manage.py migrate --check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Browser tests use `PLAYWRIGHT_MODULE` and `CHROME_EXECUTABLE` as described in [authentication validation](authentication-validation.md). The database must be native MySQL with the separate disposable test database; browser tests require permission to launch Chrome and access temporary uploads.
