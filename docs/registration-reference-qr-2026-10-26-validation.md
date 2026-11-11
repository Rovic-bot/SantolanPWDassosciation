# Public membership reference QR and onsite completion — 2026-10-26

The owner requested a reference number and QR after public online Association registration, instructions to visit the Barangay office to confirm/verify information and bring the PWD ID Card, and reference-based prefill on Admin onsite registration with only the PWD number left to enter. This explicitly authorizes the reference QR in this scope; it does not authorize a public tracker or reference-only access to private data.

## Implemented behavior

- Both the immediate receipt and the Done confirmation display the already issued reference and a real PNG QR containing exactly that displayed reference. Generation uses the existing local `qrcode` dependency; no external service receives the reference. Existing short aliases, original references and staff lookup remain unchanged.
- The receipt says to visit the **Barangay Santolan office**, confirm and verify information with the PWD Association Help Desk, and **bring the PWD ID Card**, reference/QR and existing required documents. The card is expressly listed in the visit checklist. No PDAO issuance or government verification is implied.
- A **Print / save reference slip** control prints the reference, QR and visit instructions. The existing membership-form print command and source document layout remain separate. The textual reference and copy control remain available alongside the QR.
- Admin **Onsite Member Registration → Already applied online? → Load online application** accepts the same issued reference or a pasted/scanned QR value. The lookup is placed before the blank form's guidance. It opens the same retained registration, with all submitted fields populated and **PWD No. required**. The instructions tell Admin to confirm the information with the applicant's PWD ID Card, enter/confirm the number, and record the membership decision.
- Lookup creates no duplicate registration or Member. Completing approval still uses the existing permission-checked, stale-version-protected and audited workflow. Supplying a PWD number preserves the original online declaration and adds the existing correction/decision history. Existing decision/correction permissions are unchanged.

Done still revokes access to the private submitted form. Only the server-confirmed reference remains in the session; the QR contains no name, birthdate, contact details, PWD number, assessment fields, document URL, session token or access link. Posted references cannot select another person's receipt or final confirmation. Starting another registration clears the previous confirmation. No public lookup endpoint, account, migration, policy activation or application-data conversion was added.

## Validation

The initial isolated **116-test** run passed 115 checks. The new end-to-end assertion initially treated hidden version `0` as a missing user-entered field. After excluding hidden controls, a focused rerun reached approval and exposed a second assertion issue: the existing approval writer correctly regenerates printable labels/values when PWD No. changes. The assertion now compares every retained value except those regenerated print rows and checks the complete approved profile against its retained revision. No application guard was weakened. The final **four QR tests passed**; all 116 unique checks are covered across these runs.

```powershell
.venv\Scripts\python.exe -B .local\onsite-registration-20261026\run_tests.py test membership.test_registration_receipt_qr membership.test_registration_finish membership.test_pdf_registration membership.test_registration_intake membership.test_registration_prefill membership.test_registration_decisions membership.test_onsite_registration_alignment core.tests.test_short_references.ShortReferenceTests --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe -B .local\onsite-registration-20261026\run_tests.py test membership.test_registration_receipt_qr --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Each run used a new disposable native MySQL instance, separate grants/database/media, and disabled `.env` loading. Logs are under `.local/onsite-registration-20261026/temp/santolan-g12-tests-eoakcl2c/` (combined), `santolan-g12-tests-aw09i967/` (intermediate), and `santolan-g12-tests-t7ubeyhw/` (final).

Coverage includes actual PNG output and reference-only QR payload, matching reference/QR before and after Done, receipt ownership, unrelated-session denial, forged reference rejection, private-form revocation, confirmation clearing, unchanged short-reference lookup, every prefilled applicant field, PWD-only completion, original declaration preservation and one Member after explicit approval. Existing tests cover duplicate/concurrent decisions, stale requests, permissions, CSRF, expiry, attempt budgets, audit rollback and private attachments.

## Main development verification

The verified main site remains **http://127.0.0.1:8000/**, serving this checkout with `.local/ronnel-development-20261026/ronnel_settings.py`. Its existing server was successfully restarted using the corrected main-development helper.

- Main `check --database default` and migration drift checks passed. JavaScript syntax and `git diff --check` passed.
- A SQL guard rejecting writes verified both receipt templates and the required-PWD editor against existing retained data. The generated reference QR was inspected as a PNG with clear quiet margins. Helper: `.local/onsite-registration-20261026/validate_reference_main.py`.
- Authenticated HTTP on port 8000 loaded an existing online reference and verified all **29 applicant fields** against the retained revision, with PWD No. required. It also verified the public/onsite 30-field contract (including acknowledgement) and the existing EWAF breakdown. No application was submitted, saved or approved by the live checks; normal login/view audit and temporary session/context handling remain in effect.
- Browser visual/responsive and physical print-layout verification were not performed; browser processes remain unavailable in this environment. The print control has syntax-checked JavaScript and scoped print styles, not a claimed browser print pass.

No real applicant was approved by this work. No commit, push, database migration or hosted deployment was performed. Earlier membership/EWAF work and unrelated concurrent documentation edits remain intact.
