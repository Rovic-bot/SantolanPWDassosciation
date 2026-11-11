# Eligibility and onsite information changes — October 29, 2026

## Owner-confirmed amendment

The owner clarified that an administrator must be able to mark a program
application Eligible without changing the member's information. Applicants who
report information changes should instead receive an instruction, on the receipt
with their reference number and QR code, to visit the barangay office to confirm
the change.

The current one-click eligibility action therefore no longer requires completing
the separate information-update/review step. It keeps the member row, original
application declaration and information-review history unchanged. An unresolved
change/uncertainty report remains pending and is recorded as a nonmandatory item
in the eligibility audit; Eligible does not falsely resolve it. The administrator
can still use the optional editor when confirming the information with the member
at the office. Existing identity/photo, required-submission, membership,
classification, permissions, version and audit safeguards remain in effect.

The submission receipt now displays **Confirm your information at the barangay
office** for `changed` and `uncertain` declarations. It instructs the applicant to
visit the Barangay Santolan office/PWD Association Help Desk and bring their
reference number or saved receipt, and explains that submission does not update
the member record. `unchanged` submissions do not get this instruction. The
notice is printable and still appears if QR rendering is disabled.

The existing verification-based QR/link flow is retained, as authorized and
validated in `docs/program-tracking-2026-10-24/validation.md`. The notice adds no
change details, member information, secret or new authority to the receipt/QR.
Existing scoring, final selection and release requirements are unchanged; this
amendment concerns the current eligibility action and receipt guidance.

This supersedes the information-update prerequisite described in the earlier
October 29 direct-review and information-update validation notes. The editor
remains available but is optional for eligibility.

## Validation

- **55 tests passed** in one disposable native MySQL run:
  `programs.test_direct_review`, `programs.test_information_update`,
  `programs.test_change_receipt`, `programs.test_tracking`, and
  `programs.test_application_workflow.ConfirmationEvidenceTests`.
  Command used `scripts/g12_test_runner.py` and
  `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`.
  Artifacts: `santolan-g12-tests-0f3izy3b`.
- New regression proves an eligibility reviewer without member-edit permission
  can mark Eligible while the report stays unresolved, with an unchanged complete
  Member row, unchanged submitted snapshot, no member-change event, no fabricated
  report-resolution audit and the correct Eligible display.
- Receipt tests cover changed, uncertain and unchanged declarations, retained
  reference/QR, QR-disabled behavior, private/no-store caching, session-bound QR
  access and absence of private report text/email. Submission leaves the member
  row unchanged. Existing tracking and legacy review/scoring guards still pass.
- Chrome/Playwright checked the synthetic receipt at widths 320, 390, 768 and
  1440, including visible reference, loaded QR, notice, print visibility, no
  horizontal overflow and no JavaScript errors. Only fixture HTML/QR and static
  files were loaded; no backend writes were made.
- Read-only rendering of the reported real application and its receipt returned
  HTTP 200 with the current saved-state display, office notice, reference and QR.
  All SQL writes were blocked. No real member or eligibility record was changed.
- Django/database checks, migration-drift checks and `git diff --check` passed.
  No migration is required. The identified development web process on port 8013
  was refreshed; its retained database and uploads were preserved.

Browser harness: `scripts/change_receipt_browser.cjs`.

- [Desktop receipt](change-receipt-2026-10-29/receipt-desktop.png)
- [Mobile receipt](change-receipt-2026-10-29/receipt-mobile.png)
- [Browser results](change-receipt-2026-10-29/browser-results.json)

The full repository suite was not run. All test data and saved screenshots are
synthetic; no actual application decision was made during verification.
