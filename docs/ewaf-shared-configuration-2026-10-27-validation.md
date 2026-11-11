# EWAF page error and shared program configuration — 27 October 2026

## Status and checkout

**Implementation and applicable validation: completed. Loading the changes into the running port-8000 server: blocked by Windows process permissions.**

Checkout: `C:\Users\rovic\Documents\Capstone System\System Vault\santolan-pwd-system`, branch `ronnel-updates`, HEAD `805c059`. Existing unfinished work and prior development evidence were preserved. No commit, push, merge, deployment, institutional approval, real scoring activation or working-database migration was performed. The owner-defined 70% milestone is unchanged.

## Reported page error

The private program page `/ewaf/programs/43957a4f-08ad-4dd0-8662-a4084a5b4659/` was reproduced using the pinned development settings and a database execution wrapper that rejects mutation statements. The latest historical calculation calls `run.clean()`, which rejects missing historical PR functional-need, consent and accessible-alternative definitions. The workspace previously let that `ValidationError` escape as a server error.

The workspace now renders a **Saved calculation needs review** notice. Invalid retained scores and beneficiary-decision controls are not displayed. Private export fails closed with HTTP 409 instead of crashing. Scoring Explanation and How Calculation Works retain their existing integrity guards. Previous configurations and runs are not rewritten or recalculated.

The reported page returned HTTP 200 through the updated Django view against the development records. This is a read-only authenticated view render, not a claim that the old running process loaded the new Python code or that visual browser checks passed.

## Shared configuration behavior

- Weight approval automatically attaches the exact approved Vault version to new programs and appends updated inheritance for matching, unstarted weights-only drafts. Prior revisions remain intact. Opened intakes, other method signatures and existing scoring bindings retain their versions.
- The existing central calculation-rule editor now includes a **Shared assessment cutoff rule**. An administrator explicitly chooses application closing time or a fixed timezone-aware cutoff once. No approved choice or institution-specific cutoff is seeded.
- The existing `SharedDatasetPolicy.content` stores the optional, versioned `shared-program-application-v1` rule. Group C approval explicitly covers automatic application and its cutoff. Historical policy payloads without this rule keep their original contract.
- Central approval applies the exact policy and weight version to ready matching programs. New programs apply it during ordinary authorization/publication. The central **Apply shared configuration to ready programs** action supports a future effective date or later completion of program prerequisites. There is no second EWAF weight/policy-entry form on the program workspace.
- Automatic application requires the same method and retained weight version, complete approved policy, valid program authorization, compatible cutoff and current source context. Unknown rules and missing evidence remain blockers. The feature/schema guards and separately controlled scoring activation remain in force.
- A publisher can apply an already centrally approved configuration without re-approving EWAF. Central approval/application requires the appropriate EWAF and program-publication permissions. Existing terms locks, immutable records and audits are reused; audit failure rolls the operation back.
- An unopened draft with changed approved terms can append the **same** shared policy against its final terms before publication. Active programs, existing calculations, and the choice of weights/method are not silently rebound.
- Approved weights still permit normal publication/intake while scoring rules are pending. The workspace labels this **Weights approved; scoring pending**, directs missing rule decisions to the Vault, and hides the inappropriate older registered-input review link until its workflow is applicable.

Composite SES mathematics, slider projection, exact coefficient storage, accepted-evidence rules, four contributions, exact-score ties, human decisions, release and public-result restrictions are unchanged. The automatic-binding journey was tested through accepted inputs, calculation, ranking and human selection. Its SES contribution is checked as an exact fraction, not only a rounded total.

## Files amended for this request

- Services and validation: `ewaf/operational_views.py`, `ewaf/vault_services.py`, `ewaf/revised/contracts.py`, `ewaf/revised/live_services.py`, new `ewaf/revised/shared_application.py`, `programs/services.py`.
- Forms and request handling: `ewaf/revised/live_forms.py`, `ewaf/revised/live_views.py`.
- Existing UI: `templates/ewaf/operational_workspace.html`, `templates/ewaf/vault.html`, `templates/ewaf/revised/policies.html`, `templates/ewaf/revised/policy_review.html`.
- Validation: new `ewaf/test_shared_application.py`, changes to `ewaf/test_score_breakdown.py`, `ewaf/test_composite_ses.py`, `ewaf/test_ses_workflow.py`.
- Documentation: this record and `EWAF_Composite_SES_Configuration_and_Ranking.md`.

These files include pre-existing uncommitted implementation; the list does not claim this request authored all of their current Git diff.

## Test evidence and limitations

All database tests used the existing disposable-MySQL runner with `.env` disabled, a fresh loopback datadir/UUID/port, restricted synthetic database grants, InnoDB tables and synthetic private media. The command prefix was:

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test <labels> --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Logs are retained under `.local/ewaf-score-breakdown-20261026/temp/`:

| Run directory suffix | Scope | Result |
|---|---|---|
| `9f22kvx9` | Initial shared-application and breakdown run; included imported composite tests | 37 tests: 35 passed, one stale-draft binding error and one old form-fixture failure. Both corrected. |
| `frqvdkmy` | Shared application, breakdown, composite SES, income-only SES, dataset policy, Vault, intake and operational modules | 147 tests: 146 passed; one income-only HTTP form fixture omitted the new explicit cutoff choice. Corrected and retested below. |
| `44iw98zh` | Program application workflow and approved terms | 67 tests: 66 passed; one historical migration replay was blocked by the runner's `PermissionDenied: Blanket/historical migration execution is forbidden.` The guard was not weakened. |
| `zod11wb_` | Shared application, the corrected composite HTTP case, invalid-run guard, application workflow and approved-term non-migration/concurrency classes | **81 passed**, 58.422 seconds. |
| `hb5s8697` | Final shared-application suite and corrected income-only HTTP policy form | **14 passed**, 28.877 seconds. |

There are **214 distinct applicable test cases with passing results across these runs**; overlapping reruns are not added to that count. The final runs have no failures. One separate historical migration-replay case remains unexecuted because the disposable runner deliberately forbids it. This is not a claim that a single 214-test command was run or that the historical migration test passed.

The shared tests cover bulk and new-program application, exact method/weight matching, publication before scoring readiness, fixed/closing cutoff rules, future effectivity, disabled flags/unavailable schema, missing or malformed shared choices, unchanged historical policies, ordinary publisher permissions, stale approval requests, idempotency, append-only inheritance, atomic rollback after a partial bulk operation, and the stored-policy-to-human-decision journey. Existing suites cover preserved scoring and operational behavior.

`manage.py check --database default`, `makemigrations --check --dry-run` through the read-only pinned probe, and `git diff --check` passed. No model changes or schema migrations were required. Actual EWAF leaf `0012_dataset_policy_integration` is already applied; it was not replayed. Test databases used the established model-synchronized baseline, not a migration rehearsal.

The read-only inventory covers 95 development tables. EWAF, programs, assistance, evidence, audits and migration records matched their initial hashes. The only observed external difference was two additional `membership_registrationsubmissioncontext` rows while the development system was in use; the probe rejects writes and did not create these. Do not describe the whole database as unchanged. Probe and restart evidence is in `.local/ewaf-shared-config-20261027/`.

## Loading and authorized use

The verified port-8000 process was PID 14672. The existing restart helper verified the project executable and environment headers, then Windows rejected `Stop-Process` with **Access is denied**. No alternative process-control mechanism, credentials, startup-guard change or different server port was used. Restart from the user's own terminal before expecting the browser to use the updated Python code:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/restart-current-development.ps1
```

After separately authorized setup, approve the four main weights in the Vault; complete the central calculation rules and shared cutoff choice; review and approve A/B/C; complete normal program approvals. Compatible programs then receive the shared binding automatically. Accept the complete eligible pool's current evidence before generating rankings, then make human decisions under the existing capacity/tie rules.

The inspected development database currently has **no recorded dataset scoring policy**. This implementation supplies the workflow, not that missing institutional approval. The reported program is historical and retains its earlier method and calculations; approving the new Vault does not convert its results. Existing scored/active programs still need their authorized revision procedure. No live approval, binding, scoring, release or publication was performed during this task.
