# Immediate action feedback — November 11, 2026

Owner request: make email, EWAF generation, and other processing actions feel responsive with immediate UI updates.

## Behavior

- Shared `action-feedback.js` / `action-feedback.css` run in the public portal, custom Admin workspace, and native Django administration. Accepted native form submissions immediately show a pending label, spinner, and status message. The original named submitter, CSRF token, input values, and validation remain intact. Repeated clicks and repeated `requestSubmit()` calls are blocked while the form is pending.
- Existing asynchronous controllers explicitly start and finish the same feedback for eligibility/document reviews, program and event dialogs, record dialogs, publication, announcement composition, program application submission, assistance release/undo/email retry, private conversations, program/page editing, EWAF generation, human selection, and weight previews. Native membership/PDAO/member-email and settings forms use the shared submission handler. Buttons that only open or switch UI retain their existing immediate behavior.
- The submitted action appears pending immediately. It is not shown as successfully sent, published, approved, released, or ranked until the existing server response establishes that result. Old saved rankings remain visible during generation. A lost ranking response stops its spinner and offers a GET-only status reload; no automatic calculation POST is replayed.
- Slow requests keep a pending message. Overlapping read-only previews retain feedback until all requests finish. Existing page-specific failure messages and validation results remain authoritative. Returning through browser history restores native form controls, including originally disabled controls. Workspace replacement removes scoped listeners, pending UI, and timers.
- Report export links show preparation feedback while downloading the generated response, require an attachment response, preserve the server filename, and restore the link on failure. They do not treat a login page or permission error as a downloadable report.
- Visible feedback stays inside the form to preserve adjacent layout panels. A separate live region is outside the form's busy state. Spinner motion respects both the operating system preference and the system's Reduce Motion setting.

This is a presentation and interaction change. SMTP transport, post-commit email services, server processing time, scoring formulas, permissions, history, and human decision requirements are unchanged. No new worker, background queue, database schema, or automatic retry was introduced. Server acceptance of email still does not prove inbox delivery.

## Validation

`node scripts/action_feedback_browser.cjs`: **14 synthetic browser checks passed** using actual shared scripts and actual eligibility, EWAF, and receipt-popup controllers against a temporary loopback fixture server. Covered immediate pending feedback, required-field validation, cancelled submission, named action/CSRF preservation, duplicate suppression, server rejection, interrupted responses, confirmed ranking replacement, retained ranking after rejection, explicit reload after an uncertain calculation, dynamically loaded email retries, report downloads/errors, overlapping requests, slow requests, mobile layout, reduced motion, cached-page restoration, and workspace cleanup. No JavaScript runtime errors.

Existing synthetic full-template browser checks also passed for workspace double-click routes, event popup submission, repeated sidebar navigation, and annual-observance create/edit at 1440, 390, and 320 px. A rendered mobile observance form was inspected with its pending save feedback visible. These checks intercept application writes and use fictional data.

JavaScript syntax checks passed for all 17 changed/new production scripts. `git diff --check` passed. No real email was sent, no actual EWAF calculation was run, and no member or program record was changed during validation.
