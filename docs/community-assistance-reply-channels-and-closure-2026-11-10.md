# Community Assistance reply channels and closure

The owner requested two admin reply destinations, no reply-status dropdown, collapsible Supporting evidence, and final closure of public conversation access.

## Implemented changes

- The reply selector offers Email and Online conversation. Email retains sender validation, email permission checks and the existing queued delivery/history. Online conversation saves a member-facing reply in the same ticket and does not create an email job or require an email connection. Staff with review permission but without email permission can use the online option.
- Onsite assistance is removed from new reply forms, and the server rejects that channel for new replies. Existing onsite history is preserved. New online staff replies are included in the private public conversation feed.
- The status input is removed from the form and from its backend validation. Sending a reply keeps the current processing status, except an unreviewed Received ticket moves to In review. A submitted status parameter cannot change ticket status. Closing remains a separate explicit action.
- The owner's later clarification replaces the evidence-only disclosure with [collapse of the entire sidebar toward the right](community-assistance-sidebar-collapse-2026-11-10.md). Existing private preview/download permissions remain unchanged.
- Close ticket retains the audited closed record, closes the admin popup, and returns to the inbox. The inbox defaults to Open conversations; Closed and All statuses filters retain staff access to historical records.
- A closed ticket cannot issue new conversation access. Already-issued conversation access is rejected on every subsequent read, polling request, or reply. The original intake receipt cannot reopen a closed conversation either. Matching a finished reference shows a finished notice and a Start a new concern link, without old messages or the private reference.
- An open public conversation clears its messages, reference and reply form when the next update check reports closure. The member must submit a new concern to receive a new reference. This replaces the earlier read-only public access for closed conversations.

No migration or record deletion is involved. Historical messages, issued identifiers, files, email records and audits remain intact.

## Verification and limits

- Django/database checks, migration drift check, JavaScript syntax checks and `git diff --check` passed.
- Read-only form inspections accepted Email/Online replies without status or manual notes, rejected the removed Onsite option, and retained email sender-version validation. Source review confirmed that only the Email branch invokes the email queue.
- The common closed-ticket access gate was checked using an existing ticket object with its status changed only in memory and never saved. It rejected both the direct gate and access issuance. The finished response cleared the in-memory conversation session and contained no old messages/reference. No actual ticket was closed for verification.
- Browser inspections used private renderings of real existing tickets and blocked all POST requests. The channel control updated the submit label and destination text; no status dropdown remained. Evidence collapsed and expanded by mouse/keyboard. Light, dark, high-contrast, mobile and standalone views remained usable with no horizontal overflow or JavaScript errors.
- A read-only browser check supplied the closed update response to verify that an already-open public page clears the conversation and offers a new concern. The admin closed-result marker closed its popup. These UI checks did not submit a message or change a ticket.
- Existing ticket/action/email counts were unchanged during guarded inspections. No automated test suite, fixture, synthetic operational record or live email send was used. Actual submission and ticket closure remain available for the owner's manual verification.

Private inspection artifacts are under ignored `.local/development/`. The local development server was restarted after the changes.
