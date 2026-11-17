# Immediate pending feedback and message previews - November 17, 2026

Owner request: optimistic UI across all loading and send actions, especially email.

## Behavior

- Shared accepted form submissions and existing asynchronous actions now display a persistent pending status card. Slow requests update the status after 15 seconds. Existing inline feedback, accessible announcements, duplicate-submit protection and server result handling are preserved.
- A thin indeterminate progress bar follows existing busy states for navigation, filtering, dialogs, processing and downloads. Background polling does not create repeated notifications.
- Staff email/online replies and public conversation messages appear immediately as explicitly pending outgoing bubbles. They contain text only and have no saved message ID. Server confirmation replaces the preview with the saved message. Rejected or interrupted requests remove the preview and preserve the draft and retry revision.
- A saved conversation reply and failed email delivery remain distinct. Email acceptance and delivery statements still come from existing server responses. No new SMTP transport, queue, automatic write retry, schema, permissions or workflow policy is introduced.
- Pending cards remain visible above modal dialogs without taking keyboard focus. Dark mode, high contrast, reduced motion and 320 px mobile layouts are supported. Workspace disposal removes pending UI and private previews.

## Predeployment validation

- `node scripts/action_feedback_browser.cjs`: 14 existing synthetic browser checks passed, covering native validation, CSRF/named submitters, duplicate prevention, actual eligibility/EWAF/receipt controllers, rejection, interrupted responses, downloads, overlap, slow requests, reduced motion, browser history and disposal. Updated spinner locators to distinguish the submit-button spinner from the additional status-card spinner.
- `node scripts/optimistic_feedback_browser.cjs`: 16 checks passed with 10 fictional loopback POSTs. Covered staff/public confirmation, rollback, lost responses, text safety, duplicate prevention, email-delivery failure, expired access, modal focus, mobile themes, busy-state progress, overlap and cleanup. No JavaScript runtime errors. See `preview-checks.json`.
- Real release public, custom Admin and native Django base templates rendered with database access prohibited. Five changed templates compiled. Eighteen browser combinations passed: three layouts, desktop/mobile, light/dark/high contrast; no missing static assets or JavaScript runtime errors. See `template-checks.json` and screenshots.
- `.venv\Scripts\python.exe scripts/current_development.py check`: no issues.
- JavaScript syntax and `git diff --check` passed. Changes were applied independently to the current local source and isolated deployment checkout, preserving preexisting template differences and unfinished work.

No real email, membership record, application, ranking or release was created or changed during validation. Simulated delivery responses verify UI behavior, not external inbox delivery.

## Live verification

- Render deploy `dep-dbu2vojm8hqs73dvfj7g` became live at `2026-11-17T10:44:56.46253Z`, running commit `7cc09bc621158152fa71aa4f3be11489fe496936` on the existing deployment branch. Service configuration and automatic-deploy settings were preserved.
- `https://santolan-pwd-system.onrender.com/healthz/` returned HTTP 200 and `status: ok`.
- Nine content-hashed published CSS/JavaScript assets matched the release Git bytes exactly. The Home page loads the new shared feedback and public-conversation assets. See `hosted-assets.json` for URLs and SHA-256 hashes.
- A read-only live Announcements filter request was held briefly in the verification browser. The existing results remained visible, the new progress bar appeared while waiting, and it cleared when the actual server response arrived. No production POSTs, blocked requests or JavaScript errors occurred.
- The 16 conversation/feedback checks passed again using the downloaded, byte-verified deployed assets and fictional loopback responses. See `hosted-checks.json`. This confirms published client behavior without sending real emails.
- Render returned no application error logs between activation and the post-deployment check at `2026-11-17T10:46:02Z`.
