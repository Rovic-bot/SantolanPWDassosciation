# Resources & Help request entry — 24 October 2026

The owner requested that members ask for assistance/referral support from the Resources & Help tab, provide their email address, subject and concern, and have those requests appear in the Admin Assistance Information with Referral Support Inbox.

Resources & Help now presents the assistance request section before the information topics. Its **Ask for assistance or referral support** button starts the existing member-verification flow. Resources & Help stays active in the navigation during verification, request entry and the private receipt. The Home shortcut points to this section.

The request now requires a subject of up to 200 characters, in addition to its existing required email and concern. The subject is stored with the immutable submitted details, participates in duplicate-submission checks and appears on the receipt and acknowledgment. Staff see the subject, email and concern preview in the private inbox and the full concern in ticket details. Existing member verification, optional later evidence, permissions, editable sender settings and email delivery controls are preserved.

Earlier tickets retain empty subjects and display an explanatory fallback. Their references, submitted-data fingerprints and existing email records are unchanged. No subject is invented for historical requests.

## Validation

- All 28 focused referral and Resources tests passed using a fresh disposable MySQL database. Coverage includes required/length/single-line subject validation, immutability, duplicate posts, escaped display, private staff access and active Resources navigation.
- The live HTTP journey started from Resources & Help, verified an existing fictional member and submitted email, subject and concern with real CSRF tokens. The same values appeared in the private Admin inbox and full detail. Repeat submission returned the same reference. Finish revoked receipt access.
- The subject was verified in the stored ticket and local acknowledgment. The test created one explicitly fictional ticket; no real email was sent.
- Before applying `assistance.0005_referral_ticket_subject`, a 60,247,658-byte SQL backup and row fingerprints were saved under ignored `.local/resources-help-20261024/`. All original rows and prior column values across 110 tables were preserved after migration.
- Exactly 16 scoped runtime files changed. Database checks, migration-drift checks and `git diff --check` passed. Visual browser automation was not performed.

Evidence: `resources-help-tests.log`, `resources-help-http-journey.json`, `resources-help-data-preservation.json`, and `resources-help-source-preservation.json`.

Live entry: `http://127.0.0.1:8003/resources/#referral-support`. The Admin inbox is `http://127.0.0.1:8003/assistance/referrals/inbox/`. Email still uses the private development outbox until sending credentials are configured, as described in `validation.md`.

## Owner clarification: request email is independent

The owner clarified that the member may enter any valid email address for this request; it must not come from or match the membership database. Both email fields now start blank. Help text explains that the address is for this request, while confirmation only checks for a typing mistake against the address just entered. Membership verification does not use email.

All 21 referral tests passed, including a regression that supplies an address different from the member record and verifies that both acknowledgment and staff update use that address without altering the stored member email. A live HTTP check confirmed blank email fields and the explanatory text. This check finished its verification session without submitting a ticket or sending email. No schema or data migration was required; only the form and test file were updated in the running instance.

Evidence: `independent-email-tests.log` and `independent-email-http.json`.
