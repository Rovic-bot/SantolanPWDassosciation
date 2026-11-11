# CODEX — IMPLEMENT SES / ES / PA / HM IN THE CURRENT EWAF WORKFLOW

## 1. Implement this revision now

I authorize scoped technical implementation of the NEW four-criterion EWAF:

1. SES — Socioeconomic Status, measured here by accepted household monthly income after evidence review.
2. ES — Employment Status.
3. PA — Previous Assistance Received.
4. HM — Number of Household Members.

Replace separate HI and SI scoring ONLY for this new method. Keep all four weights adjustable through the existing configuration workflow. Connect the new method to the actual Configuration Vault, policy approval, program binding, evidence acceptance, EWAF Ranking, selection, release and permitted-publication services. Do not deliver only a renamed screen, an isolated calculator or another planning-only report.

This explicitly authorizes necessary method-aware EWAF source changes for this revision. Earlier blanket restrictions against changing any EWAF file must not prevent this authorized implementation. Preserve legacy behavior and historical data, not a false claim that every implementation file remained unchanged.

The authorization covers code, reviewed additive migrations, and isolated synthetic validation. It does NOT create institutional approvals, authorize real-data activation, change the working/production database, or authorize commit/push/merge/deployment.

## 2. Source priority and existing implementation

Read the actual available files:

- `EWAF_Current_Criteria_Scoring_and_Ranking.md` — implementation baseline supplied for this task; confirm its statements against the checkout.
- `Computation_Updated_SES_ES_PA_HM.docx` — four-criterion definition, mathematics, example assumptions and revision record.
- `Codex_EWAF_SES_Computation_and_Ranking.md` OR its identical `.txt` counterpart — earlier revision guidance.
- Applicable current policies, integration reports, decisions, and approval records.

The older `Codex_EWAF_Updated_Computation_and_Ranking_SES_ES_PA_HM` files are earlier prompt versions, not additional approvals. Do not execute conflicting copies as separate tasks. Locate the actual filenames; do not assume an unreadable/truncated display name is a new document.

This instruction resolves two conflicts explicitly:
- The new version uses SES/ES/PA/HM, not the baseline's HI/SI/ES/PA/HM.
- Preserve the CURRENT cascading sliders, priority arrows and slider-generated AHP projection, adapting them to four criteria. Do not replace them with an older prompt's simpler adjustment rule.

The current guide identifies these likely implementation points; inspect their actual contracts before editing:

- `ewaf/revised/engine.py`
- `ewaf/revised/si.py`
- `ewaf/revised/live_evidence.py`
- `static/js/ewaf-weights.js`
- `ewaf/weight_input.py`
- `ewaf/household_math.py`
- `ewaf/vault_services.py`
- `ewaf/revised/contracts.py`
- `ewaf/revised/live_services.py`
- `ewaf/revised/live_math.py`
- `ewaf/operational_services.py`

Do not restart completed registration/CMS work or build duplicate policy storage. Inspect branch, worktree, existing schema and relevant tests. Preserve unrelated uncommitted work. Missing operational policy must block that operation, not all independently implementable development.

## 3. Criterion sources and scoring contract

Use the canonical method signature `(SES, ES, PA, HM)` and a distinct versioned method identifier. Criterion count alone is insufficient: the historical `(SI, ES, PA, ND)` method also has four criteria.

| Criterion | Raw accepted input | Source | Direction |
|---|---|---|---|
| SES | Accepted average household monthly income in PHP | Current approved income assessment linked to the member and supporting evidence | Inverse: lower accepted income contributes more |
| ES | Employment category encoded 1–4 | Accepted employment finding | Increasing |
| PA | Qualifying actual-release count | System assistance ledger and accepted coverage finding | Inverse |
| HM | Positive whole-person household count | Accepted household assessment | Increasing |

For this method:

`SES_raw = accepted_household_monthly_income_php`

SES is an income-based proxy, NOT a new multi-domain hardship index, a poverty certificate, a clinical assessment, or an invented low/middle/high tier. Use this description in help text and documentation.

Do not also score HI. Do not retain the old SI contribution. Do not divide income by HM, subtract expenses, add a three-domain SI rubric or add employment effects inside SES. Those would change this requested definition.

Initial registration supplies declarations and documents. Scoring consumes accepted, current, policy-compatible findings. Registration approval or a generic review note is not evidence acceptance.

### SES and document review

4Ps information, Certificates of Indigency and other permitted documents remain verification evidence, not numerical bonuses.

The current 0 / 2.5 / 5 SI rule must remain available for its historical method but must NOT execute for SES. Do not require both legacy SI findings to be completed before SES is ready. Appropriate income evidence and discrepancy review still apply.

Examples of required behavior:
- Accepted PHP 100,000 remains PHP 100,000 even when a 4Ps record or indigency certificate exists.
- A material inconsistency triggers review of dates, circumstances and evidence; it is not automatic fraud, rejection, low-income substitution or extra points.
- Missing accepted income is unresolved, not zero.
- No 4Ps membership/certificate does not automatically fail SES or award zero need. Use authorized evidence alternatives; separate genuine program eligibility rules remain separate.
- For identical accepted numerical inputs and accepted status, different document counts or 4Ps status do not change scores.
- Evidence changes may invalidate an accepted finding; do not confuse this freshness control with adding points for documents.

### Other inputs

Retain ES encoding:
- Full-Time Worker = 1
- Part-Time Worker = 2
- Seasonal Worker = 3
- Unemployed = 4

Unlisted, mixed or unresolved employment requires an authorized mapping; never guess Unemployed.

Reuse the income assessment's approved complete-calendar-month averaging rule, month count and income inclusion/exclusion policy where compatible. Do not invent a universal three-month period.

PA remains a count of actual successful, non-voided release records under the bound policy's scope, dates, cutoff and history-coverage rules. Do not count applications, selections without delivery, tickets or attendance. Unknown coverage is not zero. Preserve existing treatment of records entered by cutoff and date boundaries; do not introduce new PA scopes by inference.

HM remains the accepted household count under the applicable definition, not Number of Dependents. Unresolved definitions or evidence remain explicit blockers.

## 4. Keep weights editable; adapt the existing sliders to four criteria

Keep the current behavior documented in the baseline:
- Full 0–100% visual slider scale, 0.01 percentage-point increments.
- Increasing a criterion redistributes weight among criteria below it proportionally; earlier ones stay fixed.
- Decreasing it releases weight below it.
- The last criterion receives the remaining percentage.
- Priority arrows can move ANY criterion, including SES and HM. The last criterion is indirectly adjustable and can be moved higher for direct adjustment.
- Feasible proposals retain positive weights, the chosen non-increasing priority order and the existing maximum 9:1 proposal ratio.
- Validate on the server, not just in JavaScript. Zero and 100% endpoints are not necessarily feasible saved values.

Use criterion codes, not display positions, to associate weights with inputs. Reordering the interface must never apply an ES weight to SES income.

Do not force 25% each, 44.78/23.22/16.01/15.99, the old five-criterion defaults, or version 6 into real configurations. Do not add old HI+SI weights or automatically rescale a live five-criterion vector.

Restore an existing matching four-criterion draft when available. Otherwise provide an explicit unapproved setup requiring an administrator to select/review four proposed weights. A clearly labeled demonstration is separate from that real setup.

## 5. Preserve slider-generated AHP; calculate it correctly for n = 4

Adapt the current generated-comparison algorithm, not the teaching document's ratio-reconstruction shortcut:

1. Generate SIX distinct pairwise comparisons from the four slider proposals.
2. Retain supported values 1–9 and their reciprocals.
3. Preserve nearest multiplicative-ratio projection and its existing smaller-integer tie rule.
4. Build a reciprocal 4×4 matrix with diagonal ones.
5. Use column normalization and row averages:

   S[j] = SUM_i A[i,j]
   N[i,j] = A[i,j] / S[j]
   w[i] = SUM_j N[i,j] / 4
   WSV[i] = SUM_j A[i,j] * w[j]
   CV[i] = WSV[i] / w[i]
   lambda_estimate = SUM_i CV[i] / 4
   CI = (lambda_estimate - 4) / 3
   CR = CI / 0.90

6. Retain the strict `0 <= CR < 0.10` requirement and the existing order-compatibility check, allowing genuine equal calculated weights.

For n = 4 use RI = 0.90; do not retain division by 5, CI denominator 4 or RI = 1.12. Keep the five-criterion arithmetic unchanged for old methods.

Display both proposed slider percentages and calculated weights. The approved CALCULATED weights control scoring, not rounded slider labels.

Describe provenance accurately as slider-generated comparisons processed by AHP, not independently elicited stakeholder judgments. Do not manufacture CR = 0 by reconstructing A[i,j] = w[i]/w[j] for operational approval.

Preserve the documented 50-digit weight arithmetic and exact stored decimal strings. Reuse the recorded precision/total validation contract; do not silently rescale stored values. Any residual-adjusted display must not change the coefficients. Genuine substantive weight errors must fail validation.

## 6. Dataset normalization, weighted score and ranking

After applications close and the bound cutoff is reached, resolve the application inventory and freeze the complete accepted eligible pool. Do not calculate all registered members or silently omit unresolved applicants.

For each criterion j:

`L[j] = minimum accepted value in that frozen pool`
`U[j] = maximum accepted value in that frozen pool`

SES and PA:

`z[i,j] = (U[j] - x[i,j]) / (U[j] - L[j])`

ES and HM:

`z[i,j] = (x[i,j] - L[j]) / (U[j] - L[j])`

Final score:

`EWS100 = 100 * (wSES*zSES + wES*zES + wPA*zPA + wHM*zHM)`

Use accepted PHP income as raw SES, normalize it once, and include exactly FOUR contributions.

Retain exact arithmetic from stored values, half-even two-decimal presentation and exact-score competition ranking:

`rank(i) = 1 + count(applicants with a strictly higher exact score)`

Exact ties share ranks, e.g. 1,2,2,4. Apply the assigned capacity-boundary hold or authorized reasoned-human procedure. No secret timestamp/ID/reference tie-break.

Preserve:
- Missing/stale/disputed/invalid input blocking.
- Current constant-column stop when U = L, including a one-applicant pool. Do not add midpoint substitution, clipping, epsilon, criterion removal or reweighting.
- Scope-bound PA coverage checks and accepted evidence references.
- Complete-pool recalculation after accepted source changes, with earlier runs retained.
- Bounds unaffected by filters or pagination.
- Classifications disabled as in the current operational dataset policy. Teaching bands are not activated.
- Human selection, capacity, actual delivery and result publication as separate actions.
- No new public numerical ranks, private scores, evidence or expanded identifiers.

## 7. Integrate the actual Admin and program workflow

Extend the existing EWAF Configuration Vault and **EWAF Ranking** route. Do not restore the retired preview navigation or build another disconnected page. Preserve the eight Admin groups and minimalist design.

Implement the complete new-method path:

Four-criterion draft weights
→ generated AHP comparisons and approved compatible weight version
→ complete new-method policy and approval
→ immutable program/method/policy/weight/cutoff binding
→ accepted SES/ES/PA/HM inputs
→ Generate EWAF Ranking
→ authorized human decision
→ existing release/publication controls.

Update input forms, policy validation, readiness messages, serializers, calculation snapshots, breakdowns, internal exports and compatible consumers to use the method signature. Old-method screens must still show old criteria.

Remove obsolete SI-rubric/4Ps-points prerequisites ONLY for the income-based SES method. Retain its income basis, period, evidence acceptance, household definition, PA history, cutoff and authority checks. No need to ask for a new qualitative SES rubric for this explicitly income-based measure.

Do not accidentally make optional document possession a mandatory eligibility rule.

Use existing storage and accepted-evidence services. Do not consider raw profile fields accepted merely because code can read them. If a legacy income finding could be reused, verify purpose/period/evidence/version compatibility through an explicit new-method acceptance process; do not relabel historical findings automatically.

Preserve the CURRENT publication distinction: approved compatible weights and normal program prerequisites may permit publication/intake while scoring rules are pending; generation requires the complete approved bound policy and ready evidence. Do not reinstate an obsolete blanket scoring-policy-before-publication gate. Dataset numerical bounds are determined at evaluation, not invented before applications exist.

Expose the SES method for new drafts without pretending the old version has been converted. Existing programs retain their exact original bindings. Rebinding an active program requires its separately authorized revision process.

## 8. Preserve history and make readiness honest

Retain all historical method keys, old HI/SI points, old four-/five-criterion configurations, original references, evidence, calculations, decisions, releases and public projections.

Do not migrate old results to new codes, delete `si.py` for historical use, backfill a new four-weight authority or update an old approved version in place.

Record source-code amendments and regression evidence explicitly. A historical protection manifest is evidence to compare, not permission to claim zero changes when this new method changes those files.

This task authorizes the requested technical scoring definition and direction. It does not supply missing institution-specific facts, approvals, income rules, staff authority or a selected four-criterion live weight vector. Reuse genuinely compatible recorded policy values in drafts without transferring their approvals automatically.

Do not ask again whether to use four criteria, whether documents should earn points, or whether weights stay editable: these choices are made here. Report only genuinely unresolved operating dependencies.

## 9. Required fixtures and tests

### A. DOCX arithmetic fixture — teaching only

Use exact demonstration weights:

`q = [3421/7640, 1774/7640, 1223/7640, 1222/7640]`

The DOCX's ratio matrix A[i,j]=q[i]/q[j] reproduces q and CR=0 by construction. Test that mathematical example separately; it is NOT the operational slider-projection approval path and not a production seed.

Synthetic accepted inputs, ordered SES income / ES / PA / HM:

- A: [5000, 3, 1, 4]
- B: [12500, 4, 0, 2]
- C: [20000, 1, 3, 6]

Expected normalized vectors:

- A: [1, 2/3, 2/3, 1/2]
- B: [1/2, 1, 1, 0]
- C: [0, 0, 0, 1]

With the exact DOCX q, expected scores are:

- A: 15075/191 → 78.93, rank 1
- B: 47075/764 → 61.62, rank 2
- C: 3055/191 → 15.99, rank 3

### B. Actual slider-to-AHP-to-ranking fixture

Separately test a SYNTHETIC slider proposal of [44.78,23.22,16.01,15.99] percent, in SES/ES/PA/HM order.

Using the current multiplicative-nearest Saaty projection adapted to four criteria, the independently calculated expected matrix is:

    [1,   2,   3, 3]
    [1/2, 1,   2, 2]
    [1/3, 1/2, 1, 1]
    [1/3, 1/2, 1, 1]

Exact mathematical row-average weights:

`[331/728, 383/1456, 411/2912, 411/2912]`

`CR ≈ 0.00383664320175544`

With the same applicant inputs, mathematical reference scores display:

- A: 79.47
- B: 63.15
- C: 14.11

These differ legitimately from fixture A because the quantized comparison matrix changes the weights. Verify against the actual projection algorithm and 50-digit storage contract using reviewed precision tolerances, not rounded coefficients or hardcoded scores. Record any discrepancy rather than changing expected results without explanation.

Neither test vector is a default approved configuration. Add tests with other valid adjustable vectors and reordered priorities.

### C. Integration and safety tests

Test all of the following:
- A second eligible applicant with identical accepted values but different reviewed 4Ps/indigency evidence receives exactly the same score.
- Document absence/count cannot directly change SES or create a fifth term.
- Conflicting high income and documents require review; accepted high income is used without a bonus.
- New configuration/policy/binding compatibility rejects old signatures even when n=4.
- All four sliders/priority positions work, totals/positivity/ratio constraints hold, and proposed versus calculated weights remain distinct.
- Old generated-matrix, SI 0/2.5/5, legacy score and rank fixtures still reproduce.
- Missing evidence, incomplete PA coverage, unlisted employment, invalid household counts, constant columns and unresolved applicants retain existing gates.
- Exact/near ties, complete-pool freshness, new versions and source invalidation are correct.
- Unauthorized direct requests, approval, private exports, stale concurrent changes and audit failure are controlled.
- A full synthetic stored-policy → program binding → accepted inputs → ranking → human selection → permitted publication journey works in the real service path.
- Browser/keyboard checks show four correct criteria for new configurations, accurate weight feedback and unchanged legacy screens.

## 10. Environment, migration and delivery

Inspect the actual migration graph. Do not assume migration 0012 is unapplied or reuse an occupied migration number. No migration reapplication based on an outdated report.

Necessary schema changes must be additive, narrowly reviewed, and preserve nullable historical bindings and existing records. No approval seeds or historical score conversion. Generate/rehearse only in verified disposable MySQL with synthetic media. Do not change the normal database, startup guard, credentials, feature flags for real users or program schedules.

Deliver the implemented service/UI integration, not just another proposed contract. Keep operational actions gated only by their real unmet prerequisites; do not let missing institutional facts block independently authorized code/tests.

Return:
1. Completed/Partial/Blocked status and exact new-method behavior.
2. Current checkout and files changed, including narrowly modified legacy dispatch points.
3. New schema proposals and disposable migration results, if any.
4. Both fixture sets and actual end-to-end evidence.
5. Tests run, counts/overlaps, failures and limitations.
6. Preserved historical calculations, approvals, data and UI behavior.
7. Remaining four-criterion weight/policy decisions, installation and activation prerequisites.
8. The exact Admin steps to configure, approve, bind and run the SES method after authorized setup.

Update development records without overwriting earlier evidence. Preserve the accepted 70% milestone unless separately updated by the owner. Do not commit, push, merge, deploy, publish a real program or activate real-applicant scoring automatically. Stop after the implementation report.
