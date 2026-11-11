# Scoring explanation and calculation-guide tabs — 27 October 2026

Completed the requested private Admin tabs after generation of an EWAF ranking:

- **Scoring Explanation** reuses the existing saved-score breakdown service and route. Applicants' scores link directly to their explanation. It shows accepted raw/encoded inputs, normalization, weights, weighted points, exact-rank reasoning, ties and whole-pool comparisons. Each criterion now shows how many other applicants contributed more, equally or less, using exact retained contributions rather than rounded display values. It also displays the point multiplication with an approximation sign for rounded intermediate labels.
- **How Calculation Works** is a separate GET-only tab at the program's `calculation-guide/` route. It reuses the same authentication, run scope, integrity replay, freshness assessment and saved-data presentation. It explains the retained criterion signature, weight versions and exact coefficient strings, accepted-input basis, bounds, employment encoding, normalization, composite SES adjustment when applicable, final sum and exact competition ranking.

Both tab links appear once a saved run exists and carry the selected run ID. Applicant selection is retained when switching between them. Direct visits without a run explain that generation is required; they create no calculation. Old method definitions and original criteria remain explicit, including historical SI/ES/PA/ND and fixed configuration bounds. Income-only SES does not acquire the composite adjustment. No rank/score edits, automatic beneficiary selection, new classifications or public disclosures are introduced.

## Implementation and preservation

Source changes are limited to the read-only presentation helper `ewaf/score_breakdown.py`, the shared handler in `ewaf/operational_views.py`, the added named route in `ewaf/urls.py`, and the relevant templates. `templates/ewaf/calculation_context.html` shares the saved-run selector and freshness notice between both pages. `templates/ewaf/calculation_guide.html` provides the separate guide. Existing program tabs and result links expose the two pages after generation. Top-level Admin groups are unchanged.

Criterion comparisons use counters over the complete retained calculation and exact `Fraction` values, with sorted cumulative counts; filters and pagination do not narrow the comparison pool. Historical display placeholders are not treated as included factors in the guide. No calculation engine, scoring direction, weight projection, policy approval, accepted-evidence service, selection service or release/publication projection changed.

The work remains in the existing `ronnel-updates` worktree at HEAD `805c059`. Source-preservation hashes and the change inventory are under `.local/ewaf-scoring-tabs-20261027/`. Prior validation evidence, unfinished unrelated work and the owner's accepted 70% milestone remain intact. No migration, working-database update, institutional approval, activation, commit, push or deployment occurred.

## Validation

**116 tests passed in 212.134 seconds** in one combined isolated run:

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_score_breakdown ewaf.test_composite_ses ewaf.test_ses_workflow ewaf.test_dataset_policy ewaf.test_household_criteria ewaf.test_operational --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
git diff --check
```

Coverage includes an actual synthetic HTTP generation action followed by both tabs; four composite contributions and the exact 90/10 formula; employment codes; input/weight/bound explanations; identical rounded contribution labels with different exact comparisons; zero/equal contributions; historical criterion sets and configured bounds; old/stale snapshots; authentication and private permissions; GET-only behavior; invalid/cross-program run and applicant identifiers; no-store responses; and rejection of tampered saved calculations. GET inspection preserves the run payload and run, decision and audit counts. The suite also replays existing arithmetic, policy, evidence, ranking and human-decision regressions. These checks overlap previous test reports; they are not an additional disjoint coverage total.

The fresh disposable MySQL instance used port **61776**, database `test_g12_disposable`, UUID `bb541f7c-d17a-11f1-bbeb-581122e63603`, isolated grants, disabled `.env` loading and synthetic private media. Logs are under `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-_o2d1wj9/`. Its schema was synchronized from models; historical migrations were blocked. Django system checks and whitespace validation passed.

No browser layout or screenshot pass is claimed. Validation used real Django responses and the private service path in disposable MySQL. The running local server needs a restart to load the new route and handler; the earlier Windows process-stop denial was not bypassed. The existing `scripts/restart-current-development.ps1` is the owner's local restart entry point.
