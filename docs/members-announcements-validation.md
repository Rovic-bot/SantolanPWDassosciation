# Member management and announcement publishing validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


## Original Milestone Evidence

Date: September 27, 2026 (Asia/Manila). Branch: `feature/members-announcements`.

## Delivered behavior

Member directory at `/members/`: private name/control-number search, status filters, pagination, profile corrections with reasons, archive/inactive/active transitions and restoration, retained before/after history, and permission-controlled original documents. The application review links to the official member; changes never rewrite the original application. There is no member account or public member lookup.

Announcement workspace at `/announcements/manage/`: drafts, editing, preview, explicit publish/withdraw/archive/delete, filters, pagination, optional PNG/JPEG images, image descriptions, and publication history. Public `/announcements/` and individual details show only currently published records; the homepage uses the three most recently published announcements. No announcement was created in the normal application database during validation.

Separate permissions protect member editing/status/history/documents and announcement creation/editing/publication/deletion/history. Services repeat authorization checks. Active staff and dashboard access remain required. Published-content edits also require publication permission. Mutations use POST/CSRF, database transactions, row locks, and version checks; failures to write audit events roll back the associated change.

Member records are archived, never deleted through the workspace. Announcement Delete is a terminal internal tombstone: removed from public access and the default management list, retained under the Deleted filter with its audit history. Republish is available for drafts/archives, not deleted records. Public responses and private views use no-store headers for successful responses.

## Database and dependency changes

Applied `announcements.0001_initial` and `members.0002_memberevent_alter_member_options_member_archived_at_and_more` on native MySQL after a verified, private `mysqldump` backup.

- Member additions: `archived_at`, `updated_at`, optimistic `version`, change/status permissions, ordering, and an archived-implies-inactive constraint. Existing `is_active`, profile fields, and protected source application remain.
- New MemberEvent table: protected member, nullable actor and preserved actor label, action, reason, before/after JSON, timestamp and address.
- New Announcement table: UUID, title, plain-text content, optional image path/description, draft/published/archived/deleted status, publication/create/update timestamps, creators/updaters, and version. Database constraints validate status and require a publication timestamp for published records.
- New AnnouncementEvent table: protected announcement, actor/label, action/description, timestamp and address.
- Added `Pillow==12.3.0` for actual image decoding and re-encoding. No other dependency, credential, database-provider, or authentication changes.

Before/after fingerprints matched all original columns and rows in 12 existing tables, including both user accounts, the existing member, two membership applications, roles/permission assignments, configuration, and membership history. The new permissions are added through Django migrations; existing assignments are unchanged. Private evidence and the database/source backups are in ignored `.local/milestone40/`; do not publish that directory.

## Verification

Initial automated run: all 100 existing/new tests passed. Initial Chrome workflow: 50 responsive checks across 320/390/768/1024/1440 pixels and 10 Largest-text checks passed, with no page errors or failed resources. Member edit/archive/restore and announcement create/image/publish/edit/archive/republish/delete completed against a disposable MySQL test database. Screenshots of desktop member records, mobile publication controls, and public announcement detail were inspected.

Final result: **102 automated tests and all 3 optional Chrome workflow tests passed**. The combined 105-test run passed the 102 automated cases and milestone-40 browser workflow; two old browser scripts stopped at selectors made obsolete by the earlier frontend redesign. Scoping the registration-settings link to navigation and opening the mobile workspace menu before logout corrected those harnesses. Both were rerun successfully. There are no unresolved test failures.

The existing portal workflow also passed all eight public/login routes at five widths, keyboard/mobile navigation, role creation, sign-in audit, password change, and logout. The membership workflow passed configuration, private uploads/downloads, blocked premature approval, manual verification, approval, rejection, and logout protection. The final milestone-40 workflow again passed 50 responsive and 10 enlarged-text checks, labels/duplicate-ID checks, keyboard focus and reduced motion, with zero resource/page errors.

System/database checks, pending-migration checks, model/migration consistency, dependency consistency, static collection, and whitespace validation passed. No real application submissions, member edits, announcements, user accounts, or document uploads were created by testing. Browser actors and files were synthetic and temporary.

## Test coverage and resolved issues

New cases cover access control, separate capabilities, history visibility, CSRF, escaped HTML, search/filter/pagination, source-application preservation, archived records, stale updates, duplicate controls, future birthdates, negative values, transactional audit rollback, document ownership/access/headers/missing files, publication visibility, future timestamps, image validation/limits/descriptions/re-encoding, file replacement/removal cleanup, and missing-image publication blocking.

Windows sandbox restrictions initially prevented temporary upload access; successful tests ran with approved execution outside the sandbox. An initial test incorrectly expected no-store on Django's exception-generated 404 responses; the assertion now checks successful content/image responses while still requiring 404 for unpublished records. Older foundation homepage tests expected pre-redesign text and no database reads; they now validate the preserved redesign and database-backed announcement list. No product behavior was changed to satisfy obsolete assertions.

## Remaining boundaries

Event/program/assistance histories depend on their future modules and remain explicitly unavailable. Association roles, official contact details, PRPWD URL/document requirements, and future business configurations remain administrator/client decisions. Existing registration configuration was preserved.

This is local milestone validation, not production deployment or completed association UAT. Firefox/Safari, real-device screen readers, backup restoration drills, production storage/retention policies, malware scanning, and production performance remain future validation. Image re-encoding strips source metadata/appended bytes and rejects invalid/oversized/animated input; it is not a claim of complete upload safety. See [Pillow image-security guidance](https://pillow.readthedocs.io/en/stable/handbook/security.html).

Important actions/history are application-protected; this does not claim database-administrator-proof immutable logging. As with the existing upload workflow, a process crash during a file/database boundary can leave an orphan image for later storage reconciliation.

## Running the checks

```powershell
.venv\Scripts\python.exe manage.py test accounts core membership members announcements --noinput
.venv\Scripts\python.exe manage.py test scripts.milestone40_browser_qa scripts.membership_browser_qa scripts.browser_qa --noinput
```

Browser checks use `PLAYWRIGHT_MODULE` and `CHROME_EXECUTABLE` as described in [authentication validation](authentication-validation.md). Local browser evidence is `.local/qa-milestone40/results.json` and its screenshots. Configuration and day-to-day instructions are in [README](../README.md).
