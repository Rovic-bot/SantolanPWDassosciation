# Member update confirmation popup — November 10, 2026

Replaced the large submitted-update guidance layout with an automatically opened confirmation dialog. After the server saves an update, the member sees **Your update is awaiting review**, a short explanation, and **Finish and return home**. The dialog also shows the appropriate message when an existing request has been approved or needs verification.

The popup uses the shared public palette, rounded card styling and dimmed/blurred backdrop. It fits narrow screens and scrolls internally if needed. Native modal behavior makes the background inactive; keyboard focus stays in the dialog. The close button and Escape use the same CSRF-protected finish action as the primary button, clearing the verification session and returning home.

The protected POST/redirect/GET submission flow, saved pending request and admin approval rules were not changed. No AJAX submission or automatic resubmission was introduced. With JavaScript disabled, the same compact confirmation and finish button remain usable inline.

Validation:

- The complete synthetic browser test passed using the disposable MySQL runner: `scripts.member_updates_browser_qa` with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner` through `scripts/g12_test_runner.py`.
- **27 layout checks** passed across the prefilled form, confirmation popup and admin comparison at 1,440, 390 and 320 pixels in light, dark and high contrast. The popup's nine checks verify modal state, viewport fit, no horizontal overflow, unique IDs and removal of the old large guidance layout.
- Verified keyboard focus wrapping; close and Escape returning home and clearing access; the no-JavaScript confirmation/finish path; staff comparison and invitation; needs-verification blocking; and approval restoring program access.
- Test fixtures and email outbox were synthetic. No real member update or real email was generated during validation. No schema or existing-record changes were needed.
- JavaScript syntax checks and `git diff --check` passed. An initial JavaScript strict-mode syntax issue was corrected before the final passing browser run.
- Restarted the local server and confirmed both new static assets return HTTP 200.

See `browser-test.txt`, `browser-results.json` and the six popup screenshots in this directory.
