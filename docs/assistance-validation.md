# Eligibility and assistance milestone validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


## Original Milestone Evidence

Date: September 28, 2026 (Asia/Manila). Milestone 60% to 70% is complete and locally validated. Existing source work remains uncommitted on `feature/events`; no publication or deployment.

## Delivered behavior

A private, searchable/paginated assistance queue links from the dashboard and program applications. Administrators assess original submitted documents, answers, acknowledgements, active membership and other program requirements. Required checklist items must pass before Eligible. The user-approved Pending, Eligible, Review Needed and Not Eligible labels and availability are configurable; previous assessments retain their original labels and checklists.

Separate permissions protect eligibility assessment, basic human approval/rejection/return, release recording, voiding, release viewing, configuration and detailed history. The user explicitly authorized basic approval now to satisfy approval-before-release while the fuller human-validation workspace remains at 90%. Approval requires a current Eligible assessment, active membership, a published program and an available beneficiary slot. Applications remain uncapped. No automated ranking, selection or EWAF computation is introduced.

Release records preserve delivered assistance type/benefit, nullable cash amount and estimated non-cash value, actual date, optional receipt reference, remarks, actor and approval snapshot. Confirmation is explicit. Release dates cannot be future or precede approval. Only successful, non-voided releases count as Previous Assistance. Events, pending/rejected/cancelled applications and unreleased approvals never count.

Incorrect records can be voided with required reasons, retaining original details and history. A replacement needs renewed assessment/approval. Member profiles show release history and successful counts under explicit permissions. Release/void notes are hidden from reviewers who have history permission but lack release viewing. There is no public assistance lookup, member account, new PRPWD check or unrestricted file endpoint.

Services serialize operations with program/application/member locks, check versions and save audit events atomically. Open review forms also check member/program versions. Later member/program edits invalidate approval/release readiness. Reassessment and return clear approval; application cancellation requires approval withdrawal and resets assessment on restoration. Released records prevent cancellation or reassessment until an incorrect release is voided. Slots cannot be reduced below existing approvals. Budget remains internal planning information rather than an invented automatic eligibility rule.

## Database and preservation

Applied `assistance.0001_initial` and `assistance.0002_default_eligibility_labels` after a verified private native-MySQL backup. Four new tables; existing table schemas were unchanged:

- `EligibilityStatus`: stable code, editable unique label, active flag and version. Only the four user-approved defaults were installed.
- `AssistanceCase`: protected one-to-one application, eligibility/label snapshot, checklist/review notes, reviewer/time, member/program versions and current administrative decision/actor/time/remarks.
- `AssistanceRelease`: UUID, protected application, nullable unique active-application link, type/benefit, optional monetary values/reference, actual date, remarks/approval snapshot, recorder/time and retained void actor/time/reason. Constraints enforce nonnegative values and a valid active-or-void state.
- `AssistanceLog`: protected optional application, actor and retained actor label, action, reason, before/after snapshots, timestamp and network address. Configuration events use a null application.

Before/after fingerprints matched all existing data across **27 tables**, including users, assignments, memberships, member records, documents, announcements, events, programs and histories. A final preservation check matched again. No synthetic assistance cases, releases or logs exist in the normal database. Private backup and preservation evidence: `.local/milestone70/`. Browser fixtures use disposable test MySQL and temporary media.

## Validation evidence

- Full automated suite: **199 tests passed** (168 prior-module tests and the initial 31 assistance tests).
- Final focused run: **69 tests passed together** — all 36 assistance tests, all 32 Programs tests and the assistance Chrome integration test. Added coverage includes stale-open-form, restoration, release-note privacy, void confirmation and configuration rollback. This is **204 distinct automated tests plus six Chrome workflows** across the full and focused runs.
- Three assistance concurrency tests passed: two approvals competing for the final slot; simultaneous release attempts producing one record/event; and member deactivation racing release.
- All five previous Chrome workflows passed again: Programs, Events, Members/Announcements, Membership and Authentication/Public Portal.
- New assistance Chrome workflow: **passed 45 responsive checks and eight enlarged-text checks** at 320/390/768/1024/1440 pixels, with no page/resource errors, duplicate IDs or unlabeled form controls. It exercised private document access, failed/valid eligibility, human approval, editable labels with retained snapshots, release, void/reassessment/reapproval/replacement and successful-only member history. Real Tab focus and reduced-motion checks passed.
- Resolved the initial 320-pixel overflow by using the existing positioned workspace table component. Corrected the test harness to use keyboard Tab for focus-visible rather than programmatic focus after pointer input. Screenshot review caught and corrected an ambiguous required-submission/optional-assessment label. Inspected desktop review/release and mobile checklist/release/member-history screenshots. Final focused rerun passed; no unresolved test failure.
- System/database checks, model/migration consistency, applied migration check, dependency check, JavaScript syntax, static collection and **65-template compilation** passed. Whitespace checks passed.

Automated cases cover required and optional original requirements, missing uploads/answers/acknowledgements, inactive membership, ineligible outcomes, missing approvals, changed-member/program checks, capacity, cancellation/restoration, immutable successful releases, date/amount/confirmation validation, duplicate/void/replacement behavior, database uniqueness/check constraints, protected history, atomic audit rollback, configuration changes and snapshots, direct-service/route permissions, CSRF/GET safety, no generic admin mutation, XSS escaping, scoped void URLs, search/filter/pagination, member history and public privacy.

## Files and use

New `assistance/` models/forms/services/views/URLs/migrations/tests; five assistance templates; `scripts/milestone70_browser_qa.py` and `.cjs`; plan/validation notes. Integrations: root URLs, program application link and service guards, member view/history, workspace navigation/dashboard, README and vault decision/schema/progress notes. No new package, database provider, credential or role-assignment change.

Open **Dashboard → Review eligibility and assistance** (`/assistance/`). Configure labels from the queue or dashboard. Superusers already have access; ordinary staff need the capabilities in [README](../README.md#assess-eligibility-and-record-assistance).

## Boundaries

EWAF is next at 80%; its encodings, normalization bounds, AHP failure/activation policy and thresholds remain open configuration decisions. Analytics/reports, fuller human validation and production readiness are later milestones. The current release workflow supports one successful release per application with retained correction records; a future multi-installment policy needs separate design.

Local validation does not establish production readiness or association UAT. Production storage, backup restoration/retention, deployment, real-device assistive technology and Firefox/Safari remain future validation. Audit protection is at application level, not immunity from a database administrator. Obsidian rendering was not inspected.

## Reproduce

```powershell
.venv\Scripts\python.exe manage.py test accounts core membership members announcements events programs assistance --noinput
.venv\Scripts\python.exe manage.py test scripts.milestone70_browser_qa scripts.milestone60_browser_qa scripts.milestone50_browser_qa scripts.milestone40_browser_qa scripts.membership_browser_qa scripts.browser_qa --noinput
.venv\Scripts\python.exe manage.py check --database default
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py migrate --check
```

Browser tests use `PLAYWRIGHT_MODULE` and `CHROME_EXECUTABLE` as described in [authentication validation](authentication-validation.md), with the required Windows browser/temporary-file access.
