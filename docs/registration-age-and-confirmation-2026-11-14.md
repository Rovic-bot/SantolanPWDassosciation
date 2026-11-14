# Registration age rules and PDAO confirmation — November 14, 2026

The owner requested age-appropriate education/employment choices, required family background, and a confirmation before marking a PDAO application ready. The owner explicitly selected: **“For all children under 15: education up to elementary; Student or Unemployed only.”** This is the application policy authorized for this release, not a claim about statutory employment or education rules. Baseline: deployment branch commit `6ff0fa5`, following the [address and required-field release](registration-validation-2026-11-14.md).

## Behavior

- All four new-intake forms (public/onsite Association and public/onsite PDAO) calculate age from the birth date. Ages 5–14 can select None / Not yet in school, Kindergarten or Elementary, and Student or Unemployed. The existing minimum age of five remains enforced. Full choices return on the fifteenth birthday.
- Changing birth date immediately filters the dropdowns. Incompatible previously selected choices are cleared and require a new selection. A status is not silently assigned. PDAO employment details are cleared/disabled for children under 15. Server validation independently rejects disallowed choices and child employment details, including manually altered or JavaScript-free submissions.
- PDAO Family Background requires both parents’ given and family names. Middle names are labeled “if any” and remain optional. Association family-count, 4Ps answer and conditional guardian/spouse requirements remain in force.
- Association review forms retain the new None/Kindergarten choices; PDAO review and print forms retain Student. This allows staff to reopen new child applications without dropping their saved values. Existing records and historical dates are not rewritten or subjected to retroactive age filtering.
- PDAO **Mark ready to forward** opens a confirmation for both online and onsite records. Cancel/Escape leave the application unchanged. The popup identifies the status change and whether an online office-verification invitation is queued. It does not record actual forwarding or issue an ID. The existing manual PRPWD check, permissions, stale-version controls, audit transaction and separate actual-forwarding confirmation remain intact.
- The server requires an explicit ready confirmation. A visible checkbox provides the no-JavaScript fallback. Keyboard focus starts on Cancel and returns to the initiating button when canceled. Rapid double confirmation submits once.

No models, migrations, account creation, score/rank rules, document requirements, storage settings or service plans change.

## Validation

- **92 focused Django tests passed** on fresh disposable MySQL with `.env` disabled, isolated test database grants, fictional records/private media and in-memory email. Coverage includes intake, permissions, CSRF, audit rollback, stale/concurrent transitions, unchanged original submissions, required ready confirmation and no side effects when confirmation is absent.
- **17 database-free rule/template tests passed** on the final code, including all four forms, ages 5/10/14, the exact fifteenth birthday, forged education/employment values, required parents’ names and reopening saved child choices in staff review.
- **Six read-only Chrome scenarios passed** across all four actual intake templates at 1440/390/320 px, including dynamic age filtering, selection clearing/restoration, required family fields, previous address/mobile/date rules, address-download failure and JavaScript-free fallback. Zero application POSTs and JavaScript errors.
- **Two browser suites passed** using disposable records: online/onsite ready dialogs (Cancel, Escape, Enter, focus, small screens, duplicate-click prevention and checkbox fallback), manual PRPWD gating, two captured online notices, onsite no-email behavior, private receipts/printing and access revocation; plus actual PDAO print layout for filled/minimal/Student/long-text fixtures. Filled/minimal/Student forms remain two A4 pages. The existing extreme long-text fixture spans four pages.
- Screenshots of child options, mobile/desktop confirmations and the checked Student print option were inspected. Django checks, migration drift detection, JavaScript syntax and `git diff --check` passed.

The initial browser attempt exposed stale print-control/inline-receipt expectations and sampled a theme transition before it finished. The harness now uses the current preview controls, tests the authenticated receipt through its live iframe route, and waits for finite theme transitions before checking contrast. No product behavior was weakened to satisfy those checks.

Evidence: [intake browser results](registration-age-and-confirmation-2026-11-14/intake-browser.json), [child PDAO choices](registration-age-and-confirmation-2026-11-14/child-pdao.png), [online confirmation on mobile](registration-age-and-confirmation-2026-11-14/ready-online-mobile.png), [onsite confirmation](registration-age-and-confirmation-2026-11-14/ready-onsite.png), [Student print page](registration-age-and-confirmation-2026-11-14/student-print.png).

## Activation

Render deploy `dep-dbs3dtgae00c73digh70` reached **live** on November 14, 2026 at **10:26:31 UTC / 6:26:31 PM Philippine time**, running commit `453a085c5cd45e2cc8095b7c0b69499dfadb1229` on the existing [hosted system](https://santolan-pwd-system.onrender.com).

Four hosted Chrome scenarios passed: both public forms with age/choice/family/address/mobile checks at 1440/390/320 px, unavailable address suggestions, and the no-JavaScript fallback. No JavaScript errors or application POSTs occurred. The hosted child PDAO screenshot was inspected. The health endpoint returned HTTP 200 with `status: ok`; both changed JavaScript assets matched the committed release bytes. Render returned no application error logs from activation through 10:27:49 UTC.

The scoped changes were also applied to the main workspace, preserving its unrelated work and existing source-form layout. Its 17 database-free checks passed. Staff transitions were tested with disposable records and in-memory email, without changing real applicants or sending production notices. The service remains on its existing Free plan with automatic deployment off.

Hosted evidence: [browser results](registration-age-and-confirmation-2026-11-14/hosted-browser.json), [child PDAO options](registration-age-and-confirmation-2026-11-14/hosted-child-pdao.png), [health and committed-asset checks](registration-age-and-confirmation-2026-11-14/hosted-assets.json). This activation evidence is a documentation-only follow-up and does not require another deployment.
