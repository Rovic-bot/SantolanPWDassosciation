# Online membership approval email — November 8, 2026

The owner requested that online Association membership applications require an email address and PWD number, and that clicking **Approve membership** sends an email through the connected Association Gmail. The email invites the applicant to the office to verify their information and tells them to bring their PWD ID.

## Implemented behavior

- New online Association applications require both fields in the browser and in server/service validation. The PWD number retains the existing digits/hyphens validation. Public form help, privacy notice and receipt instructions explain the approval email and office visit.
- The existing Admin decision and manual PRPWD workflow remain in place. A successful online approval creates one immutable recipient/message snapshot in the same transaction as the membership decision; sending starts only after commit. Repeating the approval or delivery callback does not resend an accepted message.
- The recipient is the email in the reviewed revision. The sender is the connected Association Gmail account. The plain-text email includes the applicant's name and application reference, asks them to visit the Association office / Help Desk, and says to bring their PWD ID. It does not include the PWD number, birth date, disability or household details.
- The private review and resulting member record display delivery status. An authorized administrator can retry a failed or unconfirmed attempt. Unconfirmed deliveries display a duplicate-message warning before retry; there is no automatic resend. Sender changes cannot silently substitute a different sender for a saved notification.
- An email failure does not undo a completed membership approval. Delivery attempts are recorded separately. Older submissions without a valid email remain reviewable and explicitly show that no email was sent. Onsite registration and separate PDAO applications do not send this online approval notice.
- Existing submitted revisions, issued references, membership decisions and other workflows remain unchanged. This is the owner's November 8 online requirement, not a change to the separate PDAO approval process or to historical intake snapshots.

## Verification

The following command passed **75 tests** on a fresh, disposable native MySQL database:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test membership.test_approval_email membership.test_approval_email_migration membership.test_registration_decisions membership.test_pdf_registration membership.test_onsite_registration_alignment membership.test_pdao_registration.PDAORegistrationTests scripts.membership_approval_email_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Coverage includes required fields and invalid submissions; reviewed recipient and preserved originals; commit/rollback behavior; repeated and concurrent delivery; permission checks and retry confirmation; SMTP failure, uncertain delivery and failed connection close; sender binding; legacy submissions; onsite/PDAO regression; and an additive schema rehearsal.

Real Chrome browser checks completed the fictional public submission, manual PRPWD check and Admin approval, then verified the email status after the member-record redirect. Desktop, 390px and 320px views had no horizontal overflow or JavaScript errors. Tests used Django's in-memory email backend and fictional recipients. The screenshots explicitly identify the test outbox; they do not claim inbox delivery.

The existing Association Gmail connection successfully authenticated without sending a message. Actual recipient inbox delivery was not tested.

After activation, the running public form returned HTTP 200, required both fields, showed the updated privacy notice, and passed the three responsive widths without submitting an application. The runtime database check and `git diff --check` passed. `makemigrations --check --dry-run` reported no changes; its isolated no-database configuration intentionally produced a connection warning, so it did not verify migration history.

## Local activation and preservation

Migration `membership/0011_membership_approval_email.py` adds two notification tables and their constraints. The retained local database has no migration ledger and was originally synchronized from models. Following the existing local activation procedure, the tested migration's exact additive operations were applied directly after verifying the database and web-process identities and creating a private SQL backup. No historical migration chain was replayed.

All **127 existing tables** retained identical columns and row fingerprints. The two new tables were empty after activation. The local policy's version, form/privacy versions, authority reference, privacy notice and visit instructions were updated; unrelated policy settings and historical revision snapshots were preserved. The original policy was backed up. The server was restarted and passed the database check. Activation sent no email and did not approve any application.

Private backup and activation script: `.local/membership-approval-email-20261108/` (ignored by Git). Sanitized evidence is saved alongside this note:

- [Preservation proof](preservation.json)
- [Live form checks](live-check.json)
- [Required email field](online-email-required.png)
- [Desktop approval status](approval-email-1440.png)
- [Mobile approval status](approval-email-390.png)
- [320px approval status](approval-email-320.png)
- [Synthetic email body](synthetic-email.txt)
