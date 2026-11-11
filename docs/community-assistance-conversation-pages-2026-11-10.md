# New concerns and dedicated conversation pages

November 11 follow-up: the owner added a required Concern field after Type of assistance needed. The form now has six required fields and uses the concern as its opening message; see [Concern field validation](community-assistance-concern-field-2026-11-11.md). The five-field description below records the earlier implementation.

The owner requested a single New concern form with five required fields, followed immediately by a full conversation page. Continuing an existing reference must also open a full page rather than the Community Assistance popup.

## Implemented flow

- New concern has exactly five visible, required fields, in this order: Association control number, Registered full name, Email address, Subject, and Type of assistance needed. The button is Submit. The separate Concern, supporting-evidence, and acknowledgment-checkbox inputs are absent from this new form.
- Submission still matches the registered control number and full name to an approved, active Association member. Verification and ticket creation run in one transaction. The supplied subject is the opening concern; the member can describe it further in the conversation.
- A visible notice beside Submit explains accuracy, email access, privacy, and the absence of guaranteed assistance/approval/selection. Choosing Submit acknowledges that notice, replacing the earlier separate checkbox. Existing acknowledgment constraints remain enforced.
- A signed, expiring, session-bound hidden request key identifies the intake grant. Retrying the same form reuses that grant and the existing submission fingerprint instead of creating another ticket or acknowledgment email. It does not replace membership verification.
- A successful new submission opens its protected conversation page directly. The original receipt/start endpoints remain available for older receipts; the old second-step form URL now redirects GET requests to New concern. Already-open legacy POST forms retain their validation and also lead to the conversation on success.
- Continue a conversation still asks only for the complete private conversation reference. Successful verification opens that conversation's full page. Resources & Help links directly to both entry pages, and no longer includes or opens the Community Assistance dialog. Program application tracking keeps its separate popup.
- The conversation reference is visible near the conversation heading so a member can save it immediately. Existing automatic updates, in-place message sending, and closed-reference behavior remain in effect.

## Page isolation and retained protections

Each conversation has a separate navigation URL with an opaque page identifier, unrelated to the private ASR reference. The page URL alone does not authorize access. Its signed access token remains in the originating browser session and is bound to that session and ticket. Opening another reference does not redirect an existing page's reads or replies to the newly opened conversation.

The page and its update/reply endpoints use the same ticket-specific grant. Private references are not placed in URLs. Missing or expired access requires reference verification; closure removes public conversation access. Session page entries are bounded to ten conversations. Finish and clear this session clears all conversation page grants in that session. Existing membership checks, verification throttles, CSRF protection, immutable references, private evidence, audit history, acknowledgment mail, and duplicate-reply protection remain in use.

No schema change or migration is required. Historical concerns, evidence attachments, tickets, issued references, emails, and audits are retained.

## Verification

- Django/database checks, migration drift check, affected JavaScript syntax checks, and `git diff --check` passed.
- Read-only inspections confirmed the exact five required fields and rejected missing fields, invalid email/type, multiline subjects, incorrect registered identity, altered intake keys, and different-session keys.
- Existing real conversation data verified page redirects, page-specific message/update URLs, stable reopening, independent access from the old shared conversation slot, rejection in another browser session, rejection of unknown page identifiers, and cross-conversation reply rejection. Missing access did not create a conversation page entry.
- Browser previews checked native full-page navigation from both New concern and Continue, no Community Assistance popup, a visible private reference, scoped automatic updates, and in-place replies. Desktop and 390/320-pixel layouts had no horizontal overflow or JavaScript errors.
- Entry submissions were intercepted to preview the existing ticket destination; actual server redirect responses were inspected separately. No new concern, grant, message, email, or operational database record was created during verification. Full creation and acknowledgment delivery remain for normal/manual use. No automated test suite or synthetic operational records were used.

Private inspection artifacts are under ignored `.local/development/conversation-pages-preview/`.
