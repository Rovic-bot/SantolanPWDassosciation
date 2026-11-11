# SES EWAF implementation and validation — 27 October 2026

## Status and scope

**Implementation: completed in the checkout. Validation: partial because the browser process could not launch. Real-data activation: not performed.** See the [Admin and calculation guide](EWAF_SES_Configuration_and_Ranking_Guide.md).

The new `ewaf-ses-es-pa-hm-dataset-v1` method is integrated into the existing Vault, policy approval, immutable program binding, accepted evidence, operational ranking, score breakdown, private export, reasoned human selection, actual release and permitted-publication services. It is not an isolated calculator or a restored preview page.

The owner's explicit SES implementation instruction governs this revision. It supersedes older conflicting prompt versions and earlier blanket restrictions on EWAF source edits for this scope only. No institutional approval, approval seed, historical conversion, live weight selection, feature-flag change, commit, push, merge, deployment or real program publication was performed. The accepted 70% milestone remains unchanged.

Checkout: `ronnel-updates`, existing HEAD `805c059`, one worktree at `C:\Users\rovic\Documents\Capstone System\System Vault\santolan-pwd-system`. Existing unrelated unfinished work was preserved.

## Source reconciliation

- Read the current system specification, development guidance, implementation impact, decisions, applicable validation evidence and actual implementation contracts. TARGET documentation was not treated as proof of availability or extra implementation authority.
- Read `docs/EWAF_Current_Criteria_Scoring_and_Ranking.md` as the preceding five-criterion baseline and checked it against the checkout. It remains unchanged.
- Read the actual root `Computation_Updated_SES_ES_PA_HM.docx` with the documents skill. Its SHA-256 is `bac9c89e20047c241f536a7df6d48eb5b89f8e246ec9aabc0fd67aeb1c6d27a3`.
- Read `Codex_EWAF_SES_Computation_and_Ranking.md`; its `.txt` counterpart is identical. Earlier `Codex_EWAF_Updated_Computation_and_Ranking_SES_ES_PA_HM` copies were treated as superseded prompts, not independent tasks or approvals.
- **Source discrepancy:** the actual available Word file uses a 25%-each teaching placeholder. It does not contain the fractional q attributed to the DOCX in the current instruction. The fractional-q fixture is implemented as the explicitly requested demonstration, alongside a separate test for the actual Word placeholder. Neither is a production seed. The original Word file was not rewritten.
- The current instruction's cascading controls, discrete multiplicative projection and operational integration take precedence over the earlier simpler slider guidance and ratio-reconstruction teaching shortcut.

## Implemented behavior

| Area | Result |
|---|---|
| Identity | Exact method and canonical SES/ES/PA/HM signature; old SI/ES/PA/ND and HI/SI/ES/PA/HM cannot be mistaken for SES |
| SES | Accepted average household PHP income, inverse, normalized once; no HI/SI contribution, per-person adjustment, expense subtraction or document bonus |
| Evidence | Explicit method-bound acceptance; current permitted evidence, income discrepancy review, ES mapping, positive household count and PA coverage remain required |
| Documents | Reviewed 4Ps/indigency information supports verification only; identical accepted values produce identical scores regardless of optional document count |
| Weights | Blank first setup, matching draft restoration, four cascading sliders, all priority positions, code-keyed weights, server feasibility/provenance checks, saved-draft review before approval |
| AHP | Six supported pairwise comparisons, reciprocal 4×4 matrix, row-average weights, CI denominator 3, RI 0.90, strict CR/order checks, retained 50-digit arithmetic |
| Policy | Existing versioned storage and A/B/C approvals; SES income authority/procedure replaces SI-rubric prerequisites for this method only |
| Binding | Exact immutable program/method/policy/weight/cutoff binding; compatible weights-only intake remains possible; old and active scored bindings are protected |
| Ranking | Complete accepted eligible pool, inverse SES/PA and increasing ES/HM, exact four-term sum, half-even display, exact competition ranks, constant-column and unresolved-input stops |
| Downstream | Existing human selection, capacity/tie controls, release and restricted public projection; private retained-run JSON export with permission checks |
| History | Original method keys, old SI rules, weight versions, references, approvals, evidence, results and predecessor chains retained |

### Precision restriction discovered during review

The existing retained-weight contract is asymmetric: stored total must not exceed 1; a deficit is permitted only within the existing decimal-place-derived residue bound. It was extracted into `contracts.validate_weight_total` without changing that rule. It is reused by historical snapshots, new SES approval and the SES preview. No coefficient is rescaled or silently corrected.

An independent check found that some CR-valid proposals have a tiny positive 50-digit residue. For canonical 40/30/20/10, it is `+1.5e-50`; for 35/25/25/15, `+4e-50`. These can be saved as unapproved drafts, but the preview explains the incompatibility and approval is blocked. The requested operational fixture has `-1e-50` and is compatible. Tests also verify storage-compatible unequal vectors and all 24 priority orders. Changing the total contract to accept positive residues remains a separately authorized policy/precision change, not an unreported alteration in this task.

## Calculation fixtures

All three use synthetic A = [5000,3,1,4], B = [12500,4,0,2], C = [20000,1,3,6], ordered SES/ES/PA/HM.

Bounds are SES [5000,20000], ES [1,4], PA [0,3], HM [2,6]. Normalized rows are A = [1,2/3,2/3,1/2], B = [1/2,1,1,0], C = [0,0,0,1].

| Fixture | A | B | C | Ranks |
|---|---:|---:|---:|---|
| Requested fractional teaching q | 78.93 | 61.62 | 15.99 | 1,2,3 |
| Actual slider → discrete AHP → ranking | 79.47 | 63.15 | 14.11 | 1,2,3 |
| Actual Word file's equal-weight placeholder | 70.83 | 62.50 | 25.00 | 1,2,3 |

Requested teaching q is `[3421,1774,1223,1222]/7640`. Independent exact rational arithmetic reconstructs `A[i,j]=q[i]/q[j]`, reproduces q and obtains CR=0 by construction. Its exact EWS100 values are `15075/191`, `47075/764`, `3055/191`. This path exists only in the test fixture and is not an operational approval mechanism.

The operational proposal `[44.78,23.22,16.01,15.99]` produces:

```text
[1,   2,   3, 3]
[1/2, 1,   2, 2]
[1/3, 1/2, 1, 1]
[1/3, 1/2, 1, 1]
```

Independent mathematical row averages are `[331/728,383/1456,411/2912,411/2912]`. The actual 50-digit stored coefficients are:

```text
SES 0.45467032967032967032967032967032967032967032967032
ES  0.26304945054945054945054945054945054945054945054945
PA  0.14114010989010989010989010989010989010989010989011
HM  0.14114010989010989010989010989010989010989010989011
CR  0.0038366432017554408350061907865019606744886168244444
```

The stored total is exactly `1 - 10^-50`. Tests compare these generated coefficients and CR against independent rational references with absolute `1e-47` verification tolerance for the 50-digit arithmetic only. This tolerance does not relax the operational CR cutoff or the retained weight-total contract. Ranking uses the actual stored strings, never these rounded display percentages.

The three-applicant operational fixture also runs through stored draft/approved weights, approved policy, program binding, verified evidence and real synthetic release-ledger records with counts 1/0/3. It generates the expected 79.47/63.15/14.11 through the real operational service and replays the saved run successfully.

## Test evidence and limitations

Final regression result: **204 passed in 206.920 seconds**, including 31 SES tests and 173 existing regression tests. The final disposable run used artifact directory `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-oqlwlt89`, database `test_g12_disposable`, loopback port 55281 and verified server UUID `6e5d2896-d16d-11f1-8348-581122e63603`. The test database was destroyed by the runner afterward; logs were retained.

The focused tests cover first setup without defaults; matching draft restoration; rejection of changed/unapproved proposals; compatible and incompatible signatures; A/B/C policy approval; HTTP binding and input acceptance; document/4Ps invariance; accepted high income; unresolved contradictions; unlisted employment; missing/foreign/stale evidence; household-domain checks; incomplete PA coverage; release-recording cutoff; unresolved inventory; constant/single-person pools; exact/near ties; capacity and reasoned-human ties; full-pool recalculation; preserved predecessor runs; private exports and authentication; stale requests, concurrent drafts and audit rollback. The two independent mathematical fixtures and the actual Word placeholder are separate tests.

A synthetic end-to-end test follows stored policy → binding → accepted inputs → HTTP ranking generation → separate human decisions → permitted results preparation/publication → actual release. Public projections exclude private inputs, scores and evidence. Methodology text may identify criterion codes, as allowed by the existing public projection.

The regression command is:

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_ses_workflow ewaf.test_dataset_policy ewaf.test_document_ranking ewaf.test_intake_policy ewaf.test_vault ewaf.test_weight_input ewaf.test_household_criteria ewaf.test_operational ewaf.test_score_breakdown ewaf.test_revised_math ewaf.test_four_criterion_reference ewaf.test_four_development ewaf.test_ahp_validation --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The existing local wrapper invokes the fresh-instance G12 launcher, disables `.env`, verifies a disposable MySQL identity, limits database grants and uses disposable synthetic media. It does not use normal application data. Do not replace it with an unverified test database or the normal startup command.

Runs are overlapping validations, not additive coverage counts:

| Run | Result and interpretation |
|---|---|
| Initial focused run, 45 | 43 passed, two test-fixture issues: duplicate evidence requirement and overly broad privacy assertion. An imported baseline test class also added 27 overlapping historical tests to discovery; fixed. |
| Corrected focused run, 22 | 22 passed. |
| First broad run, 202 | 201 passed; one Vault readiness-message regression. Restored the publication/intake versus scoring distinction. |
| Second broad run, 202 | All 202 passed before the final precision-contract checks were added. |
| Final broad run, 204 | All 204 passed, including the two added precision-contract tests and the final method-aware binding guard. |
| Node slider harness | 2,500 deterministic cascade/reorder iterations passed across SES and both historical signatures, plus explicit position/endpoint cases. This is algorithm validation, not browser validation. |
| Browser integration, 1 attempted | Failed before executing UI assertions: `browserType.launch: spawn EPERM` for the configured Brave executable. Browser screenshots, real keyboard behavior and responsive layout remain unverified. |

The browser harness is `scripts/ses_browser_qa.py` / `.cjs`. It prepares only synthetic fixtures in disposable MySQL and targets four-slider keyboard/arrows, saved draft/approval, SES policy/evidence/breakdown screens and preserved five-criterion controls. Browser denial was not bypassed and was not counted as a pass. Server-rendered HTTP checks cover the actual new and historical page contracts separately.

This was a targeted EWAF regression set, not the entire repository suite. Historical migration replay was not run. No real staff, real applicant or production publication journey was executed.

Final `manage.py check --database default` and migration-state checks passed through a read-only guarded verification helper. `git diff --check`, JavaScript syntax checks, and the 2,500-case slider harness passed. Git emitted existing line-ending conversion notices; no whitespace errors were reported.

## Schema and preservation evidence

The actual working database's EWAF migration graph ends at **0012_dataset_policy_integration**, already applied. Existing method, JSON content, policy FK, accepted-findings and immutable-history fields accommodate SES. No model-field changes or new migrations are required; no migration number was reused and no approval seed was created.

The disposable runner synchronized the current model schema in a fresh MySQL 8.4.11 instance with InnoDB tables and `READ-COMMITTED`. Its guard forbids blanket historical migration apply/unapply. The schema-graph test and `makemigrations --check --dry-run` report no unrepresented model changes. There is therefore no new migration rehearsal to claim.

Read-only preservation checks verify the working database identity `santolan_lab_ronnel_20261026` on port 3308 and reject write SQL. Before/after hashes match for all 95 inspected EWAF, programs, assistance, membership, members, documents, admin-audit and migration tables.

- All 11 retained Vault versions replay.
- There are zero stored shared scoring-policy versions in the inspected working database; none were created by this task.
- 17 retained operational runs replay.
- Seven known preexisting legacy runs still fail their existing Program Relevance item/outcome completeness validation. Their run IDs and exact messages match the prior validation record. This task neither repaired nor converted them.
- New historical replay failures: zero. Database writes by preservation checks: zero.

The original Word file, previous workflow Markdown, historical `revised/engine.py`, `revised/si.py`, `household_math.py`, `four_criterion_development.py`, operational orchestration, settings and startup script match their task-start hashes. Other authorized method-aware EWAF files were amended as listed below; this report does not claim that every EWAF implementation file stayed unchanged.

The task-start file inventory comparison records 28 amended existing files, eight added files including this report and the guide, no task-deleted files, and 1,183 existing files unchanged. Preexisting user deletions and other unfinished Git changes were preserved.

## Files changed for this revision

New implementation/tests:

```text
ewaf/dataset_methods.py
ewaf/ses_math.py
ewaf/revised/ses_policy.py
ewaf/test_ses_workflow.py
scripts/ses_browser_qa.py
scripts/ses_browser_qa.cjs
```

Amended implementation/templates/tests:

```text
ewaf/household_criteria.py
ewaf/operational_models.py
ewaf/operational_policy.py
ewaf/operational_views.py
ewaf/revised/contracts.py
ewaf/revised/live_evidence.py
ewaf/revised/live_forms.py
ewaf/revised/live_math.py
ewaf/revised/live_models.py
ewaf/revised/live_services.py
ewaf/revised/live_views.py
ewaf/score_breakdown.py
ewaf/urls.py
ewaf/vault_forms.py
ewaf/vault_policy.py
ewaf/vault_services.py
ewaf/vault_views.py
ewaf/weight_input.py
scripts/ewaf_weight_slider_test.cjs
static/js/ewaf-weights.js
templates/ewaf/program_sections.html
templates/ewaf/revised/input_review.html
templates/ewaf/revised/policies.html
templates/ewaf/revised/policy_choices.html
templates/ewaf/revised/policy_review.html
templates/ewaf/revised/policy_weights.html
templates/ewaf/vault.html
templates/ewaf/weight_editor.html
```

New documentation: this report and `docs/EWAF_SES_Configuration_and_Ranking_Guide.md`. Ignored local evidence/helpers remain under `.local/ewaf-ses-20261027`; disposable logs remain under `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-*`. No existing source or evidence file was deleted by this task.

## Remaining operating dependencies

An authorized Admin must select a storage-compatible four-weight proposal; approve its exact calculated vector; specify institutional income periods/basis, household definition, permitted evidence/alternatives, history scope and coverage, assessor authority, ties/corrections, effective dates and policy scope; explicitly approve the policy; and bind an appropriate program/cutoff. Staff must then resolve eligibility and accept current evidence for the complete applicant pool. Existing feature and authority controls continue to apply without changes to real-user permissions.

No new decision is requested about the four criteria, document points or editable weights: those technical choices are implemented. The preserved asymmetric total contract is disclosed above; broadening it is not implied approval. Browser acceptance remains an environment-blocked verification dependency. The exact Admin actions are documented in [the guide](EWAF_SES_Configuration_and_Ranking_Guide.md#7-admin-sequence-after-authorized-operating-setup).
