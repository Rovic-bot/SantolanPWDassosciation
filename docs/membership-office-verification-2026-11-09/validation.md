# Office verification before Association membership approval — November 9, 2026

The owner clarified that sending an office-visit email must precede membership: the applicant remains pending, visits the barangay office to verify their information, and only then receives final Association approval and a separate membership confirmation email. This supersedes the premature approval/office-invitation sequence described in the November 8 approval-email validation. Historical decisions and saved messages remain unchanged.

## Implemented workflow

For online Association applications under Membership Reviews:

1. **Send office-verification email** sends the saved applicant an invitation to visit the barangay office / Association Help Desk with their PWD ID, application reference and membership requirements. The message explicitly says they are not yet a member. No Member or final membership decision is created.
2. The application remains pending. Successful sending must be recorded before final approval. The staff member must explicitly confirm that the applicant visited and their information was verified in person. Existing manual PRPWD and decision permissions remain required.
3. **Approve membership and send confirmation** creates the Member, records the visit attestation and final decision, and queues a separate email saying the applicant is now an Association member. The confirmation sends only after the transaction commits.

The office-email button uses saved information independently of unsaved approval-form edits. A visible correction link handles an incorrect saved address. A corrected revision requires its own invitation; changing the email only during final approval is blocked. Ordinary pending-review messages cannot satisfy the invitation requirement, even with identical wording. Repeated clicks and callbacks do not resend accepted invitations. Queued notices are cancelled when their source revision or final decision changes. Known delivery failures can retry the saved message; uncertain sends require investigation and cannot automatically resend or unlock approval.

Server-side checks protect direct and stale POSTs. The historical linked-membership decision and quick-approval endpoints cannot bypass the online office-verification workflow. Existing onsite intake/approval remains available for applicants already processed at the office. PDAO review and emails stay separate. Existing approved members are not revoked or reclassified, and old notification snapshots are not rewritten.

A final confirmation-email failure retains the completed membership decision and displays the existing retry controls. Acceptance by Gmail is not proof of inbox delivery. No new member account, public status lookup, government integration, scoring rule or membership checklist requirement is introduced.

## Storage and UI

No schema migration is required. Invitations reuse immutable `MembershipPendingEmail` snapshots and delivery attempts. The protected `office_verification_email_requested` action identifies the invitation purpose and its source revision. Final `office_information_verified` actions retain the attesting staff member, time, revision and invitation identifier atomically with approval. Generic pending notices have no such invitation action.

The review shows invitation delivery status, a separate office-verification checkbox, pending status and final approval controls. Public form, receipt, confirmation and versioned policy instructions now explain the correct sequence. The existing privacy, print-preview, correction, PRPWD and pending-email controls are retained.

## Validation

All **105 distinct focused tests** passed across the final runs, including two real Chrome workflows. The broad run passed 104/105; its remaining legacy streaming-download test needed to consume the Django test client's closing iterator instead of emitting a late request-finished signal inside its test transaction. That test and the following transaction-isolation regression passed on rerun (2/2). The final invitation/decision suites passed again (35/35) after preserving compatibility with historical decision request digests. No known failing case remains in these scoped checks; the entire repository suite was not run.

The broad command was:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test membership.test_office_verification membership.test_registration_decisions membership.test_approval_email membership.test_pending_email membership.test_onsite_registration_alignment membership.test_registration_handoff membership.test_pdao_registration.PDAORegistrationTests scripts.membership_pending_browser_qa scripts.membership_approval_email_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Checks covered missing/failed/unconfirmed invitations, explicit office attestation, direct-route bypass, stale edits, changed recipients/revisions, duplicate and concurrent requests, commit-only delivery, audit rollback, protected recipient selection, permission/CSRF enforcement, final-email retries, saved originals, onsite behavior, separate PDAO processing and member creation. Synthetic prerequisite fixtures were updated for existing approval tests; the new suite exercises actual invitation queueing and delivery through the in-memory email backend.

Chrome completed online submission, invitation sending, pending status, PRPWD review, office attestation and final approval, then verified the separate confirmation email status after the member-record redirect. Desktop, 390px and 320px checks passed without overflow or JavaScript errors. The pending-message and private form-preview workflow also passed. Screenshots were visually inspected; all pictured applicants and emails are fictional.

`makemigrations --check --dry-run` on an isolated MySQL instance reported no changes. Database configuration checks, Python/JavaScript syntax checks and `git diff --check` passed. No real applicant email was sent during development or validation.

## Local activation

The retained local app at `http://127.0.0.1:8013/` was restarted after validation. The existing local policy was backed up before updating only its version, form/privacy versions, authority reference, privacy notice and visit instructions. No migrations or database updates were used for activation.

All **133 tables** retained identical columns and row fingerprints across the restart. A subsequent public-form HTTP 200 check confirmed the new instructions; it created only the normal transient form context, session and request-limit records. No Member, membership decision or applicant email was created by activation. One previously unconfirmed program email from more than a day earlier was preserved without modification or resend.

Private activation script and policy backup remain in ignored `.local/membership-office-verification-20261109/`. Sanitized evidence: [activation checks](activation.json), [desktop invitation](office-invitation-1440.png), [mobile invitation](office-invitation-390.png), [320px invitation](office-invitation-320.png), [final confirmation status](approval-email-1440.png), [invitation text](synthetic-invitation.txt), [membership confirmation text](synthetic-email.txt).
