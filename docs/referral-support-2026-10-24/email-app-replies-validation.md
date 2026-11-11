# Replies from the admin's email app — 24 October 2026

Historical validation: the owner subsequently replaced this default-mail-handler workflow with direct Gmail links. See `gmail-replies-validation.md` for current behavior.

The owner requested that admins respond to a referral ticket using the member's provided email address and the account signed in on the admin's computer.

The private Assistance Information with Referral Support Inbox and ticket detail now provide a **Reply by email** action. It prepares a `mailto:` draft with the request's email address, its subject and immutable reference. The computer/browser selects its configured email handler; the admin chooses the signed-in sender account in that app and presses Send. The system does not inspect browser sessions, choose a From account or submit the draft automatically.

The compose link includes only the recipient, subject and a short greeting/reference body. It does not include evidence, internal notes or the member's concern. Address/query values use percent encoding following [RFC 6068](https://www.rfc-editor.org/rfc/rfc6068). If no handler is configured, the page explains how to use a preferred mail handler or copy the recipient and reference into the email service.

For authorized senders, the ticket review form defaults to **Email sent from this computer**. After sending, the admin pastes the reply, records the review notes/status and confirms that the message was sent in the email app. This saves an append-only `email_app_reply_recorded` action with the authenticated actor, reply and processing status. The record represents the admin's confirmation, not verified provider delivery. Opening a draft creates no sent record, status change or email attempt. Saving an email-app reply queues no system email.

Workspace/inbox access plus review and send permissions are required for the reply action and recording. Stale edits, missing confirmation and closed-ticket edits remain rejected. Failed audit writes roll back the status change. Staff with review-only permission retain onsite follow-up. Automatic acknowledgment and the explicitly labeled configured-Association-email option retain the existing sender settings and durable email-attempt history.

## Validation

- All 25 referral tests passed on fresh disposable MySQL. New checks cover request-address selection, encoded query parameters without injected recipients or forced sender, no writes when opening the page, required confirmation, no second system email, permissions, stale edits, closed tickets and audit rollback.
- Live authenticated HTTP checks verified reply links in both the inbox and ticket detail, their recipient/subject/reference, the default follow-up channel and the manual confirmation control. No mail application was launched and no real reply was sent.
- The live check left referral email/action counts and the existing ticket version unchanged. The seven scoped runtime files were backed up privately before updating. No schema/data migration was required.
- Migration-drift and whitespace checks passed. The root's ordinary database on port 3307 remained offline; verification used disposable MySQL and the guarded local runtime on port 8003.

Evidence: `email-app-tests.log` and `email-app-http.json`. Sending from the user's actual email app remains a user-controlled action, dependent on that computer's mail-handler configuration.
