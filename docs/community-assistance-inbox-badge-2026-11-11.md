# Community Assistance Inbox badge

The owner requested a numbered badge for new concerns arriving in the Community Assistance Desk Inbox.

The admin sidebar now displays the exact number of concerns still marked Received beside the inbox link. When Applications & Verification is collapsed, its summary displays the same count. Zero hides the badge. This is the shared queue awaiting staff review, not a per-administrator unread-message count or a lifetime submission total. Existing begin-review behavior moves a concern out of Received when an authorized reviewer opens it; closing also removes it from this count. Follow-up messages in already-reviewed conversations do not increase the new-concern badge.

The count is rendered initially and refreshed with a small permission-checked JSON request every three seconds after the preceding request completes. Ticket-dialog changes, returning to the tab and reconnecting trigger another check. Updates change only the badge, retain page state, pause while hidden, stop after access denial and are disposed during workspace navigation. A temporary connection failure preserves the last count until a successful read. The endpoint returns only a number and is private/noncached; it requires the existing active staff, dashboard and referral-view permissions. It does not change ticket state.

The shared sidebar supports custom workspace pages and native Django administration. Existing theme tokens, accessible count labels, the mobile menu and large text are retained. No schema changes or migrations are required.

## Validation

- A SQL write guard confirmed the received-only count against existing records, independence from inbox filters, count-only response fields, private/no-store headers, refusal of POST, anonymous rejection and denial without referral permission. Unauthorized sidebar rendering did not fetch the count. Dashboard, inbox and native admin templates rendered both badge locations.
- Browser previews intercepted count responses to exercise arrival, review, zero, temporary failures/reconnection and permission denial without creating records. Checks covered automatic updates, stable page/scroll, collapsed/expanded group visibility, workspace navigation without duplicate polling, native admin, light/dark themes, and a four-digit badge with largest text on mobile. No JavaScript errors occurred.
- Django/database checks, JavaScript syntax and `git diff --check` passed. No Django test suite, actual concern submission, message send or email delivery was used; existing operational records were unchanged. Private preview artifacts are under ignored `.local/development/referral-notifications-preview/`.
