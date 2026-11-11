# Online Association and PDAO registration — 2026-10-26

## Authorized behavior

The owner requested working online registration with two destinations under Admin / Membership Reviews: Association Membership and PDAO Membership. The owner explicitly confirmed **applicant confirms details, then Admin decides** for Association membership. Only Admin approval creates a member. PDAO applications are retained for staff review, printing and preparation for forwarding; they never create Association members.

The external October 10 specification, development guide, Open Decisions, membership amendment and implementation impact files named by AGENTS.md are absent at their supplied paths on this machine. This change follows the current owner's explicit instruction and preserves the existing October 25 simplified Association decision and Word-template printing implementations. It does not infer new PRPWD results, scores, eligibility, ranking, release decisions, government approval or institutional retention periods.

## Implementation

- An explicit `ONLINE_MEMBERSHIP_ENABLED` environment opt-in supplies the documented Association collection contract and enables the separate PDAO service. The example environment remains disabled; the owner's local `.env` is enabled after validation and migration. Test fixture policies are not loaded into the application. No external institutional/security certification is asserted.
- Association applicants must confirm accuracy and the privacy notice. The existing versioned pending intake, assigned member number, Admin approve/decline service, protected history and Word-template print views are retained. Approval creates the Member; submission and decline do not. Online attachments are not collected by this configuration; existing physical requirements and protected historical attachments remain available.
- `PDAORegistration` retains the original confirmed form, privacy version, private receipt binding and processing state. It has no Member or Association application relationship. `PDAORegistrationEvent` retains append-only access, print and processing events. Both use guarded service writes. Submitted applicant data is immutable.
- PDAO submission uses CSRF, a signed expiring session-bound nonce, request limits, strict source-field validation and a unique submission key. Exact duplicate submissions return the same record; conflicting retries are rejected. Receipt data is session-bound, expires, and can be revoked using Finish. A reference alone cannot reopen it. Public receipts expose no staff history or processing status.
- Admin has separate PDAO view, print and forwarding permissions, with fresh permission checks, locked/versioned transitions and transactional audits. The states are Received → Ready to forward → Forwarded to PDAO. The final action requires staff confirmation that forwarding actually happened. There is no automatic email, upload or transfer to PDAO.
- Admin can print hard copies or use the browser's Save as PDF. The existing PDAO source fields, consent and requirement printout are reused; the original print-only route remains available. Private pages are not cached. The accessibility skip link is hidden when printing.
- Membership Reviews now opens a permission-aware page with Association Membership and PDAO Membership destinations. Existing onsite applications remain accessible, and the eight Admin navigation groups are preserved.

Original submissions and audit history remain stored privately; no disposal schedule or automated purge is introduced. Privacy notices tell applicants to contact the Help Desk about corrections, retention and privacy requests. Staff arrange signed-form forwarding separately with PDAO.

## Verification

71 distinct backend tests passed across focused disposable MySQL runs, plus one full Chrome workflow test. The first backend run passed 70/71; the missing applicant-name heading was corrected and all 15 PDAO/integration/migration tests then passed. Existing Association decisions, PDF fields, member printing and navigation regressions passed. Tests used fresh MySQL instances with `.env` disabled, separate database grants and fictional applicants; they never used the application database.

```powershell
.venv\Scripts\python.exe -B scripts\g12_test_runner.py test membership.test_pdao_registration membership.test_registration_decisions membership.test_pdf_registration members.test_registration_print core.tests.test_workspace_navigation --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe -B scripts\g12_test_runner.py test membership.test_pdao_registration scripts.pdao_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Coverage includes required confirmation, duplicate/concurrent submissions, receipt isolation/revocation/expiry, CSRF, size/rate limits, unexpected and duplicate fields, uploads, permission revocation, audit rollback, immutable records, stale transitions, and additive migration rehearsal. An integration test uses the actual enabled Association policy and verifies confirmation → pending intake → Admin approval → Member → printable Word form.

Chrome completed both forms, approved the Association applicant, reviewed and printed the separate PDAO record, and recorded forwarding. Backend assertions confirmed exactly one Association member and one independent forwarded PDAO registration. Desktop (1280px) and mobile (390px) layouts had no horizontal overflow. The print button invoked browser printing. The final fictional PDAO PDF has three A4 pages, readable applicant fields/consent, no clipped text and no printed navigation. Final browser run: `santolan-g12-tests-ks1mdn85`; copied screenshots, PDF and result summary are under ignored `.local/online-membership-20261026/browser/`. Chrome required execution outside the sandbox; the initial sandboxed session could not enable its debugging page.

Django database checks, migration drift checks and Git whitespace checks passed. Live public guidance and both form pages return HTTP 200 with enabled submission controls. Unauthenticated Membership Reviews requests redirect to login.

## Local installation

The guarded helper backed up the database, environment and media, checked the actual local MySQL identity, required exactly `membership.0009_pdao_online_registration` in the pending plan, and applied only that additive migration. Migration text SHA-256: `3bacff1a1753f1527fc46e795ec197a13394fd143387042ca8e3f234eec52f62`.

Backup: `.local/backups/online-membership-20261026-20261026-135229/`. All 389 existing rows across 116 prior tables were preserved, with the private file checked byte-for-byte. The two new PDAO tables were empty after migration; no pending migrations remained. EWAF dataset policy/scoring opt-ins remain false. Public health checks create ordinary empty browser submission contexts, not applicant or Member records.

The local environment was then enabled and the verified server started at `http://127.0.0.1:8000`. Public entry: `/membership/register/`. Admin entry: `/membership/reviews/`. No commit, push or public deployment was performed. Existing unfinished changes and original supplied documents remain intact.

## Follow-up: gender dropdowns

The owner requested dropdown options for the Association and PDAO online forms. Association Gender now uses Male/Female choices, matching the existing PDAO Sex dropdown. Both retain the optional blank choice. New unlisted values are rejected. When Admin reopens an older Association submission, its saved free-text value remains available so review or approval does not discard or force a change to that declaration.

Verified both dropdowns on the running website, allowed/invalid values, and preservation of older values in editable and read-only Admin forms. All 26 existing PDF registration and Association decision tests passed in fresh disposable MySQL (`santolan-g12-tests-eo__aqr9`). Django database checks and whitespace checks passed. No migration or existing applicant-data changes were required.

## Follow-up: numeric number fields

The owner requested that online fields labeled as numbers reject letters. Seven Association fields (ZIP, mobile, spouse/guardian contact, PWD, voter certification and PhilHealth numbers) and nine PDAO fields (PWD, landline, mobile, organization/emergency contact, SSS, GSIS, PSN and PhilHealth numbers) now enforce numeric input. Contact numbers and ZIP codes accept digits only; ID numbers also accept hyphens between digit groups, retaining the displayed PDAO format. The combined house-number/street field remains text because it contains the street name. Existing family/household counts retain integer validation.

The browser offers a numeric keyboard, blocks letter keystrokes and rejects invalid pasted text as a whole. It never silently strips letters to create a different ID. HTML patterns and server-side validation reject invalid values, including scientific notation. Values remain strings so leading zeros and ID separators survive submission and printing. Optional fields remain optional. Admin can retain an exact older declaration when reviewing an existing submission, while changed values must satisfy the new rule. No existing values were rewritten and no database migration was needed.

46 focused tests passed in disposable MySQL (`santolan-g12-tests-3x35491j`): the new number validation cases, source form checks, Association decision regressions and the separate PDAO workflow. The Chrome workflow also passed (`santolan-g12-tests-qmul2b6n`), checking numeric keystrokes, pasted text, fallback input events, leading-zero retention, both submissions, approval, printing and forwarding on desktop/mobile. Live HTTP checks verified all 16 fields and the updated JavaScript on the running website. JavaScript syntax, Django configuration, migration drift and whitespace checks passed.

## Follow-up: PWD No. is the member number for new Association approvals

The owner requested replacing Assigned member number with PWD No. in Membership Reviews and explicitly selected **Use the applicant's PWD ID as the member number**, rather than a label-only change. This supersedes the separate manual-number assignment for the current Association PDF/Word form's future approvals.

The review uses the existing submitted `pwd_number` field, labeled **PWD No.**, and removes the separate `assigned_member_number` input for this form contract. Admin sees the applicant's saved value immediately. On approval, that same reviewed value becomes the application's and Member's `control_number`; the original formatting and leading zeros remain intact. The retained registration profile and printable form use the same PWD value. Corrections require the existing correction permission and create a new revision, preserving the applicant's original declaration. A decision-only actor cannot replace the submitted PWD value. Independently posted member-number assignments are rejected for the current form.

Online applicants can still submit without an issued PWD number, but Admin must record a valid PWD No. before approving under the owner's selected identifier rule. Declining does not require it. Recording the number does not manufacture PRPWD verification, government approval or a new PDAO processing result. The separate PDAO queue continues to create no members.

Duplicate checks compare numbers with hyphens removed, so changing separator placement cannot create another member with the same PWD number; stored formatting is not rewritten. Concurrent duplicate approvals are covered. The decision audit records `member_number_source=pwd_number`. Completed reviews show PWD No. only when that provenance exists. Already approved members retain their existing numbers and historical labels; older registration contracts retain their established behavior. No application-data migration or bulk renumbering was performed.

59 backend tests and one Chrome workflow test passed across focused disposable runs. The combined run (`santolan-g12-tests-eiba34ik`) passed 59/60; the additional historical-record fixture initially omitted its required linked state. After correcting that fixture, its focused test passed (`santolan-g12-tests-hehlqqp0`). Coverage includes prefilled PWD No., approval/correction and immutable source history, duplicate separator variants, concurrent duplicate decisions, unauthorized number replacement, stale/repeated decisions, source-audit rollback, existing member preservation, inbox behavior, private member printing and PDAO separation. Chrome verified that the separate assignment input is absent, the submitted PWD No. loads automatically, and approval stores that exact value on the Member. Django checks, migration drift and whitespace checks passed. The existing local server reloaded the change; an already-open review must be refreshed before submission.
