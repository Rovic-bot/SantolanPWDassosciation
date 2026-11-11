# Shared scoring policy draft for HI SI ES PA HM

**Version:** `HI-SI-ES-PA-HM-DRAFT-001`\
**Status:** Draft for review. No institutional approval or activation.\
**Scope:** New method `ewaf-hi-si-es-pa-hm-dataset-v1` only.\
**Policy identifier:** `shared-hi-si-es-pa-hm`\
**Prepared:** 25 October 2026

This draft defines a shared policy for the new five-criterion EWAF method. It separates rules found in the revised computation document from new choices proposed for review. It also separates policy readiness from applicant-data readiness. Programs cannot use this draft for official scoring or publication as an approved policy.

The [machine-readable draft](../../ewaf/revised/policies/shared-v1-draft-1.json) is the versioned source for the accompanying synthetic checks. Its authorization and weight-authorization reference are both empty. Nothing in this draft reapproves weights, creates an approval record, or changes an existing program.

## Source and provenance

Source: [Computation Updated HI SI ES PA HM](../../EWAF_Computation_Download/Computation_Updated_HI_SI_ES_PA_HM.docx), SHA-256 `b8b2af991278a19f2a42bce7e84100d06ae86541f691372cc715415c0002d6eb`.

The original DOCX remains unchanged. A fresh [paragraph and table extraction](source-extraction.txt) records its text and equations. `P` references below identify body paragraphs in that extraction. The document contains 19 XML tables, of which 16 have numbered captions; numbered Table 9, for example, is XML table 11. Source layout was not rendered because this work concerns calculation content and does not edit the DOCX.

The document expressly describes its inverse HI/PA directions, weights and SI example inputs as demonstration assumptions. Including them in this draft makes their provenance visible; it does not establish prior Association approval. The current owner instruction authorizes preparing and testing this draft, while keeping official scoring blocked.

## Rules populated from the document

| Item | Draft rule | Source and qualification |
| --- | --- | --- |
| Criteria | Household Monthly Income, Socioeconomic Indicator, Employment Status, Previous Assistance Received, Number of Household Members, in HI/SI/ES/PA/HM order | Source criterion table; HM does not replace historical Number of Dependents. Program relevance stays outside this weighted sum. |
| ES encoding | Full-Time Worker = 1; Part-Time Worker = 2; Seasonal Worker = 3; Unemployed = 4 | Numbered Table 9, P70–74. Other categories remain unresolved. |
| Normalization | Min–Max using the complete accepted eligible dataset for the evaluation | P81–107. The actual minimum and maximum are calculated at evaluation time, shared by every applicant in that run. |
| Directions | HI and PA inverse; SI, ES and HM increasing | P84–91 and numbered Table 12. These are the example's disclosed directions, proposed for operational adoption. |
| Increasing formula | `z = (x − minimum) / (maximum − minimum)` | P83. |
| Inverse formula | `z = (maximum − x) / (maximum − minimum)` | P86–87. The source calls this an explicit example extension. |
| Weighted sum | `EWS = Σ(weight × normalized value)` | P110–114. Decimal weights sum to 1. |
| Presentation | `EWS100 = 100 × EWS`, with full precision retained internally | Multiply by 100 once. Percentage-point contributions already produce the 0–100 result. |
| Missing, stale or disputed information | Stop a usable calculation; unknown is not zero | P74, P76–78 and P103–106. Do not infer accepted EWAF evidence from registration approval. |
| Constant columns | Stop pending an authorized constant-column rule | P103. This is the current protective behavior, not adoption of a final scoring convention. |
| Pool changes and history | Recompute the shared bounds and all affected results from a new accepted pool snapshot; retain the previous run | P105, P143–144. Never overwrite a score or rank manually. |
| Selection and release | Ranking supports a separate human decision; selection and actual assistance delivery remain separate | P132–144. No automatic beneficiary approval. |

The draft does **not** contain fixed numerical bounds for HI, SI, ES, PA or HM. The example's minima and maxima are demonstration outputs, not pre-application limits or poverty thresholds. A proposed SI rubric or an ES category encoding is a measurement scale; it does not replace the dataset-derived normalization bounds.

## Proposed choices for review

Every choice in this section is **proposed and not authorized**. The DOCX does not supply these institutional rules.

### Proposed SI assessment

Use a documented assessment of barriers to essential needs across three proposed domains: food access; stable housing and essential utilities; and access to necessary care and daily support. An authorized assessor would record the supported level and evidence, rather than the system inferring a score from a member's documents.

| Proposed SI value | Proposed assessment finding |
| --- | --- |
| 1 | Accepted assessment confirms no unmet barrier in the listed domains during the assessment period. |
| 2 | Occasional shortfall in at least one domain, without a recurrent or current critical barrier. |
| 3 | Recurrent unmet barrier in one domain, without a current critical barrier or recurrent barriers in two domains. |
| 4 | Current critical unmet barrier in any domain, or recurrent unmet barriers in at least two domains. |

Consider levels 4, 3, 2, then 1, choosing the highest supported level. Missing or disputed assessment has **no assigned level**. Before adoption, the Association must define “occasional,” “recurrent” and “critical,” validate the domains and levels, and determine assessor qualifications, consistency review and correction procedures. Reviewers may replace this proposal with an appropriate established assessment instrument.

Do not award points for 4Ps membership, the number of documents, disability labels, or the raw HI/ES/HM/PA values. Supporting documents and optional 4Ps information may support an assessment; they are not automatic numerical mappings. This proposal requires review for overlap with the other criteria.

### Proposed assessment periods

Use a monthly income average over the three complete calendar months before application closing. Assess SI over the same period plus current barriers at a common, timezone-aware evaluation cutoff. Use accepted ES and household composition at that cutoff. Freeze the cutoff and evidence versions with the pool.

This is a proposed period definition only. Income inclusions, gross/net basis, seasonal or irregular income, evidence validity, changing employment and post-closing corrections remain explicit review decisions. Evidence unavailable at the cutoff cannot silently receive a default value.

### Proposed household definition

Count the applicant and people who usually share the same dwelling and food or essential-expense budget. This is a household count, not a count of dependents. Review must define usual residence and address temporary absence, shared housing with separate budgets, split households, caregivers, boarders and institutional living.

### Proposed previous assistance scope

Count qualifying confirmed, non-voided actual releases across Association programs during the 12 calendar months ending at the common evaluation cutoff. Proposed boundaries include both the cutoff shifted back 12 calendar months and the cutoff itself; month-end and leap-day behavior still requires a recorded rule.

Applications, undelivered selections, referral tickets, event attendance and voided releases do not count as actual assistance. Review must decide installments, duplicate records, external assistance, imports and the unit represented by one release. Absence of database rows does not by itself prove zero previous assistance. Incomplete historical coverage remains unresolved input.

### Proposed ranking convention

Rank descending by the exact score, using competition ranks such as **1, 2, 2, 4**. Equal exact scores share a rank and tie group. Rounded display values do not decide equality. At a capacity-boundary tie, hold the unresolved group for an authorized human procedure; name, reference, submission time and database order do not secretly choose a winner.

This convention is a proposal already supported by the separate synthetic engine; it is not a ranking convention established by the DOCX. Selection remains a separate authorized record within the applicable slots. No public rank disclosure is authorized here.

## Decisions that remain open

| Decision | Required resolution |
| --- | --- |
| Document rule adoption | Adopt or revise the ES mapping, dataset method, disclosed directions and weighted sum for the new operational version. |
| SI assessment authority | Identify who can adopt the rubric and approve assessor qualifications, operational definitions, evidence, calibration and correction procedures. |
| Constant-value columns | Decide the treatment of `maximum = minimum`, including a one-person pool. Zero, one, midpoint substitution, removing the criterion and redistributing weights are all unadopted. |
| Income sources | Define gross/net basis and treatment of wages, self-employment, irregular work, pensions, remittances, benefits, one-off transfers, in-kind income, exclusions, duplicate amounts and zero/negative adjustments. |
| Unlisted employment | Define self-employment, informal work, retirement, students, unpaid caregiving, inability to work, multiple jobs and changes of category. Do not default to unemployed. |
| Evidence | Specify accepted documents/declarations and accessible alternatives, reviewer authority, freshness, disputes, rejection, unavailable evidence and re-review. |
| Incomplete history | Specify proof of PA coverage, missing legacy/external history and the evidence needed for a genuine zero count. |
| Assessment periods | Adopt or replace the proposed periods, averaging, cutoff, date boundaries and treatment of post-closing changes. |
| Household definition | Adopt the definition and decide ambiguous living arrangements and changes in composition. |
| PA scope and release units | Adopt scope/window, deduplication, installments, imported/external data and calendar boundary rules. |
| Ranking and ties | Adopt competition ranking and the authorized human capacity-boundary procedure. |
| Complete pool and corrections | Define evaluation closure, complete eligible inventory, unresolved cases, late changes, full-pool recalculation and handling of already selected or published cases. |
| Weight authority | Identify the immutable, authorized weighting-method/version applicable to this new engine. Existing source/weight-only approvals and reconstructed example matrices do not establish this authority. This task does not reapprove them. |
| Precision and classifications | Review exact-rational comparisons and half-even two-decimal display; explicitly omit or separately authorize classifications. Example bands remain inactive in this draft demonstration. |
| Policy authority and effectivity | Identify institutional approver, scope, effective dates, required audit evidence and explicit adoption/rebinding rules. |

## Two separate readiness checks

**Policy readiness occurs before operational adoption.** The complete policy must define the measurement and evidence rules, mappings, dataset method/directions, edge cases, ranking, weight reference, authority and effective scope. It does not require knowing the future applicant minima and maxima. All unresolved policy decisions and missing authority remain blockers in this draft.

**Applicant-data readiness occurs at evaluation.** Freeze the complete accepted eligible inventory and common cutoff. Retain evidence identities and versions, acceptance/dispute/freshness state, and PA history-coverage assessment. After validating that complete pool, derive each criterion's minimum and maximum. A missing, disputed or stale input, an unresolved in-scope applicant, or an unhandled constant column blocks a usable run. This does not automatically declare a person ineligible.

A policy can therefore be reviewed while applicant data is **not yet evaluated**. A synthetic dataset can be arithmetically ready while the policy remains **unapproved**. Official scoring requires both checks plus operational evidence integration and a valid approved-version binding. The current publication guard remains active because the applicable policy is incomplete; absence of future numerical bounds is not the reason to invent fixed limits.

## Immutable policy versions and program links

1. Retain each draft revision with its policy ID, revision, content digest and predecessor digest. A correction creates a new snapshot; it does not overwrite a retained revision.
2. After complete applicable policy authorization, a separate audited approval service must retain an immutable approved version and its authority, scope and effectivity. This draft implementation has no approval operation and creates no approval records.
3. A program using the **new** engine must bind the exact approved policy ID, revision and content digest, together with its authorized weight-version reference. A draft, a status flag supplied by a client, or a mutable “latest policy” pointer cannot supply this binding.
4. A later shared draft or approved version must not automatically rebind an existing program. Any permitted rebind requires its own authorized, audited version and the adopted correction/recalculation process. Earlier links remain retained.
5. Each run retains its bound policy and weights, frozen pool and evidence versions, cutoff, derived bounds, directions, exact traces and separate human decisions. Replaying a run uses those snapshots rather than the current shared draft.

No approved policy exists for this draft, so **no program is assigned to it**. Persistent approved-version storage/binding and accepted-evidence integration are prerequisites for later operational activation. The official-readiness service now names the required immutable program binding explicitly, while retaining every existing blocker. Existing four-criterion, fixed-bound, Vault and historical calculations remain under their original contracts.

## Synthetic demonstration

The [retained demonstration](synthetic-demonstration.json) uses the DOCX's unchanged example weights and three fictional applicants. It does not approve those weights. SI values 4, 3 and 1 are the document's assumed inputs; the new proposed SI rubric is **not** claimed to have produced them. Synthetic PA history is explicitly marked as an assumption. Classifications are omitted.

| Fictional applicant | Exact score out of 100 | Display | Proposed competition rank |
| --- | --- | --- | --- |
| A | 839/10 | 83.90 | 1 |
| B | 7537/120 | 62.81 | 2 |
| C | 611/50 | 12.22 | 3 |

Derived bounds for this complete example pool are HI 5,000–20,000; SI 1–4; ES 1–4; PA 0–3; HM 2–6. They belong to this run alone. Changing the synthetic maximum income to 30,000 recomputes shared bounds and affected results while the earlier snapshot still replays exactly.

Tests cover constant columns, a single-person pool, missing/stale/disputed inputs, unlisted employment, incomplete history, filtered/unresolved pools, exact ties, forged approval metadata, stale draft edits, tampered retained content and preservation of earlier results. [Validation evidence](validation.md) records the executed checks and remaining integration limits.
