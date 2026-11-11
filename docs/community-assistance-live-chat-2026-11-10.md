# Community Assistance live conversation updates

The owner reported that sending an online reply rebuilt the ticket view, scrolled back to the top, and restored Email as the destination. They requested automatic updates in both conversations and the inbox, a persistent destination choice, and a smaller composer without the visible Reply to member heading.

## Current behavior

- Admin and member replies use CSRF-protected asynchronous POSTs. The server returns the current conversation and validation/delivery feedback as JSON. Messages append to the existing view; the composer, draft, sidebar state, focus, and surrounding scroll position are retained. Native forms and redirects remain the fallback without JavaScript.
- The selected Email/Online conversation destination is retained in browser storage for the current administrator, including when reopening a ticket. Successful native submissions also retain the choice in the server session. Only the destination preference is stored in browser storage; message text and private references are not stored there.
- Both active conversations check for updates every two seconds after the preceding request finishes. The admin inbox checks every three seconds, updating its totals and results while retaining the current filters. New concerns and member follow-ups therefore appear automatically. These are short background requests, not WebSocket push; delivery timing also depends on request latency.
- Background checks pause while the page or conversation is hidden, resume when it becomes visible or the connection returns, and stop when the view is removed or access ends. Connection failures preserve the draft and retry reads automatically. Writes are never retried automatically.
- Incoming messages retain the current reading position unless the reader is already at the latest message. A successful own reply moves the message log to its newest entry without replacing the page or dialog. Background activity and email delivery history also update without rebuilding the composer.
- The visible Reply to member heading/icon is removed. The admin textarea uses two rows with a 64-pixel minimum height. Small screens have a bounded, scrollable conversation area so message bubbles cannot overflow behind the composer.

## Access and consistency

The new admin update route uses the existing staff/dashboard/referral permissions and private, noncached responses. Public reads and writes retain the signed, session-bound, ticket-scoped grant, membership rechecks, expiry, reply throttle, and closed-conversation rules. The public feed still contains only allowlisted member-facing message data; staff activities, contacts, evidence, and email-provider details remain private.

Public reply forms identify their intended conversation so switching to another conversation in a second tab cannot send an older draft to that other ticket. Mismatches preserve the draft and require reopening the intended conversation.

Staff retries of an already accepted reply now return its existing result when actor, revision, channel, and text match. They do not create another action or email job. Public replies retain their existing equivalent protection. In-flight writes and uncertain send results keep their submission revision for deliberate retry; normal background updates refresh the current revision without replacing a draft. Stale or invalid writes return current history and a readable error.

No model change, migration, stored-record rewrite, or mail-provider change is involved.

## Verification

- Django/database checks passed; migration drift check reported no changes; all four affected JavaScript files passed syntax checks; `git diff --check` passed.
- Read-only inspections rendered both conversation views and JSON feeds from existing records. They checked anonymous staff-feed rejection, absent public access, invalid replies, cross-conversation mismatch, public payload allowlisting, and replay of already-recorded staff/member replies. A SQL guard blocked writes; ticket/action/email counts and the ticket revision were unchanged.
- Browser inspection replayed existing saved messages through locally intercepted responses. All POSTs were intercepted; none reached the application or an email provider. It verified five send/error scenarios, stable view/form nodes, retained Online conversation selection after sending and reopening, automatic incoming messages in both directions, preserved drafts and reading position, automatic inbox results, and clearing a closed public conversation.
- Desktop and mobile previews confirmed the compact composer (about 67 pixels at the inspected desktop text size), missing visible heading, no horizontal overflow, and no message overlap with the mobile composer. No JavaScript errors were reported.
- No automated test suite, synthetic operational records, fixtures, actual new message, or email send was used. End-to-end creation of a new reply remains for the owner's normal/manual use.

Private inspection artifacts remain in ignored `.local/development/referral-live-preview/`.
