# Revised EWAF dataset method — implementation contract v1

2026-10-25, Asia/Manila. New source version only; accepted milestone remains **70%**.

## Authority and source

The owner's current implementation request explicitly permits the new HI/SI/ES/PA/HM calculation and private numerical ranking alongside historical engines. It does not permit real scoring activation, working-database migrations, public ranks, automatic selection, deployment or invented Association approval. Earlier documentation-only boundaries are amended only for this version.

The actual source reviewed is [Computation_Updated_HI_SI_ES_PA_HM.docx](../../EWAF_Computation_Download/Computation_Updated_HI_SI_ES_PA_HM.docx), SHA-256 `b8b2af991278a19f2a42bce7e84100d06ae86541f691372cc715415c0002d6eb`. Its paragraphs, all 16 numbered tables, equation text and final revision record were extracted directly from OOXML. No rounded table cell is used as a calculation input. Source layout was not rendered: LibreOffice was unavailable. No source document was changed. The older computation is historical context, not the new engine's authority.

Other reviewed authorities: `../CURRENT_SYSTEM_SPECIFICATION.md`, `../Guide for Development.md`, current Open Decisions, October 10 Implementation Impact, the integrated specification §8 and Brainstorm integration log, operational-closure October 24 report, Phase 3 evidence-integration limitations, Phase 5 preservation evidence, household-criteria/Vault/one-click reports and October 25 adjustable-weight validation. Later source code was inspected rather than treating older migration-status reports as a current database inventory.

The checkout is `feature/events`, HEAD `776cac5d1119410717c6a31c044ea85f4d619941`, with substantial existing dirty/untracked work. `baseline.json` identifies the actual pre-implementation files and status. Its earlier protection-manifest comparison already differed at the root and runtime Vault templates before this task; those differences are not attributed to this implementation.

## Method and numerical contract

Method identifier: `ewaf-hi-si-es-pa-hm-dataset-v1`. Normalization identifier: `dataset-minmax-v1`. Order is always **HI, SI, ES, PA, HM**. HM means household members; historical ND is never renamed. Program Relevance remains outside this sum and must retain applicable eligibility treatment.

All arithmetic uses Python `Fraction`: exact rationals for column sums, normalized matrix, row-average weights, WSV, CV, estimated λ, CI, CR, bounds, normalized inputs, contributions, scores, classifications and ties. Finite decimal inputs are exact rational values. Binary floats, nonfinite numbers and unbounded numeric representations are rejected. Resource limits (160 input characters/512 bits; 2,000 pool rows) are engineering safeguards, not scoring bounds. No input clipping occurs. Decimal explanations use a local 50-significant-digit context; display uses exact half-even rounding to two places. Comparison and reciprocity tolerance is **zero**. Display decimals never enter arithmetic or tie decisions.

The AHP function accepts a five-by-five positive exactly reciprocal matrix with diagonal ones and derives column-normalized row averages. It retains the actual matrix, column sums, normalized matrix, weights, WSV, CV, λ estimate, CI, RI = 1.12, CR and pass/fail result. Consistency requires `0 <= CR < 0.10`; failed diagnostics are not an authorization. No principal-eigenvector substitution or negative-CI clamping is used.

The document example alone reconstructs `A[i,j] = q[i]/q[j]`, with exact q = `(0.3421, 0.2360, 0.1774, 0.1223, 0.1222)`. Its required label is **Illustrative reconstructed matrix.** CR = 0 follows by construction. It is not an independently elicited or institutionally authorized comparison matrix. Configuration construction performs AHP before applicant iteration; scores do not recalculate AHP per applicant. Replay validates the stored configuration once per run.

## Adjustable draft weights

HI, SI, ES and PA have independent numeric/slider controls, in 0.01 percentage-point increments. HM = `100 − HI − SI − ES − PA`. Other controls never move automatically. Browser code uses integer basis points; the server independently validates the proposal.

| Control | Supplied range | Effective maximum at other example defaults |
| --- | --- | --- |
| HI | 26.40–62.55% | 46.43% |
| SI | 19.48–34.21% | 34.21% |
| ES | 14.07–23.60% | 23.60% |
| PA | 12.23–17.74% | 17.74% |

Each slider's effective maximum is `min(supplied maximum, 100 − sum(other three))`. Invalid numeric entries remain visible with an explanation; submission is blocked and the server also rejects them. Setting HI to 40 at other defaults leaves SI/ES/PA unchanged and gives HM 6.43%. HI 62.55 plus the other minima gives HM **−8.33%** and is rejected.

The arithmetic HM envelope is 0–27.82%; this is **not an approved HM policy range**. HI can reach 54.22 only with the other three at their minima and HM zero. Zero HM is available only as an explicitly labeled sensitivity endpoint; it cannot satisfy a positive-weight AHP configuration. No approved HM minimum/maximum is invented.

Manual proposals retain their percentages exactly and have no AHP matrix, CI or CR. Even manually choosing the default percentages retains manual provenance. No slider-to-ratio or discrete-Saaty projection exists in this version. The existing Vault/cascade editor and its operational semantics are preserved separately. Real use requires actual recorded authorized pairwise judgments or a separately recorded weighting-method decision.

## Accepted inputs and frozen pools

The computational adapter accepts a complete synthetic eligible inventory, all five values per applicant, explicit source type, evidence identity/version, acceptance status, period, acceptance time and cutoff. Missing, unaccepted, disputed, stale, invalid, expired or late-accepted input blocks the whole pool. Missing input never becomes zero. Unresolved in-scope applicants block; a caller cannot trim supplied expected membership to match a filtered row page. The snapshot is immutable canonical JSON with a digest. A corrected pool creates a new version; all bounds and scores are derived together. Source/correction adoption for real members is not implemented by this synthetic adapter.

The source ES mapping is Full-Time Worker 1, Part-Time Worker 2, Seasonal Worker 3, Unemployed 4. Other categories are rejected. Raw ES categories and numeric encodings remain distinct. SI's document numbers 4/3/1 are explicit synthetic assumptions; 4Ps and document counts supply no numerical mapping. PA counts represent only qualifying confirmed non-voided actual releases under an approved future scope/period, never selection, applications, tickets or attendance. The synthetic fixture does not query any release ledger or member profile.

The existing evidence services, registered-input acceptance, membership reviews and assistance-release writers were inspected. The existing Vault's SI uses a 4Ps category and therefore cannot be adopted as the new numerical-SI handoff. No raw profile fallback, re-acceptance by a review note, or new accepted-evidence writer was added. Official readiness explicitly blocks this absent version-aware handoff.

For every column, L and U come from the same complete frozen pool. HI/PA use inverse normalization; SI/ES/HM increase, as disclosed demonstration assumptions. A constant column (`U == L`) stops the calculation, including a single-applicant pool. There is no epsilon, imputation, criterion deletion, fixed cap or reweighting. Existing fixed-bound engines remain unchanged.

`EWS = sum(weight * normalized)` and `EWS100 = 100 * EWS`. Percentage-point contributions are not multiplied by 100 again. Optional demonstration bands classify the exact score: High [80,100], Moderate [60,80), Low [40,60), Minimal [0,40). Official bands require separate approval; classification is not required for ordering.

## Added ranking convention and workflow

The document specifies scores/classifications, **not numerical ranks**. The owner's prompt adds exact competition rank: `1 + count(strictly greater scores)`. Equal scores share rank and a visible tie group; gaps are retained (1,2,2,4). Stable input order within a tie is presentation only. A tie crossing an example capacity boundary is flagged; no winner, selection or release is generated. There is no score input, rank override or drag ordering.

The private route is `/ewaf/revised/`, within the existing EWAF & Selection group. The method tab is separate from operational programs and the Vault. It offers the document example and draft sensitivity, readiness blockers, exact calculation detail, optional example capacity/classifications and a program context for retained synthetic history. A program context never enrolls its real applications. Missing new tables disables retention/history without attempting migrations; transient synthetic preview remains available to authorized users.

Four new permissions control view/history, calculation/retention, review and private export. They are additional to existing dashboard, operational EWAF and evidence-view permissions. No grants are made. Fresh permission checks, existing program terms locks, stale tokens and existing append-only evidence guards are reused. Mandatory atomic audits use the same `admin.LogEntry` channel as the Vault, scoped to the new preview model content types. Preview actions deliberately do not append ProgramLog source events: those would falsely invalidate existing operational evaluations. A dedicated regression checks that retention, review and export preserve an active old run's freshness, human decision and publication projection. Reviews say Reviewed demonstration or Corrections requested; neither authorizes a configuration. JSON retains the full record; CSV/Excel reuse existing safe private export serializers and include exact per-criterion breakdowns and synthetic labels. Exports audit before returning data and reject audit failure.

Retained runs store method, program, mode, immutable configuration/provenance/matrix/weights, frozen pool and evidence versions/cutoff, shared bounds/directions, exact intermediate results, precision/ranking conventions, example capacity, actor/time/reason, source context, request identity, digest, audit and predecessor. Reviews bind the exact run digest with their own actor/time/reason/predecessor. Supported source-context changes invalidate current review use without modifying history or automatically calculating/publishing. Since all retained inputs are synthetic, real member corrections have no dependency to invalidate here; official use is blocked until its accepted-evidence and invalidation integration exists.

## Schema and preservation boundary

`ewaf.0011_revised_dataset_preview` adds only `RevisedPreviewRun` and `RevisedPreviewReview`, six constraints and four permission definitions. Dependencies: `ewaf.0010_shared_configuration_vault`, `programs.0005_approved_terms`, `admin.0003_logentry_add_action_flag_choices` and the swappable staff user. Existing tables are referenced with PROTECT; no data migration, existing-field change or backfill is present. This is a reviewed source addition tested on model-synchronized disposable MySQL, not a working-target migration approval or faithful deployment-history rehearsal.

The only existing source touchpoints are the new model import in `ewaf/models.py`, three private routes in `ewaf/urls.py`, and a permission-controlled tab in `templates/ewaf/tabs.html`. No operational engine dispatch, old math, evidence writer, approval, selection, publication, release, startup guard, credentials, activation settings or existing migration is changed. No code is copied to the running runtime and no working database is accessed by this task.

Official scoring remains blocked for missing numerical SI rubric, weight authorization, accepted-evidence handoff, income/household and PA definitions/periods, category/direction/pool policy, recorded ranking/tie procedure, versioned configuration authority and operational enablement. Those are real policy/integration dependencies, not reasons to withhold the independent synthetic implementation.
