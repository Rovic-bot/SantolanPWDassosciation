# Direct volume controls on first setup — 27 October 2026

Completed the correction identified by the owner's screenshot. A fresh composite SES Vault page now opens the shared four-row volume editor directly. It no longer renders the four number-entry boxes or the separate **Adjust with volume sliders** step. The SES row describes the verified 4Ps adjustment.

An unconfigured editor has `proposal: null`, four visible range controls and **Not set** readouts. Moving the top slider creates the user's initial proposal, sharing the remainder equally among the lower rows with integer hundredths and the existing feasibility constraints. The second and third sliders then become adjustable. Subsequent changes reuse the existing proportional cascade: earlier weights stay fixed, lower weights absorb the change, and the total remains 100.00%. Priority arrows work before and after initial selection. The fourth remains the remainder and can be moved higher.

No equal-weight vector, example configuration or live weights are installed on page load. Nothing is calculated or saved until user interaction. Approval still requires an explicit saved draft and the existing server checks. Reset on a fresh editor clears the proposal and cancels its pending preview; reset on a saved editor restores that saved proposal. Unsaved weights remain editable after a rejected save. Historical signatures, existing bindings, scoring and approval services are unchanged; already-open legacy setup submissions remain compatible.

## Validation

- **90 Django tests passed in 112.633 seconds**, covering composite SES, income-only SES, document ranking and Vault operations. The first-visit regression now asserts the direct editor, absent number inputs/setup form, null proposal, required input before saving, read-only AHP preview, unsaved-approval rejection and explicit draft saving. These suites overlap prior runs and are not an additional disjoint coverage total.
- **2,500 cascade/reorder cases**, six exact cascade examples and new first-gesture/priority boundary checks passed. Three gestures selecting 50%, then 25%, then 15% produce 50/25/15/10 without typing percentage fields.
- The new DOM/event harness executes the production JavaScript and verifies four ranges on first load, no numeric controls or initialized vector, no automatic preview request, all four criterion identities, lower-row redistribution, priority changes before and after initialization, reset, draft gating and restoration after a failed save. It is a DOM simulation, not a browser layout or native keyboard test.
- Django system checks and `git diff --check` passed. No new browser launch was attempted after the earlier environment denial, and no screenshot of a running updated page is claimed.

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_composite_ses ewaf.test_ses_workflow ewaf.test_document_ranking ewaf.test_vault --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node scripts/ewaf_weight_slider_test.cjs
node scripts/ewaf_weight_editor_dom_test.cjs
git diff --check
```

The verified fresh MySQL instance used loopback port 55218, `test_g12_disposable`, UUID `4b878813-d177-11f1-a957-581122e63603`, isolated grants, disabled `.env` loading and synthetic media. Artifacts are under `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-ad3ff9em/`. Its schema was synchronized from models; no historical migrations were applied and no new migration is needed.

## Scope and local loading

Existing branch `ronnel-updates`, HEAD `805c059`. Source changes: `ewaf/vault_forms.py`, `ewaf/vault_views.py`, `static/js/ewaf-weights.js` and the Vault script cache version. Updated tests and the [current Admin guide](EWAF_Composite_SES_Configuration_and_Ranking.md). Preservation inventory: `.local/ewaf-direct-sliders-20261027/`. Earlier validation evidence and the accepted 70% milestone are retained.

No working database, approvals, credentials, startup guard, policy arithmetic, program schedule or activation flags were changed. No commit, push or deployment occurred. The existing server needs a local restart to load the new Python view. The previously denied process-stop action was not bypassed; the owner can use `scripts/restart-current-development.ps1` in their local PowerShell session.
