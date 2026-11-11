# Composite SES implementation and validation — 27 October 2026

## Result

Implemented the owner's exact candidate `SES = I × (9/10 + (1/10) × P)` through the current EWAF workflow. No additive candidate is used. The method is `ewaf-ses-4ps-es-pa-hm-dataset-v1`; its explicit formula version is `income-4ps-multiplier-90-10-v1`.

This is a separate method/policy version. Income-only SES and both historical HI/SI and SI/ES/PA/ND paths remain available with their original calculations. The [new calculation/Admin guide](EWAF_Composite_SES_Configuration_and_Ranking.md) documents the exact rule, examples and operating steps. Prior validation documents remain unchanged historical evidence.

Implementation is in branch `ronnel-updates`, existing HEAD `805c059`, the existing single worktree `C:\Users\rovic\Documents\Capstone System\System Vault\santolan-pwd-system`. No commit, push, merge, deployment, real scoring activation, institutional approval or real program publication occurred. Unrelated unfinished work and the owner's accepted 70% milestone were preserved.

## Integration and approval boundary

- Reused the existing weight editor, projection engine, Vault revisions, shared policy records, acceptance reviews, calculation records, audits and program routes. No parallel policy store or ranking screen was created.
- Added composite-specific method metadata, source description and policy choices. The internal formula and 90/10 coefficients are fixed for this version and checked during calculation. Institutional household-relationship/evidence procedures remain explicit unapproved choices until staff records and approves them.
- Main SES/ES/PA/HM sliders, all priority positions, generated comparisons, strict CR/order checks and exact retained weights remain separate from the internal adjustment. The existing stored-weight precision restriction is unchanged.
- A compatible approved income-only SES main vector may be explicitly reused in a new composite policy. Its source/version/provenance remains intact; new policy approval is still required. A new unpublished draft with no applicants may explicitly adopt the composite policy using that same retained vector. Existing income-only policy bindings or published old-method intakes are not converted by this action. Five-criterion and historical different-signature vectors remain incompatible.
- The policy and evidence forms distinguish household Verified Yes, Verified No and Unresolved. Acceptance requires the approved household relationship/evidence review and current verified SES support. A shared permitted assessment can substantiate both income and P. No certificate of non-membership, new mandatory document type, old SI indigency prerequisite or government database access is invented.
- Accepted inputs retain H and P; the frozen run retains the accepted review, its periods and evidence references. The SES trace adds I, the exact multiplier and formula version while keeping final normalized SES and the main weighted contribution. Only H supplies SES's dataset Min–Max bounds; P and composite SES are not normalized separately.
- Existing complete-pool readiness, stale/expired/foreign evidence, invalid income, PA coverage, constants, exact ranking, human decision/capacity, release and restricted publication controls remain in force.
- The applicant list and private breakdown show reviewed household participation. The breakdown distinguishes the multiplier from the main weight. Private exports contain the retained calculation; public projections gain no private income, participation, evidence or scores.

## Exact synthetic fixtures

Pool bounds are independently derived from accepted fixture endpoints 0 and 100000. They are not policy thresholds.

| H | I | P=0 SES | P=1 SES |
|---:|---:|---:|---:|
| 0 | 1 | 9/10 | 1 |
| 10000 | 9/10 | 81/100 | 9/10 |
| 50000 | 1/2 | 9/20 | 1/2 |
| 100000 | 0 | 0 | 0 |

Tests compare full rational values, income bounds, I, multiplier and weighted contribution, not only formatted scores. They verify `SES(20000,Yes)=4/5` and `SES(15000,No)=153/200`; the higher-income 4Ps household has the higher SES contribution here. They verify `100 × (2/5) × (9/10)=36` points and a No→Yes change of exactly `I/10` in SES.

All-No and all-Yes pools calculate with varying income/ES/PA/HM. With the synthetic main vector 0.40/0.20/0.20/0.20, the best all-No applicant scores exactly 96; the same all-Yes case scores 100. The final score is not renormalized. Adding an accepted income of 200000 changes the income need at 100000 to 1/2.

Other tests cover unchanged scores with different optional indigency evidence/document counts; a reviewed accepted PHP 100000 with positive need in a 0–200000 pool; unresolved conflicts; absent/missing/invalid P; disputed and stale evidence; foreign evidence; unresolved inventory; constant income; exact/near ties; all 24 priority orders; policy and weight version preservation; and audit rollback. No score is hardcoded in implementation logic.

## Validation runs

Final broad result: **225 passed in 226.338 seconds** — 21 composite tests and the existing 204-test EWAF regression set.

1. Focused run: **50 passed in 91.299 seconds** — 19 initial composite tests and 31 existing income-only SES tests. Artifact directory: `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-ncoqv93_`.
2. Expanded regression: **225 passed**, including two additional composite HTTP-policy/weight and evidence/inventory checks, plus the original 204-test EWAF regression set. These overlap the focused run; counts must not be added together as unique coverage. Final artifact directory: `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-zgh6983t`; verified database `test_g12_disposable`, loopback port 57376, UUID `832c416f-d170-11f1-b72c-581122e63603`. The runner destroyed the test database afterward and retained the log.
3. Existing Node slider harness: **2,500 cascade/reorder iterations passed**, with explicit endpoint and priority cases across SES and both historical signatures. Slider JavaScript and AHP kernels were not changed by the composite revision.
4. Read-only Django system check, migration-state check and `git diff --check` passed. The working-database preservation/replay results are below. Git's existing line-ending notices were informational, with no whitespace errors.

The expanded command is:

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_composite_ses ewaf.test_ses_workflow ewaf.test_dataset_policy ewaf.test_document_ranking ewaf.test_intake_policy ewaf.test_vault ewaf.test_weight_input ewaf.test_household_criteria ewaf.test_operational ewaf.test_score_breakdown ewaf.test_revised_math ewaf.test_four_criterion_reference ewaf.test_four_development ewaf.test_ahp_validation --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The existing G12 wrapper verifies a fresh loopback MySQL identity, disables `.env`, restricts grants to disposable databases and supplies synthetic private media. It creates no real approval or applicant evidence. The model-synchronized disposable baseline uses MySQL 8.4.11, InnoDB and READ-COMMITTED. Historical migration application/reversal remains guarded.

The stored-service journey tests cover explicit approved weights/policy → immutable binding → accepted H/P/ES/PA/HM → HTTP ranking generation → exact score/contribution replay → separate human decisions → permitted public-result projection → actual synthetic release. HTTP checks also exercise the actual policy editor, A/B/C approval, four-weight draft/approval and priority reordering, evidence form, private breakdown and export. Changing main weights does not alter an existing bound formula or vector.

Limitations: this is a focused EWAF regression suite, not every repository test. No real-user acceptance or production journey was run. Browser interaction/layout validation was not rerun: the preceding SES task's browser launch was blocked by Windows `spawn EPERM`. This task reports server-rendered HTTP and slider-algorithm checks separately and makes no browser/screenshot pass claim.

## Schema and historical preservation

The actual EWAF migration leaf is `0012_dataset_policy_integration`, already applied in the working database. Existing method strings, JSON policy/findings/traces and immutable references support the composite version. There are no model-field changes, migrations, approval seeds or historical score conversions. The existing schema-graph test covers migration state; no new migration rehearsal is claimed.

Task-start and after-change read-only checks verified `santolan_lab_ronnel_20261026` on port 3308. SQL wrappers rejected writes. All 95 inspected EWAF, program, assistance, membership, member, document, admin-audit and migration tables matched their task-start hashes.

- 11 retained Vault versions replayed.
- Zero shared scoring-policy versions existed in the inspected working database; none was created by this task.
- 17 retained operational calculations replayed.
- Seven known legacy runs still have their previous Program Relevance completeness failures. IDs and exact error messages matched the earlier validation record; no new historical replay failure occurred.
- Old SI 0/2.5/5 and income-only SES fixtures remain covered by the unchanged regression modules, including the earlier operational scores 79.47/63.15/14.11. Those are not substituted as expectations for the new composite method.

Historical SI/engine files, the income-only policy definitions, AHP kernels, operational orchestration, slider JavaScript, settings, startup guard and prior SES documentation match task-start hashes. Method-aware integration files were deliberately amended; preservation does not mean every implementation file stayed unchanged.

## Files changed

New implementation/tests:

```text
ewaf/revised/composite_ses.py
ewaf/revised/composite_ses_policy.py
ewaf/test_composite_ses.py
```

Amended:

```text
ewaf/dataset_methods.py
ewaf/operational_models.py
ewaf/operational_views.py
ewaf/revised/contracts.py
ewaf/revised/live_evidence.py
ewaf/revised/live_forms.py
ewaf/revised/live_math.py
ewaf/revised/live_services.py
ewaf/revised/live_views.py
ewaf/score_breakdown.py
ewaf/vault_forms.py
ewaf/vault_policy.py
ewaf/vault_services.py
ewaf/vault_views.py
templates/ewaf/breakdown_criterion_rows.html
templates/ewaf/operational_workspace.html
templates/ewaf/revised/input_review.html
templates/ewaf/revised/policy_choices.html
templates/ewaf/revised/policy_weights.html
templates/ewaf/vault.html
```

New documentation: this report and `docs/EWAF_Composite_SES_Configuration_and_Ranking.md`. Local preservation hashes/helpers are under `.local/ewaf-composite-ses-20261027`; disposable logs remain in the existing G12 artifact directories. No existing file was deleted by this task.

The task-start inventory records 20 amended existing files, five new files including documentation, no task-deleted files and 1,199 existing files unchanged. Preexisting user changes and deletions were preserved.

## Remaining operating requirements

Authorized staff still need to record the chosen main weights, adopt the exact composite policy, specify institutional income/evidence/household/history procedures and scope/effective dates, approve A/B/C, bind an appropriate program/cutoff, and accept current findings for the complete eligible applicant pool. Existing activation and role controls remain unchanged; technical implementation is not authorization to enable real scoring.

No formula choice remains open in this implementation: the requested income-dependent multiplier is implemented exactly. The new guide and policy UI explicitly disclose that it can reverse similar-income SES ordering, does not guarantee fairness or eliminate overlapping influences, and does not independently establish poverty or government eligibility.
