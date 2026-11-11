# Revised EWAF implementation report — 25 October 2026

Implemented a separate **synthetic calculation and private Admin ranking preview**, method `ewaf-hi-si-es-pa-hm-dataset-v1`. Official scoring remains blocked. The accepted milestone remains **70%**. No working database, running runtime, credentials, activation settings, startup guard or deployment was changed; nothing was committed or pushed.

## Source and reproduced results

Reviewed the actual [revised computation DOCX](../../EWAF_Computation_Download/Computation_Updated_HI_SI_ES_PA_HM.docx), including all tables, equations, example assumptions and final revision record. SHA-256: `b8b2af991278a19f2a42bce7e84100d06ae86541f691372cc715415c0002d6eb`. The source is unchanged. [Text extraction](source-extraction.txt), [versioned implementation contract](implementation-contract-v1.md), and [full exact intermediate evidence](example-evidence.json) are retained separately. The older computation was not used to reconstruct this version.

| Synthetic applicant | Exact score / 100 | Display | Internal competition rank | Example classification |
| --- | --- | --- | --- | --- |
| A | 839/10 | 83.90 | 1 | High |
| B | 7537/120 | 62.81 | 2 | Moderate |
| C | 611/50 | 12.22 | 3 | Minimal |

Derived AHP results, in HI/SI/ES/PA/HM order:

- Weights: 0.3421, 0.2360, 0.1774, 0.1223, 0.1222.
- WSV: 1.7105, 1.1800, 0.8870, 0.6115, 0.6110.
- CV: 5, 5, 5, 5; λ estimate 5; CI 0; RI 1.12; CR 0.
- Shared minima: 5000, 1, 1, 0, 2; maxima: 20000, 4, 4, 3, 6.
- Normalized A: 1, 1, 2/3, 2/3, 1/2; B: 1/2, 2/3, 1, 1, 0; C: 0, 0, 0, 0, 1.

The matrix is labeled **Illustrative reconstructed matrix.** Its exact ratios reproduce supplied percentages; CR = 0 is not institutional validation. Column normalization and row averages are tested with both this perfect matrix and a nonperfect reciprocal matrix. Scores, classifications and competition ties use exact rational arithmetic with zero comparison tolerance; explanatory decimals have 50 significant digits and display rounds half-even to two places only after computation.

The document supplies scores and classifications. **Numerical competition ranks are the convention added by the owner's implementation prompt**, not a claim about the document. Equal exact scores share a rank and explicit tie group; capacity-boundary ties never select a hidden winner.

## Delivered workflow and availability

The new private route is **`/ewaf/revised/`**, linked under the existing **EWAF & Selection** group as **Revised dataset preview**. It offers method/mode selection, four independent draft sliders/numeric controls, automatic remaining HM, total 100%, server validation, optional example classifications/capacity, internal ranking, exact AHP and score breakdowns, frozen inputs/bounds, readiness warnings, retained history, independent review and private JSON/CSV/Excel exports.

HI = 40% at the other defaults gives HM = 6.43%; the other three weights do not move. HI = 62.55% with the other three at their minima gives HM = −8.33% and is rejected. Effective slider limits respect the remaining total. HM zero is labeled exploratory only and is never accepted as an AHP weight. No approved HM minimum/maximum is invented. Draft proposals retain manual provenance and do not create an AHP matrix.

Retained previews and reviews are append-only, versioned, audited and linked to predecessors. They capture the method, selected program context, exact configuration/provenance, frozen synthetic pool, evidence/input versions, cutoff, directions/bounds, precision/ranking convention, actor/time/reason and request identity. Current-use checks reject stale program context and stale/concurrent reviews. Historical snapshots remain viewable and are not recalculated or published automatically.

Preview retention/review/export uses the existing private `admin.LogEntry` audit channel, scoped to the new model content types, and existing append-only guards. It deliberately does not append source-changing ProgramLog events or alter legacy freshness rules. A regression demonstrates that an active four-criterion run, human decision and public projection remain current and identical after all three preview actions.

**Availability boundary:** the preview is implemented and tested in this checkout. It has **not** been installed into the separate running local copy. Retention/history requires the new additive schema and assigned permissions; the page itself never runs migrations. With that schema absent, an authorized user can still calculate the transient synthetic example, but retention/history is unavailable. No real applications are loaded into this version.

The standalone demonstration runs now without Django settings or a database:

```powershell
.venv\Scripts\python.exe -B -m ewaf.revised.demo
.venv\Scripts\python.exe -B -m ewaf.revised.demo --json
```

The first command was executed successfully. Complete reproducible JSON is retained in `example-evidence.json`.

## Exact implementation files

| Area | Files |
| --- | --- |
| Exact calculation and synthetic input/configuration contract | `ewaf/revised/__init__.py`, `ewaf/revised/math.py`, `ewaf/revised/engine.py`, `ewaf/revised/fixtures.py`, `ewaf/revised/demo.py` |
| Private history, permission/readiness/audit services and forms/views | `ewaf/revised/models.py`, `ewaf/revised/services.py`, `ewaf/revised/forms.py`, `ewaf/revised/views.py` |
| Admin display and draft controls | `templates/ewaf/revised/preview.html`, `templates/ewaf/revised/result.html`, `templates/ewaf/revised/retained.html`, `static/js/ewaf-revised-weights.js` |
| Additive schema | `ewaf/migrations/0011_revised_dataset_preview.py` |
| Tests and isolated runner | `ewaf/test_revised_math.py`, `ewaf/test_revised_preview.py`, `scripts/revised_ewaf_test_runner.py`, `scripts/revised_ewaf_schema_tests.py`, `scripts/revised_ewaf_weights_test.cjs` |
| Only existing-file integration changes | `ewaf/models.py` (two new model imports), `ewaf/urls.py` (three private routes), `templates/ewaf/tabs.html` (permission-controlled method tab) |
| Contract/evidence | This directory's report, contract, source extraction, exact example, baseline/preservation manifests, validation metadata and retained logs |

There is **no operational dispatch extension**. Existing fixed-bound engines, ND meanings, protected evidence/selection/publication/release services and all old tests remain unchanged. No public route or rank projection was added. The eight Admin groups and existing sidebar files remain unchanged.

The migration creates **two new tables**, `ewaf_revisedpreviewrun` and `ewaf_revisedpreviewreview`, with six constraints and four unassigned permission definitions. It depends on `ewaf.0010_shared_configuration_vault`, `programs.0005_approved_terms`, `admin.0003_logentry_add_action_flag_choices` and the swappable user. It contains no RunPython, backfill or changes to existing tables. Final migration SHA-256: `c3c8889714cfa485cf47973b6019002f3a96cb03e119dd19ed4938e5b7491194`.

## Actual verification and failures

All database checks used the existing G12 fresh-instance launcher: native MySQL **8.4.11**, new loopback datadir/port/server UUID, empty `g12_empty`, separate **`test_g12_disposable`**, disabled `.env`, test-only grants and isolated media. The new runner synchronizes model-derived baseline tables and permits only the hash-pinned new migration's operations. No historical schema migration was executed, and no old report was treated as the working database's current state.

| Evidence | Actual result |
| --- | --- |
| [Final revised suite](final-revised-tests.log) | **48 passed**, 37.974s, no failures/errors/skips. Includes math, HTTP, permission/CSRF/direct-request denial, stale/concurrent saves/reviews, immutable history, audit rollback/revocation, private exports, no public ranks/selection, active legacy isolation and exact new-schema reverse/forward. |
| [Initial combined regression run](initial-regressions.log) | **140 executed: 136 passed, 4 failed.** 96 existing regression tests passed. Two new HTTP assertions expected an exact Cache-Control string; Django added stronger cache-prevention directives. Assertions were corrected to require `private` and `no-store`; final suite passes. Two old fixed-schema assertions remain incompatible, as explained below. |
| [Intermediate revised suite](focused-v1.log) | 44 passed, 30.885s, before the final audit-channel isolation improvement and its added regression. Retained as earlier evidence, not substituted for the final run. |
| [Server-rendered controls](server-rendered-controls.log) | 3 passed, 2.217s. Correct HM/total also renders without JavaScript; invalid totals are explained. Included again in final coverage. |
| [Schema drift](schema-drift.log) | `makemigrations --check --dry-run --noinput`: **No changes detected**, exit 0 after final schema edits. |
| Node control/DOM harness | Passed independent control values, immediate HM, infeasible endpoints, effective limit, zero exploration, invalid-input preservation/submission blocking and restore defaults. An initial ad-hoc stdin harness had a `document` variable shadowing error; the retained test harness corrects that test setup. |
| Static checks | New Python AST/whitespace checks, JavaScript syntax and `git diff --check` passed. Git reported pre-existing line-ending normalization warnings only. |

The two **unchanged, still failing** older assertions are:

- `ewaf.test_ranking_preservation.RankingPreservationTests.test_no_schema_models_or_permissions_added`
- `ewaf.test_recalculation_preservation.RecalculationPreservationTests.test_no_new_models_schema_permissions_or_routes`

Both hardcode EWAF migration leaf `0008_operational_four`; this checkout already contained `0009_household_registration_criteria` and `0010_shared_configuration_vault` before this task, and now has separately authorized additive `0011`. These assertions were **not removed, edited or made to pass by hiding the new schema**. The combined run is not claimed as wholly green. Their separate history/zero-write and retired-workflow guards passed. Existing four/historical-five reference, AHP, normalization, weighted scoring, operational complete-pool, human tie/slot decisions, stale evidence, publication and actual-release regressions passed.

Exact final command:

```powershell
.venv\Scripts\python.exe -B .local\dual-registration-20261024\run_tests.py test ewaf.test_revised_math ewaf.test_revised_preview scripts.revised_ewaf_schema_tests --testrunner scripts.revised_ewaf_test_runner.RevisedEWAFTestRunner --noinput --verbosity 2
```

Exact combined regression command:

```powershell
.venv\Scripts\python.exe -B .local\dual-registration-20261024\run_tests.py test ewaf.test_revised_math ewaf.test_revised_preview scripts.revised_ewaf_schema_tests ewaf.test_computation_reference ewaf.test_four_criterion_reference ewaf.test_ahp_validation ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_four_kernel ewaf.test_operational ewaf.test_delivery ewaf.test_household_criteria ewaf.test_ranking_preservation ewaf.test_recalculation_preservation --testrunner scripts.revised_ewaf_test_runner.RevisedEWAFTestRunner --noinput --verbosity 2
```

Other executed checks:

```powershell
.venv\Scripts\python.exe -B -m unittest ewaf.test_revised_math -v
.venv\Scripts\python.exe -B .local\dual-registration-20261024\run_tests.py makemigrations ewaf --name revised_dataset_preview --noinput
.venv\Scripts\python.exe -B .local\dual-registration-20261024\run_tests.py makemigrations --check --dry-run --noinput
node --check static/js/ewaf-revised-weights.js
node scripts/revised_ewaf_weights_test.cjs
git diff --check
```

The generated new migration was revised before any working use to bind preview audits to the private admin audit channel, then hash-reviewed, drift-checked and rehearsed again. No pre-existing migration was changed. Full browser/visual, representative screen-reader/UAT, real-data handoff, production load and a faithful target-database upgrade were **not tested**. Browser launching was unavailable in the earlier environment; no browser-approval bypass was attempted. DOCX contents were inspected structurally; source page layout was not rendered.

## Preservation and remaining operational dependencies

[Preservation evidence](preservation.json) compares **1,207 pre-existing repository files**. Only the three listed integration files changed; **1,204 match exactly**, including every pre-existing migration, protected old calculation/service/test, startup guard and activation setting in that baseline. The original revised DOCX hash is identical. Existing unrelated Git work is preserved. The prior protection manifest already differed at the root/runtime Vault templates before this task; baseline metadata records those pre-existing differences. No files were copied to the running runtime and no application database was queried, migrated or activated.

Official scoring still requires:

- An approved numerical **SI rubric** and traceable accepted SI assessment; 4Ps and supporting documents are evidence only.
- Actual **weight authorization**: recorded pairwise judgments/validation, or a separately approved manual weighting method.
- The **accepted-evidence handoff and invalidation integration** for this version. Registration/member approval or review notes are insufficient, and no raw profile fallback exists.
- Approved income and household definitions, assessment periods, ES categories, qualifying actual-release scope/period/cutoff and evidence requirements.
- Approved dataset directions/complete-pool policy and required-input/constant-column handling, plus recorded competition ranking and capacity-boundary human tie procedure.
- A current authorized, versioned, locked configuration and separately reviewed operational enablement. Official classifications require their own approval if enabled.

The existing running application, historical results and 70% accepted milestone remain preserved. The delivered demonstration, tests and permission-controlled preview are ready for review; real scoring and public ranking were not activated.
