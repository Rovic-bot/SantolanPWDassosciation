# Household Members scoring — November 11, 2026

The owner explicitly requested that one household member score zero, with the largest household in a program receiving the maximum HM score. The smallest applicant household must not automatically score zero when it contains more than one member. This instruction authorizes the HM normalization change for new current composite SES / ES / PA / HM rankings; it is not evidence of separate institutional policy approval.

## Implemented rule

Let H be the accepted household member count and M the largest accepted count in that program's eligible scoring pool:

- When M > 1, normalized HM = (H − 1) / (M − 1).
- When M = 1, normalized HM = 0 for every applicant. This avoids division by zero and preserves the explicit one-member zero point.
- Equal counts greater than one receive normalized HM = 1.
- Contribution to the total = normalized HM × retained HM weight × 100 points.

For M = 5, H = 1 scores 0, H = 4 scores 3/4, and H = 5 scores 1. With an HM weight of 20%, those contributions are 0, 15 and 20 points. A pool containing only households of 4 and 5 therefore assigns 15 HM points to the household of 4 at that weight.

The existing eligible-pool boundary is retained: pending and ineligible applications do not establish M. Missing, invalid or nonintegral counts are rejected. Other criterion formulas, weights, eligibility, exact ranking, boundary ties and human selection controls are unchanged.

## Versioning and presentation

`ewaf/household_scoring.py` defines `household-members-fixed-one-2026-11-11-v1`. `operational_services.capture` freezes its complete definition in each new composite run's `household_scoring` snapshot. The calculation preserves the observed pool minimum separately from `normalization_minimum = 1` and records the rule version in the HM trace.

`ewaf/revised/live_math.py` uses exact fractions and the saved rule. A snapshot without this marker replays the original pool-minimum and equal-value behavior. Existing fixed-policy definitions, bindings, old calculations and their audit records are not rewritten. Historical methods outside the current composite workflow remain unchanged.

The score breakdown uses the retained normalization baseline and explains the one-person special case. Old snapshots continue to show their original formulas. Stale generation tokens are rejected; further decisions and publication require a ranking generated with the current rule. No live member records were read or recalculated during this implementation.

Operators apply the change to an existing program using **Generate EWAF Ranking**. This creates a new audited calculation; prior snapshots remain available. Beneficiary selection remains a separate human action.

## Validation

**38 distinct focused tests passed across the final targeted runs**, on fresh disposable native MySQL databases using the G12 launcher and `scripts.email_test_runner.EmailTestRunner`. External Python socket connections were blocked; project `.env` was disabled. The launcher verified the isolated datadir and database identity. No application database migration or real email delivery was performed.

Coverage includes the 4/5 example, a one-person baseline, program-specific maxima, changing maxima, equal and singleton pools, invalid inputs, exact weighted contributions, unchanged non-HM formulas, preserved old-run replay, changed-rule tokens/selection/publication guards, pending-pool exclusion, displayed formulas, exact boundary ties, existing employment permissions and audit rollback, and historical score explanations.

The initial runs exposed outdated fixtures: shared-policy tests attempted to replace the newer fixed binding, a historical presentation fixture lacked the current method property, and an old UI expectation referenced a removed rubric list. The new workflow fixture also needed a synthetic clock within the fixed policy's effective period and before the retained audit timestamp. Only fixture setup and obsolete display assertions were corrected; production policy, permission and audit controls were preserved. This is not a claim that the full repository test suite passes.

Reproduce the selected checks from the repository root:

```powershell
.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_household_scoring.HouseholdScoringArithmeticTests ewaf.test_household_scoring.HouseholdScoringWorkflowTests ewaf.test_employment_scoring.EmploymentScoringTests ewaf.test_composite_ses.CompositeSesArithmeticTests ewaf.test_shared_calculation_rules.FullCreditArithmeticTests ewaf.test_score_breakdown.ScoreBreakdownPresentationTests ewaf.test_fixed_scoring.FixedScoringDefinitionTests --testrunner=scripts.email_test_runner.EmailTestRunner --noinput --verbosity 1
```

Django's system check, Python syntax checks and `git diff --check` passed. No schema change is required. The verified local development server was restarted successfully after validation.
