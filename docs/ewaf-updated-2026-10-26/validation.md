# Revised EWAF source alignment and validation — October 26, 2026

## Outcome and scope

The existing separately versioned engine already implements the supplied updated document. This change makes its private **Revised calculation preview** accessible from EWAF navigation and each program's score breakdown, aligns breakdown presentation with **HI, SI, ES, PA, HM**, and corrects outdated readiness messages. It does not replace the existing engine with another copy or recalculate historical programs.

Main development route: `http://127.0.0.1:8000/ewaf/revised/`. Viewing and calculation require the existing staff permissions. The preview uses fictional applicants A/B/C, including when a program context is selected. Retained demonstration history, reviews and private exports remain separate from actual program calculations and human beneficiary decisions.

Official scoring remains disabled. The supplied implementation instructions authorize synthetic calculation and private preview while withholding real scoring activation, working-database migrations and publication. Accepted milestone remains **70%**.

## Sources actually reviewed

- `EWAF_Computation_Download/Computation_Updated_HI_SI_ES_PA_HM.docx`: SHA-256 `b8b2af991278a19f2a42bce7e84100d06ae86541f691372cc715415c0002d6eb`.
- `Codex_EWAF_Updated_Computation_and_Ranking.md` and `.txt`: byte-identical; SHA-256 `99a5d8bd75b388b719ee5a6b1a80a7060151f1bfeb3998bd13e03537cdb71e9b`.
- `OVERALL_SYSTEM_SPECIFICATION_INTEGRATED.md`, `BRAINSTORM_INTEGRATION_LOG.md`, current specification/development guidance, Open Decisions and October 10 implementation impact.
- Existing October 24 operational closure; October 23 evidence foundation/preservation; October 25 revised-engine contract, shared-policy and dataset-policy integration; October 26 score-breakdown validation.

The DOCX was extracted in body/table order, including all 522 document paragraphs, 19 tables, 29 OMML equations and the revision register. It has no embedded media or tracked changes. Page layout was not rendered; the bundled document renderer was unavailable. The mathematical content and source hashes were reviewed directly. Source documents were not edited.

The DOCX hash matches the source pinned by `ewaf/revised/engine.py`. This note supplements [the existing version-1 contract](../ewaf-revised-2026-10-25/implementation-contract-v1.md); earlier evidence is not overwritten. Later dataset-policy integration already supplies a separately gated accepted-evidence bridge. A preview must still never treat raw registration values, membership approval, review notes or a draft policy as accepted inputs or scoring authority.

## Calculation contract confirmed

Method `ewaf-hi-si-es-pa-hm-dataset-v1`; normalization `dataset-minmax-v1`.

| Order | Criterion | Document example weight | Example direction |
| --- | --- | ---: | --- |
| HI | Household monthly income | 34.21% | Inverse |
| SI | Socioeconomic Indicator | 23.60% | Increasing |
| ES | Employment Status | 17.74% | Increasing |
| PA | Previous Assistance Received | 12.23% | Inverse |
| HM | Number of Household members | 12.22% | Increasing |

These weights and directions reproduce the document's example; they are not a new institutional approval or replacement for locked program weights. HM is not historical Number of Dependents (ND).

1. Preserve the weight source. For the document demonstration only, reconstruct `a[i,j] = q[i] / q[j]`, label it **Illustrative reconstructed matrix**, compute column sums/normalization and row-average weights, then WSV, CV, lambda, CI and CR. RI is 1.12; genuine AHP acceptance requires `0 <= CR < 0.10`. A reconstructed CR of zero does not validate independent stakeholder judgments.
2. Freeze the same complete eligible, evidence-ready pool for all five criteria. HI/SI/ES/PA/HM require accepted, current inputs with source/version/period provenance. ES encodes Full-Time Worker 1, Part-Time Worker 2, Seasonal Worker 3 and Unemployed 4. Unlisted categories block. SI requires a numerical rubric; neither 4Ps status nor document count supplies one.
3. Derive each minimum L and maximum U from that pool. Increasing normalization is `(x-L)/(U-L)`; inverse is `(U-x)/(U-L)`. Missing, disputed, stale, invalid or incomplete inputs, empty/single-applicant pools and constant columns stop calculation. There is no imputation, clipping, reweighting or silent exclusion.
4. Calculate `score = 100 * sum(weight * normalized_value)` using exact rational arithmetic. Compare unrounded totals; round only display to two decimal places using half-even. Comparison tolerance is zero. Decimal explanations use 50 significant digits.
5. Rank internally by `1 + count(strictly higher scores)`. Exact ties share rank with gaps (1, 2, 2, 4); presentation order does not select a winner. Capacity-boundary ties require human decisions. Optional example classifications use the unrounded total.

The DOCX provides scores and example classifications. Numerical competition ranking is an additional convention authorized by the accompanying MD/TXT instructions, not a claim about the DOCX.

Draft weight controls preserve independent HI/SI/ES/PA entries and calculate HM as their remainder to 100%. Invalid totals are rejected. HI 62.55 plus the other three minima would produce HM -8.33 and is rejected; no positive HM floor is invented. Manual proposals do not manufacture AHP authority or a ratio matrix.

## Independent example evidence

An independent standard-library `Fraction` derivation exactly matches the engine, including every AHP intermediate, bound, normalization, contribution, total and rank. Full expected and actual values are in [independent-math-verification.json](independent-math-verification.json).

The example WSV is `[1.7105, 1.1800, 0.8870, 0.6115, 0.6110]`; each CV is 5; lambda is 5 and CI/CR are 0. Every normalized matrix row is the example weight vector. Bounds in canonical order are `L=[5000,1,1,0,2]`, `U=[20000,4,4,3,6]`.

| Applicant | Raw HI/SI/ES/PA/HM | Normalized HI/SI/ES/PA/HM | Exact score /100 | Display | Rank | Example class |
| --- | --- | --- | --- | ---: | ---: | --- |
| A | 5000 / 4 / 3 / 1 / 4 | 1 / 1 / (2/3) / (2/3) / (1/2) | 839/10 | 83.90 | 1 | High |
| B | 12500 / 3 / 4 / 0 / 2 | (1/2) / (2/3) / 1 / 1 / 0 | 7537/120 | 62.81 | 2 | Moderate |
| C | 20000 / 1 / 1 / 3 / 6 | 0 / 0 / 0 / 0 / 1 | 611/50 | 12.22 | 3 | Minimal |

Exact contribution points:

| Applicant | HI | SI | ES | PA | HM |
| --- | --- | --- | --- | --- | --- |
| A | 3421/100 | 118/5 | 887/75 | 1223/150 | 611/100 |
| B | 3421/200 | 236/15 | 887/50 | 1223/100 | 0 |
| C | 0 | 0 | 0 | 0 | 611/50 |

## Exact changes in this source-alignment task

| File | Change |
| --- | --- |
| `templates/ewaf/tabs.html` | Permission-controlled Revised calculation preview navigation and current-tab accessibility state; retained existing navigation choices. |
| `templates/ewaf/score_breakdown.html` | Permission-controlled link to the synthetic preview with explicit distinction from the saved program calculation. |
| `ewaf/score_breakdown.py` | Reuse canonical five-criterion order for displayed rows/comparison columns; preserve original saved traces and separate historical factors. |
| `ewaf/revised/services.py` | Readiness messages acknowledge the separately gated dataset-policy/evidence implementation; official preview requests remain unconditionally blocked. |
| `ewaf/test_revised_preview.py` | Navigation/permission coverage and regression proving enabled official-workflow flags cannot turn a preview into an official run. |
| `ewaf/test_score_breakdown.py` | Canonical presentation order and retained contribution assertions. |
| `ewaf/test_dataset_policy.py` | Canonical order assertions in the existing saved-dataset-breakdown test. |
| `ewaf/test_household_criteria.py` | Canonical order assertion in the existing historical-household-breakdown test. |

Documentation added: this report, independent mathematical evidence and preservation summary. Ignored local verification scripts/artifacts are under `.local/ewaf-updated-20261026/`.

No new model, migration, operational dispatch, formula, evidence writer, permission grant, configuration approval or public route was added. Existing migrations 0011/0012 were already installed in the main development database; no migration was applied. Registration/QR work, launch-script edits and other unfinished work predate this source-alignment task and are preserved.

## Validation and preservation

Commands actually run:

```powershell
.venv\Scripts\python.exe -B -m unittest ewaf.test_revised_math -v
.venv\Scripts\python.exe -B -m ewaf.revised.demo
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_revised_math ewaf.test_revised_preview ewaf.test_revised_policy ewaf.test_revised_policy_guards ewaf.test_score_breakdown ewaf.test_dataset_policy ewaf.test_household_criteria ewaf.test_operational ewaf.test_delivery --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe -B .local\ewaf-updated-20261026\verify_main.py
git diff --check
```

- **24 mathematical tests passed** independently without a database; the demo reproduced all three exact totals/ranks.
- **132 focused tests passed in 165.309 seconds**, including those 24 mathematical tests. This is 132 distinct tests, not 156. No failures or skips were reported.
- Tests used a newly initialized native MySQL 8.4.11 instance on loopback port 57400, its own UUID/datadir and disposable `test_g12_disposable` database with isolated synthetic media; `.env` was disabled. The existing harness inherits restricted workspace ACLs only for its temporary test directories. The test database was destroyed afterward. Schema was synchronized from models; no historical migration chain was executed.
- Coverage includes every AHP intermediate and example contribution; directions/scales; exact/near ties and classification boundaries; empty/single/constant/incomplete pools; missing/stale/disputed/invalid inputs; slider totals/provenance and strict CR; frozen-pool recalculation; official-readiness and direct-request denial; permissions, atomic audit rollback, retries/concurrency, private exports; old four-criterion and household calculations; public projections without private scores/ranks; and no automatic selection.
- Django application/database checks and `makemigrations --check --dry-run` passed under the actual main development settings. The verification script permits only SELECT, SHOW and EXPLAIN queries. Its authenticated RequestFactory render returned 200, included the new navigation, exact A/B/C displays, reconstruction provenance and official-use blockers, and performed no database writes.
- A current-turn before/after comparison verifies **87 protected source/migration files and all rows of 43 inspected EWAF, program, assistance and migration tables unchanged**. Activation settings remain false. Details are in [preservation.json](preservation.json). The main database was identified by database name, UUID, port 3308 and resolved datadir; the different port-3307 checkout was not used.
- Static Python/template checks, independent code review and `git diff --check` passed. Git emitted only the pre-existing CRLF conversion warning for `docs/EWAF_Ranking_Workflow_Guide.md`.

The existing main-development launcher was used to refresh port 8000 after tests, without modifying startup guards or applying migrations. Anonymous access to the private preview redirects to login. This was a local server refresh, not a hosted deployment or official-scoring activation.

Earlier reports refer to several protection artifacts absent from this checkout, including the October 25 revised-engine baseline/preservation JSON and earlier phase baselines. Their claimed comparisons were not reconstructed or presented as new evidence. The 87-file/43-table comparison above is the freshly recorded scope for this task. It preserves existing saved calculation snapshots, configuration history, issued program references, decisions and release records in those tables; it is not a claim that every repository file or every application table was inventoried.

Untested here: browser visual/keyboard layout, a production migration rehearsal, hosted deployment and official real-data calculation. No new schema requires a migration test. Prior registration/QR validation belongs to its separate reports and was not rerun by this calculation-only task.

## Remaining official-use requirements

Real scoring still requires explicit weight authority, an approved SI rubric and assessor rules, income and household definitions, employment-category handling, PA qualifying-release scope/window and verified history coverage, accepted evidence/freshness/accessibility requirements, complete-pool/correction and constant-column policy, normalization directions, tie/capacity procedure and versioned approved program binding. Classifications require their own approval. Existing locked weights or source example percentages cannot stand in for these decisions.

Both `EWAF_DATASET_POLICY_ENABLED` and `EWAF_DATASET_SCORING_ENABLED` remain false on the main site. No real applicant was rescored, selected, approved or published by this task. No commit, push, merge or hosted deployment was performed.
