# Community Assistance Desk: return to a conversation

The owner authorized returning members to continue an existing assistance conversation. The later [reference-only access decision](community-assistance-reference-access-2026-11-10.md) replaces the initial three-field check: only the private conversation reference is required. This supersedes the older referral documentation's restriction to receipt-only public access for this specific workflow. It does not create member accounts or change program/application access.

## Current behavior

The later [five-field intake and dedicated-page update](community-assistance-conversation-pages-2026-11-10.md) replaces the separate intake steps and Community Assistance popup with a single form and independently scoped conversation pages. It preserves reference-only continuation and the live-message behavior.

The later [live conversation update](community-assistance-live-chat-2026-11-10.md) supersedes the original ten-second polling, native-only reply submission, manual admin refresh, and draft-revision behavior described below. It adds automatic updates on both sides, in-place sending, and safe handling of uncertain send results.

- The public desk offers New concern and Continue a conversation. New concerns retain the existing membership verification, private optional evidence, intake, and acknowledgment email.
- The submission receipt shows the private conversation reference and an Open conversation action for the verified submitter. Future acknowledgment/update emails include the same reference. Previously issued references and emails are not rewritten or resent.
- Returning users enter only their complete private conversation reference. The backend still checks the associated member's approved, active record; the user does not enter a name or PWD/control number.
- The full existing random `ASR-<UUID>` reference identifies the private conversation. Sequential `REF-` inbox aliases do not authorize access. No reference, name, or member number is placed in a URL.
- The conversation shows the original concern, recorded member-facing staff replies, and member follow-ups. Internal notes, evidence access history, files, staff account names, private contact details, and email-provider metadata are excluded from the public feed.
- A follow-up is appended to the same ticket's protected action history. It increments the ticket version without changing its issued reference or original concern. A Needs information ticket returns to In review; other open statuses remain unchanged. The owner subsequently requested that closing a ticket end public access entirely: closed references cannot reopen the conversation, read its messages, or send another reply. The member must submit a new concern. Staff retain the historical record. See [reply channels and closure](community-assistance-reply-channels-and-closure-2026-11-10.md).
- The admin conversation distinguishes member replies from staff replies. Follow-ups move their existing ticket to the top of the inbox's latest-member-activity ordering. Staff can reopen View ticket to read the latest messages. Existing staff email replies remain available in the public conversation even if email delivery later needs retry; the conversation does not claim delivery success.
- The public conversation checks for messages every ten seconds and has a manual Refresh conversation link. New messages append without replacing the reply draft. Closing the conversation popup removes its private contents; Finish clears access. Native pages and forms also work without JavaScript.
- Replies sent through an external email client are not imported into the website conversation. Evidence follow-up remains through the existing email/onsite process.

## Access and consistency

Conversation access is signed, bound to the current browser session and one ticket/member, and expires after the existing `REFERRAL_GRANT_SECONDS` (15 minutes by default). Every read/write rechecks active membership and the member source snapshot. Failed verification uses generic messages and existing member/IP/session throttles. POSTs retain CSRF protection; private responses are not cached. Intake grants and conversation access use separate session keys.

Member replies validate required text and length, lock the ticket and related member/application rows, check the displayed version, and append their audit action atomically. Repeating the same accepted POST returns the recorded message instead of creating another one. A draft keeps its original revision during background refresh; stale edits show current history and preserve the draft for deliberate resubmission. A separate per-member reply throttle uses `REFERRAL_REPLY_LIMIT` (60 per existing 15-minute window by default) and the existing throttle table.

No model changes or migrations are needed. No stored member, ticket, evidence, settings, or email records were modified by implementation or verification.

## Verification

- Django/database system checks passed; migration drift check reported no changes; both updated public JavaScript files passed syntax checks; `git diff --check` passed.
- Read-only inspections using the existing local member/ticket verified successful access with all three matching fields and rejection of incorrect details, non-private aliases, altered signatures, different sessions, absent access, and expired access. A SQL guard rejected any write statement.
- Inspected rendered conversation/verification pages and the JSON feed with the same read-only guard. The feed contains only ticket version/status and allowlisted member-facing messages. Missing access redirects the page to verification and returns 403 for the update feed.
- Form inspection checked required reference/message fields and the message length bound. The existing ticket/action/email counts and ticket version remained unchanged during these inspections.
- Browser inspection used locally rendered copies of the real existing conversation, blocking all POST requests. Light, dark, and high-contrast modes and mobile widths of 390/320 pixels had no horizontal overflow or JavaScript errors. The existing saved staff reply was used to inspect refresh/append behavior; drafts remained intact and repeated refreshes did not duplicate it. Closing the popup removed private conversation content. Receipt actions and standalone rendering were checked.
- No automated test suite, synthetic record, fixture, live message send, email delivery, or operational database write was used. Actual end-to-end message submission is left for the owner's manual testing. The local server was restarted with these changes.

Private inspection artifacts are in ignored `.local/development/referral-conversation-preview/`.
