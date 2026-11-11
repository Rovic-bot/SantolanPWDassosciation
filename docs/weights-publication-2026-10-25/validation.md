# Approved weights permit publication and scheduled applications

Owner decision: **“Yes—allow publication and applications with approved weights.”** This supersedes the earlier requirement to finish scoring-policy approval before publication/application opening. It does not authorize calculation, ranking, selection, release or scoring-rule adoption.

## Behavior

The existing approved and locked Vault version assigned to the program now satisfies the EWAF prerequisite for publication. The normal publication action retains that exact version and an audited snapshot of the authorized program terms. It creates no new weight approval and keeps the numerical scoring configuration pending.

Verified members may apply only during the original approved opening/closing schedule. Existing membership verification, program authorization, external approval, photo/evidence requirements, stale-request protection and audits remain enforced. Missing, unapproved or invalid weight configurations still block intake. Later Vault changes do not replace the program's retained weights.

Calculation and human beneficiary decisions still require a complete approved scoring policy and accepted evidence. The existing calculation validator remains unchanged. In the source integration, a published weights-only intake may explicitly receive its first approved dataset policy using the same exact weight version. Historical scored programs cannot use this transition, and no automatic policy binding occurs.

## Files

- `ewaf/intake_policy.py`: separate intake validation and audited retention of existing approved weights/terms.
- `ewaf/vault_services.py`: publication dispatch for weights-only configurations.
- `programs/application_workflow.py`: publication and scheduled membership-verified intake use the new check.
- `ewaf/vault_policy.py`, `ewaf/program_cards.py`, and the Vault/program review templates: explain publication readiness separately from scoring readiness.
- `ewaf/revised/live_services.py` and its binding template: explicit first-policy handoff for recognized weights-only intakes; unchanged weight-version requirement.
- `ewaf/test_intake_policy.py`, `ewaf/test_vault.py`, `ewaf/test_dataset_policy.py`: revised acceptance and regression coverage.

No model or migration change was needed for this publication fix. The earlier proposed dataset-policy migration remains unapplied in the running environment.

## Tests actually run

The final **201-test suite passed in 155.155 seconds** using a fresh isolated native MySQL 8.4.11 server, `.env` disabled, separate grants/datadir and `test_g12_disposable`. Test labels: `ewaf.test_intake_policy`, `ewaf.test_dataset_policy`, `ewaf.test_operational`, `ewaf.test_delivery`, `ewaf.test_vault`, `ewaf.test_household_criteria`, all four revised math/policy/guard/preview suites, `programs.test_application_workflow`, `announcements.test_results`, and `announcements.test_public_results`.

Command prefix: `.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test`; runner: `scripts.dataset_policy_test_runner.DatasetPolicyTestRunner --noinput --verbosity 1`.

Artifacts: `.local/dual-registration-20261024/temp/santolan-g12-tests-qlawuedk`. Django system checks and `git diff --check` passed. An initial new-fixture failure was corrected by refreshing the synthetic member's persisted birthdate before identity comparison; no verification control was weakened.

Coverage includes actual scheduled application submission, duplicate-reference preservation, early/late refusal, exact weight version retention, publication permissions, approved terms, stale requests, audit rollback, blocked scoring/selection/releases, new-policy handoff and historical/publication regressions.

## Local website verification and remaining restart step

Seven narrow runtime file changes were installed into the existing ignored local development clone, with original-file backups and checked hashes. No models, environment settings or database migrations were installed. The new scoring-policy workflow remains disabled.

A fresh-process **read-only transaction** checked both existing weights-only draft programs: both pass EWAF publication readiness, both already have recorded program authorization, both render the corrected review page, and both remain blocked for scoring. No live publication POST was issued.

Before/after fingerprints matched for all eight inspected tables: programs, applications, program audits, Vault revisions, operational configurations, runs, decisions and migration history. No program was published, no schedule changed and no approval was created by this work. No commit, push or remote deployment occurred.

Windows returned **Access is denied** when stopping the existing Python listener on port 8003. The installed fix therefore requires the user to run `Restart System.cmd`, then refresh the program page and use the normal publication action. This is an operating-system process-permission limitation, not an automatic approval-review rejection.

Runtime evidence/backups: `.local/weights-publication-20261025/` (`runtime-plan.json`, `runtime-verification.json`, database fingerprints and restart logs). Visual browser QA was not performed.
