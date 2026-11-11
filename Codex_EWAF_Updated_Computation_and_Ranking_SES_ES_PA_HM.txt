# CODEX — REVISE EWAF TO INCOME-BASED SES / ES / PA / HM

## 1. Task and authority boundary

Use `Computation_Updated_SES_ES_PA_HM.docx` as the NEW revision reference. Keep the supplied five-criterion document and earlier prompts as historical sources; do not overwrite them.

Update the existing versioned calculation/integration architecture for a separate four-criterion method:

- SES — Socioeconomic Status (income-based).
- ES — Employment Status.
- PA — Previous Assistance Received.
- HM — Number of Household Members.

Working interpretation of the requested change: consolidate the former HI scoring contribution and SI supporting-evidence function into a SINGLE income-based SES contribution. Its numerical source is accepted household monthly income in PHP. 4Ps membership, a Certificate of Indigency and other permitted documents support verification; they do not add points or establish a separate numerical SI level.

This is a limited, explicitly defined financial-need measure. Do not describe it as a validated comprehensive socioeconomic index, official poverty classification, or socioeconomic level. A broader composite SES rubric would be a separate policy revision; none is supplied here.

A suggested distinct method identifier is `SES_INCOME_ES_PA_HM_DATASET_V1`. Follow existing identifier conventions, while ensuring this method is not confused with the earlier four-criterion SI/ES/PA/ND method.

Implement the independently safe new-version calculation, evidence mapping, synthetic tests and permission-controlled Admin preview. Reuse existing compatible dataset-policy storage, bindings, ranking and audit services; do not rebuild the whole integration or create a duplicate engine unnecessarily.

This instruction does NOT approve new operating weights, real-data policy, public ranks, automatic beneficiary selection, working/production migrations, deployment, or genuine institutional approval records.

## 2. Read the sources and inspect the actual checkout

Read:

- `Computation_Updated_SES_ES_PA_HM.docx`, including the evidence review and revision record.
- The uploaded prior `Computation_Updated_HI_SI_ES_PA_HM(2).docx` or its retained identical original, for historical comparison only.
- `OVERALL_SYSTEM_SPECIFICATION_INTEGRATED.md` and `BRAINSTORM_INTEGRATION_LOG.md`.
- Current decisions, the latest dataset-policy integration reports, and the current program/publication rules.
- Existing calculation, policy, evidence, approval, selection, release and publication services.

Locate files at their actual paths. If the revised reference is unavailable, report that specific dependency instead of silently using the five-criterion file as the new method.

Inspect the actual branch, worktree, migration history and protection manifest. Preserve unrelated and uncommitted work. Do not infer that a migration is unapplied from an old report or reapply it.

Keep governing source documents and historical policy/runs unchanged. Record the SES amendment in a new versioned contract, not by editing old approved definitions.

## 3. Criterion set, weights and provenance

Use the order SES, ES, PA, HM consistently in matrices, data, traces, tests and internal exports.

| Code | Numerical input | Example direction | Operating weight |
|---|---|---|---|
| SES | Accepted household monthly income in PHP | Lower amount gives higher contribution | New authorization required |
| ES | Accepted employment category encoded by the adopted mapping | Higher encoded value gives higher contribution | New authorization required |
| PA | Count of qualifying confirmed, non-voided actual releases | Fewer releases give higher contribution | New authorization required |
| HM | Accepted household headcount | Larger count gives higher contribution | New authorization required |

No new four-criterion weight vector was supplied.

For arithmetic demonstration ONLY, the revised DOCX uses:

`q_demo = [1/4, 1/4, 1/4, 1/4]`

These equal 25% values are synthetic placeholders selected for demonstration. They are NOT operating defaults, a weighting recommendation, client judgments or approved weights. Do not seed them as approved configuration or silently prefill official approval with them.

Do not:
- Add the old HI and SI percentages and call the result an approved SES weight.
- Drop SI and silently redistribute or renormalize its old weight.
- Reuse or relabel the locked five-criterion version 6 vector as a four-criterion vector.
- Modify old method identities, evidence definitions or results.

Preserve all older contexts: SI/ES/PA/ND, PA/SI/ES/ND/PR, HI/SI/ES/PA/HM, and any other actually retained version.

The criterion count alone is not a version identifier. HM remains distinct from Number of Dependents. Program Relevance remains an applicable eligibility assessment outside this weighted sum, not a removed eligibility requirement.

## 4. Accepted information and evidence review

### SES: income-based assessment

Use a clearly named raw input such as `accepted_household_monthly_income_php`, mapped to criterion SES under this policy version. Keep it distinguishable from `normalized_SES` and `SES_contribution`.

The accepted amount must have its applicable assessment period, cutoff, reviewer, evidence references and acceptance history. Require a finite nonnegative amount; zero is valid only when actually accepted, not used to replace an unknown amount.

The SES normalized value expresses relative financial-need priority within this pool. Higher normalized priority does not mean greater wealth or a higher social class.

### 4Ps and Certificate of Indigency

Keep these as permitted evidence/context records, with their verification state and relevant dates. They are not another criterion, a multiplier, an income replacement, an eligibility shortcut, or a point bonus.

Do not assume:
- 4Ps membership means maximum priority.
- No 4Ps membership means no need.
- An indigency certificate proves the current exact income.
- More files mean more need.
- Missing optional documents mean zero points.

Apply approved accessible alternative-evidence procedures. Do not make every supporting document mandatory or add a new document requirement through this calculation task.

### Conflicting information

For example, an applicant reports PHP 100,000 and presents low-income supporting records:

1. Review the sources, dates, assessment period and the apparent discrepancy.
2. Do not automatically accept the lower amount, reject the member, or declare fraud.
3. If PHP 100,000 is accepted after review, use that value with no document bonus.
4. If unresolved, keep the required input pending and apply existing complete-pool safeguards.

Do not encode PHP 100,000 as a universal exclusion threshold. Do not invent a fixed evidence-precedence hierarchy or conduct government reclassification.

### Other inputs

ES: accepted employment category for the applicable period; unresolved/unlisted categories are not automatically Unemployed.

PA: qualifying confirmed, non-voided actual releases from the system ledger under an explicit scope and period, with adequate history coverage. Applications, undelivered selections, referral tickets and event attendance are excluded. An empty or incomplete history does not automatically establish zero.

HM: a positive whole-person count under the authorized household definition; do not equate it with dependents or silently switch to per-capita income.

Use existing authorized accepted-evidence services. Raw registrations, private review notes and membership approval do not automatically qualify as accepted scoring inputs. Do not bypass unresolved evidence integration by reading the latest profile field directly.

Do not require the old three-domain or four-indicator SI rubric for this new income-based method. Retain such rubrics, evidence and readiness gates for the historical methods that actually use them.

## 5. Four-criterion AHP calculations

Retain column normalization and row averaging, now with n = 4:

```text
s[j] = SUM(i=1..4) A[i,j]
N[i,j] = A[i,j] / s[j]
w[i] = SUM(j=1..4) N[i,j] / 4
WSV[i] = SUM(j=1..4) A[i,j] * w[j]
CV[i] = WSV[i] / w[i]
lambda_estimate = SUM(i=1..4) CV[i] / 4
CI = (lambda_estimate - 4) / 3
CR = CI / 0.90
```

Use RI[4] = 0.90 from the reference table. Keep RI[5] = 1.12 in the historical five-criterion methods.

Validate positive entries, diagonal ones, reciprocity, positive usable weights and the applicable strict `0 <= CR < 0.10` check. Four criteria require six independent comparisons.

For the synthetic fixture only:

```text
q_demo = [1/4, 1/4, 1/4, 1/4]
A[i,j] = q_demo[i] / q_demo[j] = 1
Column totals = [4, 4, 4, 4]
Every normalized matrix entry = 1/4
Derived demo weights = [1/4, 1/4, 1/4, 1/4]
WSV = [1, 1, 1, 1]
CV = [4, 4, 4, 4]
lambda_estimate = 4
CI = 0
CR = 0
```

Label this “Synthetic equal-weight reconstruction — not approved operating weights.” CR = 0 follows by construction; it is not evidence of client judgment, fairness or genuine institutional authorization.

Real AHP approval requires the newly recorded pairwise judgments. If a separately authorized manual-weight method is used, retain that actual provenance instead of manufacturing an AHP matrix from percentages.

Compute weights at configuration time, not separately for each member.

## 6. Adjustable weights for the new version

Do not transplant the old five-criterion slider ranges.

Show four weights for the new draft. Their approved numerical vector and ranges remain unspecified.

If the existing remaining-weight pattern is retained for this version, the draft expression is:

`HM_percent = 100 - (SES_percent + ES_percent + PA_percent)`

Validate the combined weights server-side. Reject a negative remainder or invalid total. A reciprocal AHP configuration requires positive weights; no new zero-weight rule or HM minimum is authorized here.

Do not silently move other weights, discard a criterion, or change the old UI/configurations. Official use requires a compatible newly approved four-criterion vector and the applicable provenance/precision rules.

Draft slider proposals are not automatically AHP-derived judgments. Keep sensitivity/demonstration outputs separate from official runs.

## 7. Encoding and dataset-based normalization

Retain the reference's demonstration ES mapping:

- Full-Time Worker = 1
- Part-Time Worker = 2
- Seasonal Worker = 3
- Unemployed = 4

Operational use needs the applicable adopted mapping, including a defined path for unlisted/mixed categories. Do not invent extensions.

There is NO standalone SI numeric input in the new method. Do not take the old example SI values 4/3/1, combine them with income, or add them to SES.

For one complete, frozen, eligible and evidence-ready pool:

```text
L[j] = minimum accepted x[i,j] in the complete pool
U[j] = maximum accepted x[i,j] in the same pool

Income-based SES and PA:
z[i,j] = (U[j] - x[i,j]) / (U[j] - L[j])

ES and HM:
z[i,j] = (x[i,j] - L[j]) / (U[j] - L[j])
```

SES here uses the accepted income amount as x. No separate categorical SES level, government poverty threshold, income bracket or document multiplier is defined.

These are the documented directions for the new example. Actual program use requires their adoption under the new policy.

Preserve these safeguards:

- No scoring of missing, disputed, stale or invalid required inputs.
- No silently omitted unresolved applications to create a convenient pool.
- Constant column `U[j] == L[j]` blocks calculation under the retained rule. Do not insert 0, 0.5 or 1, add an epsilon, drop/reweight the criterion or borrow a threshold.
- Empty/single-applicant pools receive explicit handling; a one-person pool cannot satisfy this Min–Max rule.
- Approved alternative constant-column behavior would require a distinct recorded policy, not a hidden fallback.
- Filters, pagination and display order do not change bounds.
- Corrected values or pool membership require a complete new run with new bounds and retained history.
- Use full precision internally and exact rational reference tests; do not rank rounded values.
- Do not convert an old fixed-range program to dataset normalization.

## 8. Weighted score and optional classification

```text
EWS[i] = SUM(j=1..4) w[j] * z[i,j]
EWS100[i] = 100 * EWS[i]

Synthetic equal-weight fixture only:
EWS100 = 25*zSES + 25*zES + 25*zPA + 25*zHM
```

The percentage-point expression already gives a 0–100 score. Do not multiply it by 100 again.

Store raw amount/category, accepted finding, encoding, normalized value, weight, contribution and final score separately. Retain exact comparison precision and round only the displayed result.

The source classification bands remain available as an illustration:

- 80 <= score <= 100: High Assistance Need
- 60 <= score < 80: Moderate Assistance Need
- 40 <= score < 60: Low Assistance Need
- 0 <= score < 40: Minimal Assistance Need

Do not turn those bands into socioeconomic classes or enable official classifications without approval. Keep classifications disabled where the existing approved workflow has them disabled. Classification is not necessary to order scores and is not eligibility or selection.

## 9. Internal ranking and human decisions

Retain the convention in the supplied Codex prompt for the new synthetic preview:

`rank(i) = 1 + number of applicants with strictly greater exact scores`

- Descending exact scores.
- Exact ties share competition ranks, for example 1, 2, 2, 4.
- Two scores that display identically are not tied unless their internal values are equal.
- No tie-breaking through name, reference, timestamp, member ID or row order.
- Capacity-boundary ties follow the applicable approved human procedure or remain on hold.
- A stable display order within a tied group is not beneficiary priority.

Official use requires the versioned ranking/tie policy. Human selection, capacity constraints, actual releases and result publication remain separate authorized actions.

Admins cannot edit generated scores or drag applicants into a preferred ranking. No public ranks, private socioeconomic information or broader identifiers are authorized by this task. Do not backfill new ranks into old runs.

## 10. Mandatory reproducible fixtures

### A. Revised four-criterion example

Use only synthetic data and the demo vector `[1/4, 1/4, 1/4, 1/4]`:

| Applicant | SES accepted income (PHP) | ES encoded | PA | HM |
|---|---:|---:|---:|---:|
| A | 5000 | 3 | 1 | 4 |
| B | 12500 | 4 | 0 | 2 |
| C | 20000 | 1 | 3 | 6 |

Bounds in SES/ES/PA/HM order:

```text
L = [5000, 1, 0, 2]
U = [20000, 4, 3, 6]

A normalized = [1, 2/3, 2/3, 1/2]
B normalized = [1/2, 1, 1, 0]
C normalized = [0, 0, 0, 1]

A contributions = [25, 50/3, 50/3, 25/2]
B contributions = [25/2, 25, 25, 0]
C contributions = [0, 0, 0, 25]

A exact score = 425/6 = 70.833333...; displayed 70.83; internal rank 1
B exact score = 125/2 = 62.50; internal rank 2
C exact score = 25 = 25.00; internal rank 3
```

Optional demonstration classifications: A Moderate, B Moderate, C Minimal. Do not activate them for real programs by inference.

Derive every intermediate value. Do not hardcode final scores or reuse rounded contributions.

### B. Evidence must not add points

With an unchanged accepted pool and accepted SES/ES/PA/HM values, changing only a 4Ps flag, the number of files, or the presence of an optional indigency certificate must not alter the numerical result.

This invariance does not mean bypass evidence review: conflicting or invalid evidence can make an input unready; it cannot award a bonus or directly overwrite the score.

In a separate complete synthetic pool, include an accepted PHP 100,000 income and low-income supporting-document labels. If 100,000 is the pool maximum, its SES normalized value is 0 regardless of those labels. It is not automatically ineligible. If that amount remains disputed instead of accepted, calculation is blocked under the existing evidence rules.

Changing income requires recalculating the whole pool's bounds, not evaluating it against an old frozen example range.

### C. Historical preservation

The prior HI/SI/ES/PA/HM fixture must still produce 83.90, 62.81 and 12.22 under its ORIGINAL illustrative vector and inputs. That fixture belongs to the old method; it is not the expected output of this SES revision.

Keep any existing version 6 fixtures with their own exact stored vector. Do not mutate them into a four-criterion case.

## 11. Admin workflow, reusable policies and history

Keep the eight Admin groups and minimalist interface. Add the new-version preview and policy presentation under EWAF & Selection, using compatible existing components.

Clearly show:

- The four criterion codes and method identity.
- “SES (income-based)” and its raw “Accepted household monthly income (PHP)” field.
- Separate evidence review of 4Ps/indigency information, with no score controls attached to documents.
- Synthetic demonstration versus real program mode.
- New weight-authorization blockers, not a fabricated approved 25% vector.
- Full input provenance, bounds, contributions, precision, ties and decision status.

Reuse versioned policy storage and immutable program bindings. The binding must check criterion identity/semantics and method compatibility, not just count or weight total.

Do not let a new shared draft change an existing program, locked weight vector, past run, selected beneficiary or published result. A program must retain the exact method, policy, weight version, terms and cutoff used.

Retain, per run: complete pool; evidence/assessment versions; raw and encoded values; directions/bounds; weight source; precision; rank convention; actor/time; predecessor; decisions and publication provenance.

Policy readiness and applicant-data readiness remain distinct. Dataset-derived bounds are obtained after the accepted pool exists, not populated with example limits before opening. Preserve the current authorized publication/opening policy; this computation revision must not change it by implication. Official calculation additionally needs complete new-method policy, weights, evidence and the existing schedule/activation gates.

The old SI-rubric requirement must not leak into the new method, but it must continue to protect historical methods that depend on it. Replace it only within the new version with the appropriate income/evidence policy checks.

## 12. Development boundaries and required tests

Inspect and extend the actual existing integration. Use a narrow version-aware adapter/dispatch change only where required; report every affected protected boundary. Do not weaken legacy assertions to get tests passing.

No new real-data processing, approval seeds, working-database modifications, startup-guard bypass, schedule changes, deployment, commit, push or merge is authorized.

Use synthetic data, verified disposable MySQL and isolated media. Necessary new schema must be additive, reviewed and separately identified; do not edit existing migrations or reapply already-applied migrations. Approval fixtures remain clearly synthetic and confined to isolated tests.

Do not modify unrelated registration, email, referral, document requirements or portal layout. Removing SI as a scoring contribution does not delete its historical evidence or erase supporting documents from registration.

Test at minimum:

1. Four-criterion matrix, column totals, weights, WSV, CV, lambda, CI and RI[4] usage.
2. Revised A/B/C inputs, bounds, normalization, contributions and exact scores.
3. No operational use of demo weights and no automatic HI+SI merging or deleted-SI redistribution.
4. Evidence-label/document-count invariance with accepted values held fixed.
5. PHP 100,000 discrepancy handled as review, and accepted income handled without a bonus or automatic rejection.
6. Missing optional documents versus missing required accepted income are distinguished.
7. Raw declaration/review-note substitution cannot bypass accepted-evidence services.
8. Unknown income/PA is not zero; invalid/negative values and unlisted ES categories block appropriately.
9. Constant columns, single/empty pools, ties, close scores and capacity-boundary decisions.
10. Complete-pool recalculation and preserved prior runs after legitimate corrections.
11. Immutable policy and weight bindings; a five-criterion or older four-criterion record cannot bind merely by name/count.
12. Old SI-rubric gates remain active only for methods that use them; no direct score editing is introduced.
13. Private evidence/export access, permissions, direct requests, audit failure and stale/concurrent changes.
14. Existing four-criterion and five-criterion fixtures and historical payloads remain unchanged.
15. No public rank exposure, automatic selection, genuine approval creation or default activation.
16. Accessible Admin labels, keyboard operation and clear readiness messages where UI changes occur.

Report actual commands and results, overlaps, failures and untested areas. Mathematical fixture reproduction is not real-applicant acceptance or a fairness validation.

## 13. Execute and report

Implement the independent scoped new-version work rather than restarting a general audit. Stop only the affected dependency where a required contract is genuinely missing; do not fabricate its policy.

Return:

- Exact new method definition and the limited income-based meaning of SES.
- Files, dispatch adapters and any proposed additive migrations.
- Calculated four-criterion matrix/consistency and A/B/C evidence.
- Historical-method preservation results and protected-file diffs.
- Evidence-review behavior and the no-document-bonus tests.
- Readiness blockers: new real weights/provenance, income definition/period, accepted evidence and other applicable policy decisions.
- Admin preview availability versus operational enablement.
- Actual tests, limitations and explicit changes not performed.

Update progress without overwriting earlier evidence. Keep the accepted milestone at its recorded value unless the owner separately changes it. Stop after the report; do not activate real scoring or publish rankings automatically.
