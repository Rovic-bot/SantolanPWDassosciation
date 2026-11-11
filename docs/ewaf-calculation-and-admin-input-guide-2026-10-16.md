# EWAF calculation: member data and Admin inputs

Prepared: October 16, 2026. Based on the October 10 target specification, the computation workbook, and the current repository.

**EWAF uses five reviewed inputs: previous assistance received (PA), socioeconomic indicator (SI), employment status (ES), number of dependents (ND), and program relevance (PR).** Admin verifies these inputs and records the program's calculation rules. The system derives criterion weights, normalizes the accepted values, and calculates an Equity Weighted Score (EWS) from 0 to 100.

**Current availability:** evidence review, configuration drafts, AHP reference validation, and score-free applicant readiness diagnostics exist. Numerical scoring, ranking, and recalculation demonstrations use synthetic fixtures. Accepted live applicant scoring/ranking and EWAF-based beneficiary selection remain unavailable. This guide explains the calculation and intended operational inputs; it does not activate that workflow or approve sample policies. The recorded milestone remains 70%.

## 1. What information should come from PWD members?

The unit being assessed is **a member's application to one particular program**. There should not be one permanent EWAF score attached to a member across all programs.

| Criterion | Information needed | Source and Admin responsibility | What enters the calculation |
| --- | --- | --- | --- |
| **PA — Previous Assistance Received** | Confirmed assistance actually received within the approved scope and time window | Derive from successful, non-voided release records. Admin checks the receipt history, relevant program/assistance types, observation period, and cutoff. | A verified release count under that policy. The workbook uses a count, not total pesos received. |
| **SI — Socioeconomic Indicator** | The program's approved socioeconomic measure. The workbook example uses monthly income. | Reuse relevant member information and review its evidence/currentness. If using income, define individual versus household income, period, currency, and gross/net basis before comparison. | The accepted income amount, or a value from a separately approved socioeconomic assessment. |
| **ES — Employment Status** | Current employment situation and applicable observation period | Review recorded employment information and map it to a defined category using approved evidence and category rules. | The category's approved numeric code. Free-text employment information is not itself a number. |
| **ND — Number of Dependents** | Number of people who meet the program's approved definition of a dependent | Reuse the member's recorded count, check currentness, and review evidence under the approved counting rules. | A verified nonnegative whole-number count. |
| **PR — Program Relevance** | Evidence of how the application meets the program's relevance rubric | Admin records findings against specific rubric items and supporting sources. The applicant provides relevant facts; Admin assesses them under the rubric. | The approved category/code resulting from those findings. |

The existing member profile contains `monthly_income`, `employment_information`, and `dependents`. These are starting sources, **not automatic proof that their values are verified or suitable for every program**. PA comes from release history. PR is assessed for the particular program rather than copied as a universal member attribute.

Do not ask the applicant to re-enter information or upload the same document when current, relevant, verified internal evidence can be reused. Request missing or outdated information through the authorized review/correction process.

### Identity and eligibility data are separate

Control number, name, birthdate, and contact number support secure membership matching. Membership status, mandatory program qualifications, and required identity/document review determine whether an application is eligible for assessment. They do not become additional EWAF score terms.

Disability type and medical severity must not be scored by EWAF. A program may use protected disability information only for an explicitly approved, relevant mandatory qualification. Photos, government ID numbers, addresses, names, and application references do not add points.

### What evidence should the member provide?

There is **no approved universal EWAF document checklist** in the current requirements. Each program needs an approved evidence policy for SI, ES, ND, and PR, including accessible assessment alternatives where authorized. PA uses actual receipt records. Do not invent mandatory income certificates, employment certificates, or other uploads solely from this guide.

For each criterion, retain its source/reference, value and unit, observation period where relevant, assessment state, reviewer, review time, and explanation. The evidence states are **Declared, Needs Review, Verified, and Rejected**.

A declaration alone is not verified. Missing or disputed information must not be silently converted to zero, maximum need, or a midpoint. Missing evidence can block scoring while correction is requested; it does not automatically prove ineligibility.

## 2. What should Admin input?

There are two different tasks: defining the rules for the program, and reviewing each applicant's facts.

### A. Program configuration — once per approved version

The target requires the complete configuration to be approved and locked **before applications open**. These are the required policy inputs for future operational use, not a claim that every field is available in today's interface.

| Admin supplies or references | What must be recorded |
| --- | --- |
| Program and selection method | Program identity, whether EWAF applies, method description, and available slots. Slots constrain later selection; they are not a scoring multiplier. |
| Criterion definitions | PA, SI, ES, ND, PR definitions, units, measurement periods, evidence requirements, and assessment responsibilities. Substantive criterion changes need separate authorization. |
| Category mappings | ES category-to-number mapping and PR rubric/category-to-number mapping. If SI uses another approved measure, its measurement/mapping rules too. |
| PA measurement policy | Which actual receipts count, assistance/program scope, time window, cutoff, and treatment of relevant history corrections. |
| AHP pairwise judgments | Relative importance of each pair of criteria. Five criteria require **10 independent comparisons**. The system generates reciprocals and derives weights. |
| Normalization rules | Direction for each criterion, lower/upper bounds, and the source of those bounds: approved fixed references or an explicitly defined eligible-pool method. |
| Exceptional input handling | Missing/unverified data, equal bounds, values outside bounds, unknown categories, and stale evidence. No silent fallback is approved. |
| Result interpretation | Precision/display rules, ranking order and true-tie handling, classification thresholds/endpoints if used, and any approved waitlist policy. |
| Governance | Configuration version, documentary authority, approval/effective date, authorized approver, reasons, revision rules, and retained history. |

**Admin enters judgments, not the final weight percentages.** For example, an SI-to-ES judgment of `2` means SI is judged twice as important as ES. The reverse comparison must be `1/2`. These judgments describe program priorities, not the circumstances of an individual applicant.

The ten comparison pairs in the current draft form are:

`SI:ES`, `SI:PA`, `SI:ND`, `SI:PR`, `ES:PA`, `ES:ND`, `ES:PR`, `PA:ND`, `PA:PR`, `ND:PR`.

### B. Per-applicant review — facts and findings

| Admin reviews/records | Example for understanding only |
| --- | --- |
| Program and application | The specific program application being assessed |
| SI source and reviewed value | Monthly income of PHP 8,000, with the approved income basis and period |
| ES finding | Seasonal Worker; the illustrative workbook mapping gives code 3 |
| PA source history | One confirmed non-voided receipt within the defined scope/window |
| ND source and count | Two dependents under the approved definition |
| PR rubric finding | Highly Aligned; the illustrative workbook mapping gives code 3 |
| Evidence and assessment | Source references, verification findings, relevant observation dates, and reasons |
| Readiness | Current eligibility, completed criterion assessment, current sources, and the correct configuration version |

These example values are fictional workbook data. They must not be entered into a real member's record to make the calculation work.

### C. What the system calculates

The system derives column totals, normalized AHP matrix, weights, consistency results, encoded values under approved mappings, applicant normalized values, weighted contributions, total EWS, and eventually program ranking under an approved policy.

Admin must not enter or overwrite a desired final score, manually move an applicant's rank, assign a hidden bonus, or alter PA through a free-form counter. Correct erroneous source records through the authorized, reasoned correction workflow. Future operational recalculation must retain old results and recalculate the entire affected eligible pool consistently.

## 3. How the calculation works

```text
Program definitions and AHP judgments
    -> derive weights and check consistency
    -> authorize and lock the complete configuration
    -> review eligible applicants' criterion evidence
    -> encode accepted categories
    -> normalize each criterion to 0–1
    -> multiply normalized values by weights and add
    -> multiply by 100 to obtain EWS
    -> apply approved classification/ranking rules
    -> separate, authorized human selection within slots
```

There are **two different normalization steps**: AHP column normalization determines the weights; applicant Min–Max normalization scales the member data.

### Step 1. Derive weights with AHP

For readability, this guide uses **SI, ES, PA, ND, PR** order, matching the current diagnostic draft form. The workbook uses **PA, SI, ES, ND, PR**. Always match criterion IDs to their weights and values. Reorder both matrix rows and columns when changing presentation order.

This is the workbook's example matrix, reordered consistently. **It is a mathematical reference, not a universal approved program configuration.**

| Row compared with column | SI | ES | PA | ND | PR |
| --- | ---: | ---: | ---: | ---: | ---: |
| SI | 1 | 2 | 3 | 5 | 3 |
| ES | 1/2 | 1 | 2 | 4 | 2 |
| PA | 1/3 | 1/2 | 1 | 3 | 2 |
| ND | 1/5 | 1/4 | 1/3 | 1 | 1/2 |
| PR | 1/3 | 1/2 | 1/2 | 2 | 1 |
| **Column total** | **2.366666667** | **4.25** | **6.833333333** | **15** | **8.5** |

For each matrix cell and each criterion row:

```text
Normalized matrix cell = original cell / its column total
Criterion weight = sum of that row's normalized cells / 5
```

For example:

```text
SI weight = [(1 / 2.366666...) + (2 / 4.25) + (3 / 6.833333...)
             + (5 / 15) + (3 / 8.5)] / 5
          ≈ 0.4036844693219094
```

| Criterion | Derived reference weight, approximately | Display percentage |
| --- | ---: | ---: |
| SI | 0.4036844693219094 | 40.3684% |
| ES | 0.2482410868847711 | 24.8241% |
| PA | 0.1680255420615515 | 16.8026% |
| ND | 0.0635202511097191 | 6.3520% |
| PR | 0.1165286506220489 | 11.6529% |
| **Total** | **1, before display rounding** | **100%** |

A larger weight gives a criterion more influence. These weights apply to every applicant assessed under that same configuration version.

### Step 2. Check the judgments for consistency

Let `A` be the original matrix, `w` the derived weight vector, and `n = 5`:

```text
Weighted sum vector: WSV[i] = sum(A[i,j] × w[j])
Consistency vector: CV[i] = WSV[i] / w[i]
lambda_max = average(CV)
Consistency Index: CI = (lambda_max − n) / (n − 1)
Consistency Ratio: CR = CI / RI
```

For the sample: `lambda_max ≈ 5.0798617324`, `CI ≈ 0.0199654331`, and the workbook's `RI(5) = 1.12`. Therefore, `CR ≈ 0.0178262795`, below the reference threshold `0.10`.

This passes the mathematical reference check. It does not establish that the criteria or judgments are institutionally approved or fair. Inconsistent judgments need review; Admin must not adjust calculated weights directly to force a pass.

### Step 3. Encode the reviewed applicant data

The workbook's illustrative mappings are:

| Employment category | ES code | Program relevance category | PR code |
| --- | ---: | --- | ---: |
| Full-Time Worker | 1 | Not Aligned | 1 |
| Part-Time Worker | 2 | Partially Aligned | 2 |
| Seasonal Worker | 3 | Highly Aligned | 3 |
| Unemployed | 4 | Fully Aligned | 4 |

These definitions and codes need program approval before real use. Do not infer mappings for categories such as retired, self-employed, or student. PR needs evidence-based rubric findings, not a discretionary score chosen by Admin. Eligibility must already have been established separately.

### Step 4. Normalize the applicant values to 0–1

Let `x` be the accepted value, `L` the lower bound, and `U` the upper bound:

```text
Ascending / benefit: N = (x − L) / (U − L)
Descending / inverse: N = (U − x) / (U − L)
```

Ascending makes larger values contribute more. Descending makes smaller values contribute more. Valid in-range values produce results from 0 to 1 when `U > L`.

**The actual workbook uses ascending normalization for both income and previous assistance. This means higher income and more previous receipts increase the sample score.** The association still needs to approve the intended directions (OQ-18 and OQ-19). An inverse rule would behave differently, but this guide does not adopt it.

The sample minimum and maximum values are illustrative. They are not approved income limits, dependent caps, receipt limits, or automatic pool-derived bounds. Equal bounds cause division by zero; missing/out-of-range inputs and equal bounds require the approved policy, not an invented adjustment.

### Step 5. Calculate the weighted sum and EWS

```text
Contribution for a criterion = weight × normalized value

EWS (0–1) = (wSI × SI_normalized) + (wES × ES_normalized)
          + (wPA × PA_normalized) + (wND × ND_normalized)
          + (wPR × PR_normalized)

EWS (0–100) = 100 × EWS (0–1)
```

Use full calculation precision internally. Round only the displayed result; do not feed display-rounded weights or scores into subsequent calculations or ranking.

## 4. Worked example from the workbook

This reproduces the fictional Member B example **using the workbook's actual ascending directions**, including the unresolved SI/PA directions. It demonstrates arithmetic, not approved beneficiary policy.

| Criterion | Accepted example value | Example lower bound | Example upper bound | Normalization | Result |
| --- | ---: | ---: | ---: | --- | ---: |
| SI | PHP 8,000/month | PHP 5,000 | PHP 20,000 | `(8000 − 5000) / (20000 − 5000)` | 0.2 |
| ES | 3 — Seasonal Worker | 1 | 4 | `(3 − 1) / (4 − 1)` | 0.6666666667 |
| PA | 1 receipt | 0 | 3 | `(1 − 0) / (3 − 0)` | 0.3333333333 |
| ND | 2 dependents | 0 | 5 | `(2 − 0) / (5 − 0)` | 0.4 |
| PR | 3 — Highly Aligned | 1 | 4 | `(3 − 1) / (4 − 1)` | 0.6666666667 |

Multiply each normalized value by the corresponding derived weight:

| Criterion | Weight, rounded here for display | Normalized value | Contribution, approximately |
| --- | ---: | ---: | ---: |
| SI | 0.4036844693 | 0.2 | 0.0807368939 |
| ES | 0.2482410869 | 0.6666666667 | 0.1654940579 |
| PA | 0.1680255421 | 0.3333333333 | 0.0560085140 |
| ND | 0.0635202511 | 0.4 | 0.0254081004 |
| PR | 0.1165286506 | 0.6666666667 | 0.0776857671 |
| **Total EWS (0–1)** | | | **0.4053333333** |

```text
EWS = 0.4053333333333333 × 100
    = 40.53333333333333

Displayed result: 40.53 / 100
```

The workbook's `H86` stores approximately `0.4053333333333332`. That is the **0–1** score. Multiply by 100 once to present the **0–100** score.

### Classification and ranking after scoring

The workbook prints these provisional labels:

| Printed EWS range | Workbook label |
| --- | --- |
| 80–100 | High Assistance Need |
| 60–79.99 | Moderate Assistance Need |
| 40–59.99 | Low Assistance Need |
| 0–39.99 | Minimal Assistance Need |

The example falls in the printed Low Assistance Need range. **These labels, thresholds, and exact endpoints remain pending approval (OQ-25).** Values such as `59.995` illustrate why printed two-decimal upper bounds do not define a complete full-precision policy. Do not round a score merely to force it into a band.

The target ranks eligible applications within the same program, highest EWS first under the approved method. A single example score cannot establish a rank without the complete comparable pool. Preserve true ties and use a separately approved tie/selection policy; internal IDs and submission order are not default tie-breakers.

Eligibility, need classification, rank, human selection, and actual assistance release remain distinct. A score of 40.53 is neither a pass/fail result nor a guarantee of assistance. Admin records the later authorized selection within available slots without overwriting the score/rank. PA changes only when actual assistance is recorded under its receipt policy, not merely when someone applies or is selected.

## 5. What can Admin enter in the current app?

| Current screen/workflow | Actual input or action | Current limit |
| --- | --- | --- |
| **Applications & Verification → Criterion evidence & readiness** | Select an application and criterion. Record the permitted evidence state, source type, supporting review IDs, relevant observation dates, dispute status, review explanation, and confirmation. PR additionally supports rubric-item findings and attestation. | Evidence/readiness review does not calculate an applicant's score or authorize processing. |
| **Record evidence policy definitions** | Documentary authority reference and supported JSON definitions for the five criteria, with explanation and confirmation. | A recorded policy reference does not establish approval. Definitions need the supported structure; do not invent JSON keys. |
| **EWAF & Selection → Configuration drafts & validation** | Enter ten independent positive decimal comparisons or a full 5×5 matrix in **SI, ES, PA, ND, PR** order. Record the reason and confirmation, then retain reference validation. | Weights and consistency results are diagnostic. The form does not activate a configuration. |
| **Configuration review / non-effective authority evidence** | Review finding, correction requests where needed, or documentary reference, stated scope, and attestation. | These records deliberately do not establish effective authorization. |
| **EWAF & Selection → Scoring-policy diagnostics** | Retain supported policy proposals and applicant readiness diagnostics with the required explanation/confirmation. | Applicant-linked results are score-free. Synthetic numeric examples are separate. |
| **Historical EWAF results / EWAF availability** | Inspect retained historical results and the availability notice. | Historical results are read-only. New operational calculation and EWAF-based selection remain unavailable. |

For profile-based income, employment text, and dependents, the current evidence form can reuse the recorded source value when its value field is blank. Blank here means **reuse the source**, not “score as zero.” If the profile is wrong, correct the source through its authorized workflow. The review form rejects a different value that would silently replace it. Category/assessment findings require an explicit value under the recorded definitions. PA is derived from the applicable source records.

## 6. Checklist before a future live calculation

- [ ] The program has an approved EWAF method and complete, effective, locked configuration.
- [ ] SI measurement/basis and SI/PA directions are approved, not copied from examples.
- [ ] ES categories, dependent definition, PR rubric, and evidence/alternative-assessment rules are approved.
- [ ] PA scope, time window, cutoff, and actual receipt sources are defined.
- [ ] AHP judgments, reference consistency, bounds, edge cases, precision, classification, and tie rules are settled.
- [ ] Every included application is currently eligible and has complete accepted criterion assessments.
- [ ] The same configuration and bound rules apply to the entire affected eligible pool.
- [ ] The operational scoring/ranking and durable recalculation/history features have been implemented and accepted.
- [ ] Authorized human selection remains separate from computed output and respects available slots.

Relevant unresolved decisions are OQ-06–13, OQ-18–19, OQ-23, and OQ-25. Required unresolved rules block live use; completing a mathematical example does not resolve them.

## 7. Source notes and verification

Authority follows the current master and Admin V2 workflow, with the workbook controlling the reference mathematics. Older inverse-income/PA descriptions and the older rounded ES coefficient `0.2483` must not silently replace the current documented source reconciliation.

The workbook was inspected read-only for exact formulas and stored values. A separate rational-arithmetic calculation confirmed the sample weights, consistency ratio, and EWS of `608/15 = 40.533333…`. This was **not Excel recalculation** and did not repair the source workbook.

`Sheet1!C29:C33` contain `AVERAGE(Q10:U10)` through `AVERAGE(Q14:U14)` and stored `#DIV/0!` errors. Downstream weights and other values include disconnected literal copies. Therefore, changing an input in the supplied workbook does not establish that all downstream results update. A functioning engine must derive its outputs from the matrix and accepted inputs.

Sources and implementation evidence:

- [Current System Specification](../../CURRENT_SYSTEM_SPECIFICATION.md), especially EWAF workflow, verification, and selection boundaries.
- [Open Decisions](<../../00 - Project Overview/Open Decisions.md>), active October 10 questions rather than superseded historical resolutions.
- [EWAF Computation Specification](<../../00 - Project Overview/EWAF_Computation_Specification_2026-10-10.md>).
- [Computation - final.xlsx](<../../00 - Project Overview/Computation - final.xlsx>), `Sheet1`: matrix `B2:G7`, reference weights `C58:C62`, normalization `C81:C85`, scoring `F80:H86`, category tables `D79:E88`, and classification `F89:G93`.
- [Workbook Formula and Cache Evidence](<../../00 - Project Overview/Workflow References/2026-10-10/Workbook Formula and Cache Evidence.md>) and [Workflow Source Register](<../../00 - Project Overview/Workflow References/2026-10-10/Workflow Source Register.md>).
- [G12 evidence validation](g12-verified-evidence-validation-2026-10-13.md), [G14 configuration validation](g14-configuration-foundation-validation-2026-10-13.md), and [G15 scoring diagnostics validation](g15-scoring-diagnostics-validation-2026-10-13.md).
- [G16 revalidation](g16-revalidation-2026-10-15.md), [G17 synthetic history validation](g17-recalculation-history-validation-2026-10-15.md), and [operational authorization review](stage8-operational-authorization-review-2026-10-15.md).
- Current source: [member profile](../members/models.py), [evidence forms](../ewaf/evidence_forms.py), [evidence source handling](../ewaf/evidence.py), [configuration forms](../ewaf/configuration_forms.py), and [operational availability views](../ewaf/views.py).

This task creates documentation only. It does not modify application code, member data, configuration, or the original workbook. No Django or browser test suite was rerun for this guide.
