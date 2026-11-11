# Member information updates — November 10, 2026

Implemented the owner's requested public member update and staff review workflow. The owner explicitly chose to keep program access while an update or office interview is pending; only an administrator's **Needs verification** decision blocks new applications until approval. This is scoped authorization for this workflow, not an implementation of other TARGET documentation requirements.

## Public flow

- The home Guidance and support section now contains six cards. **Update member information** sits beside **How EWAF works** on desktop and stacks on mobile, using the existing light, dark and high-contrast palette.
- `/members/update/` asks for only the existing PWD number and full name, following the owner's subsequent simplification request. Matching active approved members receive a six-digit verification code at their **currently saved** email. The proposed replacement email cannot be used to unlock a record.
- There are no member accounts. The code is bound to a random session nonce, expires after ten minutes, allows five attempts, and is single use. Verified access expires after thirty minutes and is invalidated by a changed member version. Starting access is limited to five requests per number and twenty-five per source address per hour, using separately salted hashes and dedicated counters. `purge_member_update_windows` removes only expired counters, not request or audit history.
- Unmatched, inactive, archived and unavailable-email cases show the same generic code response without disclosing member details. Members without access to their saved email are directed to the Association Help Desk.
- The prefilled form reuses the Association online/onsite field definitions and public registration styling. The PWD number is disabled and server-validated against tampering. Supporting documents are brought to the office; this public flow does not expose or accept private attachments.
- Submitting creates a retained declaration and changed-field list. The current approved member record and original membership application remain unchanged. Duplicate submissions are idempotent, and concurrent submissions cannot create two pending requests for the same member.

## Staff flow and program access

- Member Directory shows and filters **Update needed** and **Needs verification**. Its preview and the member detail page link to **Review updated information**.
- The comparison shows only requested changes, with current approved and proposed values. Choices use their readable labels. Original submitted values remain retained; a fresh review preserves unrelated edits made by another administrator.
- **Verify this information** queues an email to the verified existing address asking the member to visit the barangay office for interview/screening. It uses the existing configured Association email connection and retains the sender, recipient, message and delivery attempt history. Repeated clicks cannot duplicate a claimed send. Explicit retry is allowed for a definite failure; uncertain delivery is not automatically resent.
- Approval requires the relevant staff permissions, a recorded successful invitation, interview/screening confirmation, review notes and current request/member versions. Approval applies only the requested fields through the existing protected member update service and preserves earlier source/audit history.
- **Mark needs verification** requires review notes and immediately blocks both program verification paths and already-issued application grants on recheck. Approval removes this block. Pending submission/invitation alone never removes program access. Previously submitted applications, rankings, selections and release records are not rewritten by the new status.
- Update submission, invitation, retry, approval and needs-verification actions have plain-language administration audit labels. Protected request snapshots and action/email history are retained.

## Database installation

- Added portable migration `members/0009_member_information_updates.py`: six new tables, no existing data migration or Member field changes.
- The retained local development instance uses model synchronization without a historical migration baseline. A blanket migration was not run. The local installation script created only the equivalent new table definitions after stopping the web process and taking a complete MySQL backup.
- Backup retained privately in `.local/member-updates-20261110/backup-20261110-081441/`. SQL and private logs remain ignored by Git.
- Backup SHA-256: `9d83a84e8ff4972eb329974658c1ea6da89b0b43f3039c98c82346cc123ba25e`.
- Before/after schema and row hashes confirmed all **133 existing tables and 3,850 rows unchanged**. Six new tables started empty; the migration ledger was not altered. See `database-preservation.json`; full hashes remain with the private backup.
- The server was restarted on `http://127.0.0.1:8013/`. All six new tables were still empty after live read-only checks; no real member update or email was created during validation.

## Validation

Final disposable MySQL run: **39 tests passed**:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test members.test_public_updates members.test_directory members.test_registration_edit.MemberRegistrationEditTests scripts.member_updates_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

The test runner verified a separate temporary MySQL instance and disposable test database. Email tests used synthetic records and the in-memory outbox. Coverage includes identity/session boundaries, expiry and attempts, CSRF, immutable PWD number, no-op and duplicate requests, concurrent submission, staff permissions, changed-field comparison and HTML escaping, email retry/uncertain delivery, interview prerequisites, stale reviews, audit rollback, protected history, directory filtering, both application verification paths and previously issued grants.

Browser evidence in `browser-results.json` verifies home-card placement, code-gated prefill, locked PWD number, submission, directory status, changed-field comparison, invitation, needs-verification blocking, reapproval, cleared access and a complete no-JavaScript verification/prefill flow. The prefilled form and admin comparison passed **18 layout checks** at 1,440, 390 and 320 pixels across light, dark and high contrast, without horizontal overflow or duplicate element IDs. Representative screenshots are synthetic.

`live-results.json` records six additional GET-only checks of the running home/identity pages, across three themes and desktop/mobile widths, plus new asset availability and navigation. Live screenshots contain only public pages. The Association email connection is configured, but no real-recipient delivery was exercised by QA.

Also passed: Django database check, model/migration consistency check with normal migration modules restored for detection, JavaScript syntax checks, guidance Tailwind build and `git diff --check`.

During development, two cache-header assertions were corrected to allow Django's stronger `never_cache` directives; a no-JavaScript harness click was changed to keyboard activation; public route context was added so the new pages receive the current portal theme. The final run above includes these fixes. The read-only live harness also now waits for the form and scopes input counts to it, excluding accessibility controls.

The new workflow does not change the earlier approved all-EWAF program policy, existing references, private document permissions, original membership submissions or unrelated unfinished work.
