# Employment scoring — November 10, 2026

The owner explicitly replaced the employment rubric with Employed=1, Self-Employed=2, Student=3, Retired=4 and Unemployed=5. This instruction supersedes the earlier four-category employment encoding for new operational dataset rankings. Other criteria, weights, normalization, constant-column rules, eligibility and human selection remain unchanged.

## Behaviour

`ewaf/employment_scoring.py` defines the five-category rule and the exact mapping from the existing member-record identifiers. Every new dataset ranking freezes `employment_scoring` with version `member-employment-five-categories-2026-11-10` and its scores in the protected run snapshot. The existing calculation audit retains that snapshot. No saved policy, binding, member record, score, rank, selection, release or published result was edited or regenerated during implementation.

Automatic member-record rankings use the five-category mapping through a temporary runtime configuration. The persisted binding is unchanged. New policy forms display the fixed mappings; manual review forms offer the five categories. Missing/unrecognized statuses block calculation. Manually reviewed inputs still containing Full-Time/Part-Time/Seasonal categories require renewed review using the five supported statuses before a new ranking; they are not silently recategorized.

The ES calculation continues to use `(raw - pool_min) / (pool_max - pool_min)`, followed by the existing approved employment weight. A pool containing all five categories produces normalized ES values 0, 0.25, 0.5, 0.75 and 1. Pools with a narrower range use their own minimum/maximum. The retained policy's equal-value rule still governs constant columns.

Historical runs without the marker replay the original encoding from `ewaf/revised/engine.py`. Their calculation guide also shows that original encoding. Existing ranking tokens become stale when the scoring rule changes; further decisions/publication require a new current ranking. Historical source documents and their sealed policy descriptions remain intact; the editor explains that the new employment rubric supersedes those earlier employment categories.

## Validation

- **30 focused tests passed** in a fresh disposable MySQL database using `RegistrationIntakeTestRunner`: `ewaf.test_employment_scoring.EmploymentScoringTests`, `ewaf.test_composite_ses.CompositeSesArithmeticTests`, and `ewaf.test_revised_policy`.
- Tests cover all five actual generated raw scores, exact normalized and weighted contributions, ranking order, unchanged bindings, retained-run replay, stale generation/decision guards, tampered scoring snapshots, unknown employment, fixed policy fields, manual review choices/input derivation, permissions and audit rollback. Historical arithmetic and sealed source-policy tests pass unchanged.
- A read-only connection to the retained local database successfully replayed **all 53 saved OperationalRun records**, with zero errors. No writes were performed in this check.
- The EWAF workspace HTTP response displays the five scores, including Self-Employed, Student and Retired.
- Django system check and `git diff --check` passed. No migration is required.

An earlier broader run of `AutomaticMemberInputsTests` plus the first three new tests ran 11 tests, with 6 passing and 5 setup errors. The five errors originate in the existing prior-release fixture, which creates a non-EWAF program and attempts eligibility review; the earlier mandatory-EWAF change rejects that setup before scoring. Those unrelated controls were preserved. The focused suite above separately covers this change's actual generation, permissions, rollback and historical replay; this report does not claim the entire application suite passes.

Reproduce the focused suite:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_employment_scoring.EmploymentScoringTests ewaf.test_composite_ses.CompositeSesArithmeticTests ewaf.test_revised_policy --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

The local development server was restarted after verification. Administrators generate a new ranking to apply this rubric to an existing program; this implementation did not run calculations or make beneficiary decisions on real records.
