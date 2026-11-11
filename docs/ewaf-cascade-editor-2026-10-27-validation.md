# Cascading volume editor — 27 October 2026

Completed the requested first/second/third slider behavior in the existing four-criterion Configuration Vault UI. The established cascade arithmetic already supported proportional redistribution; this change exposes the editor before a first draft is saved and explains the movement of the affected rows.

In priority order:

- Increasing the first weight reduces the second, third and fourth proportionally; decreasing it increases them.
- Changing the second adjusts the third and fourth, keeping the first fixed.
- Changing the third adjusts only the fourth, keeping the first two fixed.
- The fourth receives the remainder. Priority arrows can move any criterion higher for direct adjustment.

The combined proposed total stays exactly 100.00%. The full 0–100% visual range, 0.01-point increments, positive weights, non-increasing priority, 9:1 limit and server-side AHP validation remain unchanged. At a priority limit the editor now explains how to create room by changing an earlier weight or moving the criterion higher. These are proposed weights; the approved calculated AHP weights still control scoring.

When no matching proposal exists, staff choose four starting percentages and select **Adjust with volume sliders**. This read-only action validates the values and current Vault token, then opens the existing editor without creating a draft, audit approval, or configuration. The explanation is optional for opening the controls, required when saving. Invalid saves retain the unsaved slider proposal. Approval still requires a saved, unchanged reviewed draft. No default weights, five-to-four conversion or change to the internal SES coefficients was introduced.

## Files and preservation

Changed `ewaf/vault_forms.py`, `ewaf/vault_views.py`, `templates/ewaf/vault.html`, `templates/ewaf/weight_editor.html` and the row guidance in `static/js/ewaf-weights.js`. Updated `ewaf/test_composite_ses.py`, `scripts/ewaf_weight_slider_test.cjs` and the [current guide](EWAF_Composite_SES_Configuration_and_Ranking.md).

Existing branch `ronnel-updates`, HEAD `805c059`, same worktree. The task's file-hash baseline and change inventory are under `.local/ewaf-cascade-ui-20261027/`. Earlier evidence, unrelated unfinished work and the owner's accepted 70% milestone are preserved. No calculation engine, policy service, schema, stored history, working database, startup guard, credential, activation flag or program schedule was changed. No commit, push, merge or deployment occurred.

## Validation

**90 Django tests passed in 129.111 seconds**, covering composite SES, preserved income-only SES, document ranking and Vault behavior. The updated setup test checks read-only opening without a reason, unchanged revision/audit counts, editable recovery from a missing save reason, refusal to approve an unsaved proposal, and subsequent draft saving. An additional test rejects stale tokens, incomplete values, incorrect totals, ratios over 9:1 and unauthorized staff. Historical calculations, approval gates and scoring integration also pass in these suites.

**2,500 existing Node cascade/reorder cases and six exact SES examples passed.** The examples independently check both directions for each of the first three sliders. From a synthetic 50/25/15/10 proposal, a third weight of 17 gives 50/25/17/8, and a third weight of 12.5 gives 50/25/12.5/12.5. These vectors are test data only.

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_composite_ses ewaf.test_ses_workflow ewaf.test_document_ranking ewaf.test_vault --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node scripts/ewaf_weight_slider_test.cjs
git diff --check
```

The verified fresh MySQL instance used loopback port 61376, database `test_g12_disposable`, UUID `52e11817-d175-11f1-9b23-581122e63603`, isolated grants and synthetic private media. `.env` loading was disabled. Logs are under `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-hr55p8dp/`. The disposable schema was synchronized from models; no historical migrations were applied. Django system checks and the whitespace check passed.

These 90 tests overlap the earlier validation runs; they are not an additional disjoint coverage total. Browser interactions were not rerun: validation used Django-rendered forms and the JavaScript cascade harness. The existing server runs without automatic reload and needs a local restart to load the view changes. The prior Windows process-stop denial was not bypassed.
