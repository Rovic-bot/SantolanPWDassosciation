# Membership registration validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


## Original Milestone Evidence

Date: 2026-09-20 (Asia/Manila). Milestone: 20% → 30%. Branch: `feature/membership-registration`.

## Outcome

Implemented the guide's membership acceptance criteria: a public application creates Pending only; authorized administrators review profile/documents, open a configured PRPWD hyperlink, manually save verification, and approve/reject. Only verified approval creates the official Member. Important actions produce application audit events. No member account, registry API, automatic approval, or EWAF scoring is introduced.

The user's explicit request to proceed with 20% → 30% establishes membership before announcement publishing. Planning and acceptance criteria are in [membership-plan.md](membership-plan.md). Setup and reviewer permissions are in [README](../README.md#open-and-use-membership-registration).

## Database and files

Five migrations applied successfully to native MySQL 8.4.11 on port 3307: `membership.0001_initial`, `membership.0002_registration_settings`, `membership.0003_submissionwindow`, `documents.0001_initial`, `members.0001_initial`. Both existing administrator/user records were preserved. The application database contains zero applications and zero members after verification; synthetic records were confined to the disposable test database. Registration is closed, the PRPWD link is blank, and document requirements are unseeded, awaiting association configuration.

Eight new tables:

- `membership_membershipapplication`: name, birthdate, address, contact, optional email, control number, disability/employment text, monthly income, dependents; unique UUID reference/retry key; status/submission time; original requirement JSON snapshot; PRPWD result/actor/time/notes/URL; decision actor/time/notes; optimistic version counter.
- `membership_membershipsettings`: singleton key, registration-open flag, HTTPS registry URL. Seeded closed only.
- `membership_membershipevent`: protected application FK, nullable actor FK, preserved actor label, action, description, timestamp, optional administrator IP.
- `membership_submissionwindow`: HMAC address key, timestamp, attempt count; separate from login counters and their cleanup.
- `documents_documenttype`: unique name and description.
- `documents_membershipdocumentrequirement`: protected unique document-type relationship, active/required flags, instructions.
- `documents_membershipapplicationdocument`: UUID, protected application/requirement FKs, preserved document label, randomized private file path, MIME, size, upload time, unique application/requirement pair.
- `members_member`: copied approved profile, unique control number, protected one-to-one source application, join time, active flag. Full member management remains milestone 40%.

Changes are contained in `membership/`, `documents/`, `members/`, membership templates and browser tests, plus settings/routes/dashboard/home links/CSS and a reusable counter helper. Existing public-route tests now cover the configurable membership page. No dependencies were added.

## Verification — passed

- **72 automated tests**, including all foundation/authentication regressions and 30 membership cases. The final command `manage.py test accounts core membership scripts.membership_browser_qa --verbosity 1 --noinput` passed **73 tests**: the 72 ordinary tests plus one Chrome integration case.
- Membership cases cover closed/open registration, required/optional/inactive requirements, snapshots and changed-form detection, forged/expired retry tokens, repeated submission, validation, file extension/MIME/signature/size, aggregate streaming limits, extra/multiple files, CSRF, private access and headers, permission separation, XSS escaping, missing files, approval verification gate, rejection, duplicate members, stale reviews, simultaneous approvals, rollback including saved-file cleanup, configuration validation, and bypass prevention. Submission expiry and cleanup remain independent of login counters.
- **Membership Chrome workflow passed** at 320/390/768/1024/1440 pixels for form/review overflow checks. Exercised opening registration through admin settings, two public uploads, generic receipts, private download, blocked approval before verification, manual verification, approval, rejection, logout protection, and no failed resources/page errors. Database assertions confirm exactly one approved member and one rejected application.
- **Existing portal Chrome workflow passed separately**: eight public/login routes at five widths, active links, keyboard skip navigation, mobile menu, login, role configuration, audit, password change, logout, and no errors.
- Visually inspected registration mobile, application review desktop, and approved application mobile screenshots. Local screenshots live under ignored `.local/qa-milestone30/`.
- MySQL/system checks, all five migrations, pending-migration check, model/migration consistency, static collection, dependency consistency, and whitespace diff checks passed.

Optional browser commands require the same Playwright/Chrome setup described in [authentication validation](authentication-validation.md#running-the-optional-browser-check). Use `manage.py test scripts.membership_browser_qa --noinput` for membership, and `scripts.browser_qa` for the original portal check. Browser actors, credentials, registry URL, and documents are synthetic and temporary; no actual external PRPWD lookup was made.

## Issues resolved

- Windows sandbox denied access to temporary upload directories. Successful file/browser checks ran with approved execution outside the sandbox.
- The download test closed an already-closed streaming response twice, triggering connection cleanup inside the test transaction. It now relies on Django's test streaming iterator and asserts closure; application behavior was unaffected.
- Verification and decision forms initially reused field IDs. They now have distinct IDs, with regression assertions and a completed browser workflow. The browser selector also accounts for required-field labels.
- Submission limits have their own counter table and expiry command so login cleanup cannot prematurely reset them.

## Boundaries and remaining configuration

Configure the association's document list, official PRPWD link, and reviewer role assignments before opening registration. Core pending/approved/rejected semantics implement the guide; additional statuses, resubmission/correction/reopening policy, final employment categories, and future matching rules remain open. Requirements/history are retained; generic application/member edit/delete routes are not exposed.

File validation checks signatures, not complete document parsing or malware safety. Files are served only as private attachments; public deployment still needs web-server request limits, malware/quarantine policy, HTTPS, proxy/network-rate tuning, storage/backup/retention decisions, and UAT. Django describes these limits in its [uploaded-content security guidance](https://docs.djangoproject.com/en/5.2/topics/security/#user-uploaded-content). A process crash between a file write and transaction completion may leave an orphan file; production storage reconciliation remains future work. Normal exception paths clean up uncommitted files and are tested.

This is a locally validated milestone, not a production deployment or completed user acceptance evaluation.
