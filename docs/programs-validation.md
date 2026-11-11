# Programs milestone validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


## Original Milestone Evidence

Date: September 28, 2026 (Asia/Manila). Milestone 50% to 60% is complete and locally validated. Existing work remains uncommitted on `feature/events`; no remote publication or deployment was performed.

## Delivered behavior

Administrators create program drafts with an association-defined assistance type, application window, instructions and optional program dates, beneficiary slots, internal budget, amount and benefit. Explicit publishing, withdrawal, cancellation with a public notice, and archive retain applications and history. Public pages include current/past application periods, details and requirements. The homepage program link reflects current records. Budget is private.

Each program configures its own document uploads, written questions and acknowledgement checkboxes, with labels, instructions, active/required flags and ordering. Deactivation replaces physical deletion. Existing applications preserve program details, original requirements, answers and uploaded document labels; later configuration edits affect future submissions only.

The user confirmed that **beneficiary slots do not cap applications**, that program verification reuses event matching, and that the initial application states are **Submitted, Under Review and Cancelled** with reasoned administrator changes. Eligibility, approval, assistance release and EWAF are not implemented at this milestone.

Members first verify control number, full name, birthdate and contact number against an active official membership, then complete requirements. Matching uses the existing conservative event normalization, explicit Python comparisons against MySQL collation behavior, generic failures and HMAC rate counters. No member account or PRPWD re-check is introduced. A session-scoped 15-minute grant expires on time or when program/member versions change; submission rechecks under database locks. Duplicate valid applications return the existing record; cancelled records need administrator restoration.

Private rosters support search, filters and pagination. Separate permissions protect application viewing/status changes, document attachments, requirement configuration, publication and detailed history. Member records include program applications with both program/application viewing permissions. Session receipts expose only random references and statuses; there is no public profile, roster or reference lookup. No generic Django admin mutation bypass, physical delete action or automated notification service is added.

## Database and preservation

Applied one additive migration, `programs.0001_initial`, after a verified native-MySQL backup. Six new tables:

- **Program:** UUID, name/description/assistance type, registration dates, nullable program dates/slots/budget/amount, benefit/instructions, status/publication timestamp, actors/timestamps/version.
- **ProgramRequirement:** protected program relation, label, kind, instructions, required/active flags and position.
- **ProgramApplication:** UUID reference, protected program/member relations, status, program/requirements snapshots, answers, timestamps/version; unique program/member pair.
- **ProgramDocument:** UUID, protected application/requirement relations, original label, randomized private file path, MIME/size/upload timestamp; unique application/requirement pair.
- **ProgramLog:** protected program/optional application, nullable actor plus retained label, action/reason, before/after JSON, timestamp and optional administrator network address.
- **VerificationWindow:** HMAC key, start time and attempts, with an explicit expired-counter cleanup command.

Database constraints enforce valid states, publication timestamps, application-period ordering, program-period ordering, registration before a supplied program end, positive optional slots, nonnegative optional monetary fields, and uniqueness. Program locks serialize configuration changes, submissions and review; member locks recheck active status. Application/document/audit writes commit together; failed writes clean up saved files. Nullable actor fields permit continued operation after an administrator is removed.

No existing table schema changed. Original rows and columns matched across **21 existing tables** before/after migration and again during final validation, covering accounts, role assignments, membership, member records/history, documents/configuration, announcements, events and audit data. Existing permissions were not reassigned. No synthetic programs or applications were inserted into the normal database. Private backups/fingerprints are in ignored `.local/milestone60/`; browser evidence is in `.local/qa-milestone60/`.

## Validation evidence

**168 automated tests and all five Chrome workflow tests passed across the full run and focused rerun.** The 173-test full run passed 172 tests; the new program browser harness initially used an exact document label that omitted the accessible “required” suffix. The selector was corrected. All 32 Programs automated tests plus the corrected browser workflow then passed together (33 tests). Earlier sandbox-only failures were caused by Windows temporary-file permissions and Chrome launch restrictions; the complete suite was rerun with the required access. No unresolved test failure remains.

New automated coverage includes publication/withdrawal/cancellation/archive; nullable fields and numeric/date constraints; incorrect verification fields, inactive/archived members and conservative matching; time boundaries; grant expiry/scope and program/member changes; duplicate prevention without slot capping; required/optional/inactive uploads/questions/acknowledgements; immutable submission snapshots; MIME/signature/size/aggregate/extra/duplicate upload rejection; audit rollback/file cleanup; configuration limits/stale edits; reasoned status changes/cancellation/restoration; direct service permissions, public-edit publishing permission, private roster/history/document separation; scoped/missing-file downloads, protected records; session privacy/retry/failure handling; XSS, budget privacy, CSRF, method safety and no public media/admin bypass; rate limits/expiry/cleanup; search/filter/pagination and member history.

Two native-MySQL concurrency tests passed: simultaneous duplicate submissions create one application/audit, and requirement changes racing with submission cannot produce a mixed or stale configuration snapshot.

The new Chrome workflow passed **80 responsive checks** at 320/390/768/1024/1440 pixels and **16 enlarged-text checks**. It exercised draft creation, all three requirement types, publication, failed and normalized successful verification, private upload/submission/receipt, review/cancel/restore, audited attachment download, later requirement edits retaining the submitted snapshot, member history, public cancellation and archive. Label/duplicate-ID, focus and reduced-motion checks passed, with no page/resource errors. Desktop public details, desktop application, mobile enlarged-text application and mobile review screenshots were inspected.

Existing Events (60 responsive/12 enlarged-text checks), Members/Announcements (50/10), Membership application/manual verification/approval/rejection/document, and Authentication/RBAC/Public Portal browser workflows passed again.

System/database checks, model/migration consistency, pending migrations, dependency consistency, JavaScript syntax, static collection, 60-template compilation, and whitespace checks passed. Normal-database smoke checks passed for public home/program/current/past/event/announcement pages and protected program-management redirects.

## Files and use

New: `programs/` models/forms/services/views/URLs/migration/tests/counter cleanup; `templates/programs/`; `scripts/milestone60_browser_qa.py` and `.cjs`; plan and validation notes. Integrated settings/routes, public program navigation/homepage, administrator navigation/dashboard, member program history, and README. No dependency, credential, database-provider or authentication change. Existing unrelated source was preserved.

Open **Dashboard → Manage programs → Create program**, add requirements, then publish. Public applications start only when a published program's configured window opens. Superusers have access; ordinary staff need the explicit capabilities documented in [README](../README.md#publish-assistance-programs-and-review-applications). Official program content, document requirements and role assignments remain association choices.

## Remaining boundaries

Next: 70% Eligibility and Assistance Records. Program submission/review is not eligibility, approval, beneficiary selection or successful release and never contributes to previous-assistance counts. EWAF, analytics/reports, deployment and association UAT remain later milestones.

Upload validation checks extension, MIME, signature and sizes; it is not malware scanning. Production still needs private persistent storage, retention/backup policy, proxy/network tuning and request-size enforcement. Application-level audit protection is not database-administrator-proof immutability. Process crashes at file/database boundaries may leave orphan files for storage reconciliation. Firefox/Safari and real-device assistive-technology validation remain future work.

## Reproduce

```powershell
.venv\Scripts\python.exe manage.py test accounts core membership members announcements events programs --noinput
.venv\Scripts\python.exe manage.py test scripts.milestone60_browser_qa scripts.milestone50_browser_qa scripts.milestone40_browser_qa scripts.membership_browser_qa scripts.browser_qa --noinput
.venv\Scripts\python.exe manage.py check --database default
.venv\Scripts\python.exe manage.py migrate --check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Provide Playwright through `PLAYWRIGHT_MODULE` and Chrome through `CHROME_EXECUTABLE` as described in [authentication validation](authentication-validation.md). Browser tests need temporary-file/browser access and use only synthetic records in the separate disposable native-MySQL test database.
