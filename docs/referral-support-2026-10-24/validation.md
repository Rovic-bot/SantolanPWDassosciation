# Assistance Information with Referral Support — 24 October 2026

The owner authorized a separate member-only assistance/referral inbox, required email acknowledgments and updates, optional evidence that may be provided later by email or onsite, and an editable Association email address. The initial address is `bagongalyansasantolanpwd2011@gmail.com`. These instructions authorize this scoped implementation beyond the earlier phase-4 design-only gate.

## Implemented behavior

- Home → Integrated Digital Services links to the referral service. Non-members are directed to Resources & Help → Where Can I Get Help? The existing reviewed Resources implementation is included in the local runtime; unpublished provider information remains unpublished.
- Registered control number, name, date of birth and contact number must match an active, approved member with recorded manual PRPWD verification. Failures are generic and rate limited. A separate, session-bound, expiring referral grant is rechecked against current membership before submission. Program and membership grants do not authorize this service.
- The digital form collects the verified name, current address/contact number, required email with confirmation, assistance type, concern and acknowledgment. Up to three validated private evidence files are optional. Evidence may instead be supplied later by email or onsite.
- Submission atomically creates one immutable `ASR-` reference, source snapshot, initial history and acknowledgment email job. Repeating the same submission in that verified context returns the same reference without sending another acknowledgment. Different data cannot overwrite the original ticket.
- The private receipt requires the original session and grant. Finish revokes access. There is no public reference lookup, member account or status tracker.
- Admin → Applications & Verification → Assistance Information with Referral Support Inbox supports private review, evidence downloads, status changes and email/onsite instructions. Statuses describe processing: Received, In review, Needs information, Referred and Closed. Closed history cannot be reopened or rewritten. No status grants funding, referral approval or beneficiary selection.
- Internal review notes are excluded from outgoing email. Evidence files are not email attachments. Evidence access, review, sending and configuration use separate permissions in addition to workspace/inbox access.
- Association email settings are editable in the inbox. Each change requires a reason, rejects stale versions and records the actor and previous/new addresses. New messages use the saved sender and reply-to address; existing message records retain their original sender, recipient and body.
- Email delivery claims a persisted job before contacting the provider. Completed attempts retain their result without SMTP response contents. Failed or unconfirmed attempts require an explicit, reasoned staff retry. Already accepted mail cannot be retried. `manage.py send_referral_emails --limit 50` resumes queued messages only.

Referral records do not create or update membership applications, program applications, assistance approvals/releases or EWAF results. Existing registration, printing, household criteria, source integration and program controls remain in place.

## Local runtime and schema

The running fictional workspace is `http://127.0.0.1:8003/`. The normal Start System shortcut retains its existing guarded launcher. Initial Association email configuration was saved through the audited service.

Before migration, a 60,226,914-byte SQL backup and hashes of every existing row were saved privately under `.local/referral-support-20261024/`. After the additive migrations, all 81,228 original rows and their prior column values across 101 tables were preserved. The source change manifest limits the runtime update to 34 reviewed files; 852 other existing files remain unchanged.

Applied runtime migrations:

- `assistance.0004_referralwindow_referralaction_referralgrant_and_more`
- `core.0002_resource_publication_metadata` (existing reviewed Resources dependency)

The root referral migration depends on `members.0007_household_registration_criteria`. The isolated runtime's equivalent household migration is `members.0006_household_registration_criteria`, so only that dependency name differs in its referral migration. Unfinished member information-review work was not brought into the runtime.

## Validation

- Root: 73 tests passed across referral verification/intake, editable email settings, permissions, private evidence, concurrent duplicate submissions, single-claim email sending, failure/retry behavior, audit rollback, existing assistance workflows, Resources and PDF registration.
- Runtime: all 101 tests passed, including the referral suite, existing assistance workflows, Resources, and the runtime-only program-intake/source-integration suite.
- Live HTTP: membership verification, optional evidence, reference receipt, repeat submission, cross-session rejection, Finish revocation, Admin inbox, staff email update and editable sender page all passed with real CSRF tokens and same-origin headers.
- The live journey created one explicitly fictional referral ticket and two messages in the private file outbox. No real email was sent. Program application, assistance case/release and operational EWAF run counts remained unchanged.
- Runtime database checks and migration-drift checks passed. Root migration-drift check reported no changes; its ordinary development database on port 3307 was offline, while the separately guarded runtime database on port 3308 was checked successfully.
- `git diff --check` passed. Visual browser automation was not performed; the live checks used HTTP and the isolated suites exercised rendered templates.

See `test-results.json`, `http-journey.json`, `data-preservation.json` and the retained test logs for final results. Private database backups, session fixtures and credentials remain under ignored `.local/` paths.

## Email delivery setup

The fictional runtime defaults to `django.core.mail.backends.filebased.EmailBackend`, with messages under `.local/dual-registration-20261024/referral-email-outbox/`. Its UI explicitly identifies these as development-outbox messages. An editable address alone does not authenticate a Gmail account.

For real sending, configure the process environment before restarting the local server: `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, `EMAIL_USE_SSL=False`, and the authorized account's `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`. Keep credentials local and out of source control. The runtime deliberately disables project `.env` loading, so environment variables must be supplied to the launcher. Ordinary root configuration has examples in `.env.example`.

For Gmail password-based SMTP, an eligible account can use an app password with 2-Step Verification. Google documents the availability restrictions and setup in [Sign in with app passwords](https://support.google.com/accounts/answer/185833?hl=en); SMTP connection details are in [Gmail IMAP/SMTP documentation](https://developers.google.com/workspace/gmail/imap/imap-smtp?hl=en). A replacement sender must be authorized by the configured provider. OAuth or a different Django email backend can be configured separately if the provider requires it.

Changing the Association address through Admin does not require a restart. Changing provider credentials or backend environment settings does. Existing queued messages retain the address with which they were created; review failed or unconfirmed attempts before retrying.
