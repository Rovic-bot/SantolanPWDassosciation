# One-click program publication — 27 October 2026

Implemented the owner's instruction to publish a program with one click and no separately entered reason. This supersedes the separate draft-policy authorization step in the program publication UI. It does not supply missing external approvals, program details, EWAF weights or scoring-policy decisions.

## Behavior

The program review page has a direct **Publish** button. Its form contains the CSRF token and current record version, with no reason field or confirmation checkbox. A draft no longer offers **Authorize program policy** as a prerequisite. Other status changes remain in a separate collapsed section with their existing controls; already-published legacy programs retain their authorization-recovery procedure.

`change_publication` records missing program-policy authorization and publication in the same transaction. It records the actor, time and automatic audit descriptions, and increments the program version once. Existing authorization records are retained in the current workflow. A failure in external approval, required details, Vault readiness or the publication audit rolls the transaction back, including any newly recorded authorization or shared configuration.

The normal permissions, CSRF protection, version check, installation-wide terms lock, required external approvals, application schedules and protected history remain. Approved Vault weights can support publication while scoring rules are pending. A complete approved shared policy can be bound during the same Publish action. No per-program EWAF configuration, eligibility decision, ranking, beneficiary selection, delivery or public-results disclosure is invented by publication.

## Files

- `programs/forms.py`: dedicated Publish form.
- `programs/views.py`: direct Publish handling and draft authorization-menu removal.
- `programs/services.py`: atomic authorization/publication and automatic publication audit description.
- `templates/programs/manage_detail.html`: single Publish button and updated instructions.
- `programs/test_one_click_publication.py`: new synthetic integration, rollback, permission and concurrency tests.
- `programs/test_application_workflow.py`, `ewaf/test_vault.py`: update former two-step expectations to the owner-authorized behavior.
- `docs/EWAF_Composite_SES_Configuration_and_Ranking.md`: current Admin sequence.

This checkout remains on `ronnel-updates` at `805c059`; unrelated existing changes and dated validation evidence are preserved. The owner-defined 70% milestone is unchanged.

## Validation

**84 tests passed in 70.253 seconds**, with no failures, using:

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test programs.test_one_click_publication programs.test_application_workflow programs.test_policy_authorization ewaf.test_vault ewaf.test_intake_policy ewaf.test_shared_application --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The runner verified a fresh disposable MySQL instance, `.env` disabled, synthetic private media and isolated grants. Evidence is under `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-dss79d24/`; port 65389, UUID `017e9587-d184-11f1-828b-581122e63603`. The established model-synchronized baseline was used. No schema change or migration was needed.

Coverage includes a POST containing only Publish and the current version, retained audits, absent reason/confirmation/authorization controls in the draft Publish flow, duplicate and concurrent publication, missing details, missing external approval, rollback after missing Vault approval or audit failure, permissions and CSRF, weights-only intake, and complete shared-policy binding in one publication transaction. Preserved legacy authorization-recovery tests also passed.

A separate read-only probe rendered an existing development draft through the updated view with HTTP 200 and verified exactly one Publish button and no reason or confirmation field in its form. Its database execution wrapper rejects mutation statements. Django configuration checks, migration-drift checks and `git diff --check` passed. Probe: `.local/one-click-publication-20261027/check.py`. No live program was published or authorized, and no working database writes, activation, commit, push or deployment were performed.

## Running server

The port-8000 check still identifies PID 14672, whose restart was denied by Windows in the preceding task. The same denied process-control operation was not retried or bypassed. Source and template validation passed, but the running Python process must be restarted from the user's terminal to load the new handler:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/restart-current-development.ps1
```

No visual browser pass or successful live-server reload is claimed.
