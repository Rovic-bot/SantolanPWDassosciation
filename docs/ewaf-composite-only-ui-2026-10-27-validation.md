# Composite SES configuration navigation — 27 October 2026

Completed the owner's request to remove the HI/SI and income-only SES method tabs from the Configuration Vault and calculation-rule editor. Both routes now open **SES / ES / PA / HM — income-based SES with a verified 4Ps adjustment** by default. The displayed formula uses multiplication signs correctly.

The existing volume-style cascading editor and priority arrows are reused for SES, ES, PA and HM. Matching saved proposals reopen automatically. When none exists, the Admin chooses four percentages totaling 100% and saves an unapproved draft, then adjusts/reviews them through the existing sliders and AHP preview. Approval remains separate. No five-criterion weights or example coefficients were copied into a new configuration.

The main weights remain editable; the internal SES rule remains `I * (9/10 + (1/10)*P)`. This change does not modify calculation engines, slider arithmetic, evidence services, policy approval requirements, program bindings or database records. Explicit historical method URLs and already-open forms still resolve their original method. Historical records remain available with their original signatures; the removed tabs are no longer offered in navigation.

## Checkout and changes

Existing branch `ronnel-updates`, HEAD `805c059`, same worktree. Source changes are limited to `ewaf/vault_views.py`, `ewaf/revised/live_views.py`, `templates/ewaf/vault.html` and `templates/ewaf/revised/policies.html`.

Updated composite integration coverage and adjusted historical UI tests to request their historical method explicitly in `ewaf/test_composite_ses.py`, `ewaf/test_document_ranking.py`, `ewaf/test_intake_policy.py` and `ewaf/test_vault.py`. Updated the [current Admin guide](EWAF_Composite_SES_Configuration_and_Ranking.md). Prior validation evidence and the owner's 70% milestone are unchanged.

## Validation

- **122 Django tests passed** in 162.619 seconds: composite SES, income-only SES, dataset policies, document ranking, publication/intake and Vault suites. This is one combined run; those overlapping subsystem checks are not counted again as separate totals.
- The default-route tests verify composite method identity, removal of method navigation, restoration of four saved weights, fixed internal formula, reordered main weights, immutable bindings and retained historical weight payloads.
- The first-setup test verifies blank four-criterion inputs, rejection of immediate approval, saving an explicitly chosen synthetic draft, and opening the existing slider editor without creating an approved configuration.
- **2,500 Node cascade/reorder cases passed** across SES and both historical signatures. They check totals, earlier-weight preservation, code association, all criterion priority positions and Saaty limits.
- `git diff --check` passed; only existing line-ending conversion notices were printed. Django reported no system-check issues.
- Browser interactions were not rerun in this change. UI verification used rendered Django responses and the existing JavaScript algorithm harness.

Command:

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_composite_ses ewaf.test_ses_workflow ewaf.test_dataset_policy ewaf.test_document_ranking ewaf.test_intake_policy ewaf.test_vault --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node scripts/ewaf_weight_slider_test.cjs
git diff --check
```

The fresh disposable MySQL instance used loopback port **52251**, database `test_g12_disposable`, UUID `66ad887e-d173-11f1-88d1-581122e63603`, synthetic private media, disabled `.env` loading and isolated grants. Logs are under `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-_4ot6peq/`. Its schema was synchronized from models; historical migrations were blocked by the test runner. No migration is proposed or applied by this UI change.

The task's source-preservation baseline and change inventory are in `.local/ewaf-composite-only-ui-20261027/`. No working/production database, credentials, startup guard, approval record, activation flag or program schedule was changed. No commit, push or deployment occurred.

## Local display and operation

Open **EWAF Configuration Vault** from the sidebar to reach the current method directly. The existing local server runs without automatic reload and requires a restart to load the view changes. The earlier restart attempt was denied by Windows when stopping that process; this change does not bypass that restriction.

Institutional policy approval, selected and approved main weights, accepted evidence, immutable program binding and separately authorized activation remain prerequisites for real scoring.
