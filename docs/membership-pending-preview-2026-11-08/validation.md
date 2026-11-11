# Membership examples, pending email, income controls and form preview

Implemented the owner's November 8 request in the retained local development system.

## Behavior

- Online Association membership fields show examples such as `e.g. Dela Cruz`, `e.g. Juan`, and `e.g. juan.delacruz@example.com`. These are placeholders, not saved example values. Required email and PWD number validation remains in place.
- A new online form starts household monthly income at PHP 1,000. With the field focused, an upward mouse-wheel event adds PHP 500; downward scrolling subtracts PHP 500, down to zero. Arrow keys use the same increment. Applicants can type exact amounts, including zero and cents. The shared Association income control also works in staff forms, without replacing retained values. This changes input behavior only, not EWAF calculations or verification.
- **Leave pending** opens a popup with the saved recipient address and a required reason. **Send email and keep pending** saves an immutable message and review audit, then sends through the existing Association Gmail transport after commit. It does not create a member, approve or decline the application, or save unsaved edits from the approval form.
- Email status and the saved reason appear in the private review. Known failures can retry the same saved message. Repeated requests, concurrent duplicate clicks and delivery callbacks do not resend an accepted message. Uncertain sends cannot automatically retry. A queued notice is cancelled if the application was decided or its submitted revision changed before delivery.
- **View / print submitted form** opens an accessible popup containing the existing permission-checked form endpoint. **Print / Save PDF** prints that form, not the surrounding review. The preview fits small screens and returns to full A4 scale for printing. Close and Escape return focus to the opening link, including after focus moves into the preview frame. Direct links remain usable.

## Implementation and preservation

Migration `membership/0012_membership_pending_email.py` adds separate pending-message and attempt tables. The existing approval email transport is reused through a shared delivery function; approval notices keep their original storage and behavior. Pending send requests require current membership decision permission, the current intake version, a valid saved email, a reason and a unique request identifier. The server ignores submitted recipient overrides.

The form preview remains private, is not cached, and permits framing only by the same origin. Native form-access auditing remains enabled. Submitted revisions, issued references and historical decisions are preserved. The public explanation and configured privacy notice now mention pending-review emails.

## Validation

All tests used fresh disposable native MySQL databases and Django's in-memory email backend; no real applicant email was sent.

- `membership.test_pending_email`: pending status and original submission preservation, commit-only sending, duplicate requests and callbacks, permission checks, stale/final decisions, missing recipients, audit rollback, known failure and safe retry, uncertain delivery, queued-message cancellation, tampered recipient rejection, private preview access and concurrent duplicate requests.
- `membership.test_pending_email_migration`: exact additive migration rehearsal preserving the existing registration and sender configuration.
- Existing approval email, registration decision, PDF registration and onsite alignment suites passed their relevant runs. The onsite alignment test now allows online-only example placeholders while retaining its validation/field-contract comparisons.
- `scripts.membership_pending_browser_qa`: real Chrome at 1440px and 390px. Verified empty name fields with example placeholders; initial income 1,000; wheel increments to 1,500 and 2,000; keyboard decrement; manually entered cents and zero; pending popup cancellation; sending independently of incomplete unsaved approval edits; one captured email to the saved address; pending status; private print preview; printing the frame; Escape and focus restoration. Screenshots were visually inspected. The final browser run passed.
- `makemigrations --check --dry-run` with the normal migration map: no changes detected. Django database checks, JavaScript syntax checks and `git diff --check` passed.

The first test batch exposed two test-fixture callback/mock-order errors, corrected before follow-up passing checks. Browser follow-ups corrected the privacy-dialog setup, used an actual click to focus the income field, and found/fixed Escape handling within the preview frame. No known failing case remains from these runs; the entire repository test suite was not rerun.

Repeat the new tests with:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test membership.test_pending_email membership.test_pending_email_migration scripts.membership_pending_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

## Local activation

The retained local database uses a model-synchronized baseline without a migration ledger. After verifying its identity and stopping the identified web process, a private 12,155,443-byte SQL backup was created and checked. The tested additive operations were applied directly without replaying historical migrations. All 129 existing tables retained identical columns and row fingerprints; the two new notification tables were empty. No real email was sent during activation, and no membership decision was changed.

The existing privacy policy was backed up before updating its notice, version and authority reference. The local app restarted successfully on port 8013. A read-only verification checked the exact review/form reference supplied by the owner: HTTP 200, pending popup, preview link, same-origin frame, no-store response, example placeholder, initial income and increment. No pending notifications were created by verification.

Private backup and activation scripts remain in ignored `.local/membership-pending-20261108/`.

Evidence: [preservation](preservation.json), [live checks](live-check.json), [browser checks](browser-results.json), [examples](online-placeholders.png), [pending popup](pending-message-1440.png), [mobile popup](pending-message-390.png), [form preview](submitted-form-preview-1440.png), [mobile preview](submitted-form-preview-390.png). Screenshots contain fictional test applicants only.
