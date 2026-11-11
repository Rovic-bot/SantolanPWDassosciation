# Direct Gmail replies — 24 October 2026

The owner specifically replaced the computer's default email-app workflow with Google Gmail using the admin's signed-in Google account.

Both the private referral inbox and ticket detail now show **Reply in Gmail**. The link opens `https://mail.google.com/mail/` in a new tab with the submitted request email, subject and reference prefilled through Gmail's compose navigation parameters. No sender address, account index or `authuser` hint is imposed by the system. Gmail handles the Google session in that browser; the admin checks the selected account and clicks Send. Google documents account switching and default-account behavior in [Sign in to multiple accounts](https://support.google.com/accounts/answer/1721977?hl=en).

Links use `target="_blank"` and `rel="noopener noreferrer"`. Recipient and compose fields are URL-encoded. Evidence, concern details and internal notes are excluded from the compose URL. The member's submitted email remains independent of their membership record.

The follow-up option and confirmation now explicitly say Gmail. A staff-confirmed reply records `gmail_reply_recorded` with the actor, reply and status; older email-app actions retain their original labels and contents. Opening Gmail does not mark a message as sent. Recording a Gmail reply requires review/send permissions, a current ticket version and confirmation, and queues no duplicate system email. Automatic acknowledgments and existing system email records are preserved.

## Validation

- All 25 referral tests passed using fresh disposable MySQL. Gmail-specific assertions check HTTPS and the exact Google host, submitted recipient, subject/reference, absence of forced sender/account or injected recipients, safe new-tab attributes, permissions, manual confirmation, stale edits and rollback.
- Authenticated live HTTP checks verified the Gmail buttons on the inbox and detail, encoded compose fields, Gmail instructions and confirmation. There are no remaining `mailto:` reply links or default-email-app instructions on those pages.
- The live checks did not open a Google account, send mail or change ticket/email history. Signed-in Gmail composition and actual delivery were not browser-tested. Google session/account selection remains controlled by Gmail.
- Seven scoped runtime files were backed up and updated. No database migration was needed. Whitespace and runtime file checks passed.

Evidence: `gmail-tests.log` and `gmail-http.json`. This change supersedes the default-mail-handler behavior described in `email-app-replies-validation.md`.
