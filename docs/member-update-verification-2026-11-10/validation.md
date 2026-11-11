# Two-field member update verification — November 10, 2026

The owner requested that the member information update verification screen use only **PWD number** and **Full name**. Removed birthdate and saved mobile number from this form and its record-matching service. Updated the instructions to name the two required fields.

The existing saved-email code still protects access to the prefilled member record. Code expiry, session binding, attempt limits, generic unmatched responses, immutable PWD number, staff comparison, invitation and approval rules remain in place. This change is limited to member information updates; program verification forms and their matching rules were not changed.

Validation:

- **21 tests passed** using a separate disposable MySQL database: `members.test_public_updates` and `scripts.member_updates_browser_qa`, with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner` through `scripts/g12_test_runner.py`.
- Added an HTTP-level regression confirming only the two identity fields are required, the code goes to the saved email, pre-code access remains unavailable, and successful code verification opens the prefilled form.
- The browser flow asserts exactly those two identity fields and completes submission, admin comparison, office invitation, needs-verification application blocking, approval and no-JavaScript access. Existing legacy program verification continues using its own four-field test data.
- Live GET-only checks passed across light, dark and high-contrast modes at desktop and mobile widths. Screenshots and `live-results.json` show the new form; no real member submissions or emails were generated.
- Django's test system check, JavaScript syntax check and `git diff --check` passed. The local server was restarted. No schema or existing member data changes were required.

See `focused-tests.txt`, `browser-results.json` and the live screenshots in this directory. The earlier complete workflow validation remains in `../member-self-service-updates-2026-11-10/validation.md`.
