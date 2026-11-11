# SES EWAF: configuration, accepted inputs and ranking

Implementation guide, 27 October 2026. Read alongside [the validation report](ewaf-ses-2026-10-27-validation.md). This describes the new code in the current checkout. It does not approve weights, adopt an institutional policy, enable production scoring or change the owner's accepted 70% milestone.

The earlier [current-workflow baseline](EWAF_Current_Criteria_Scoring_and_Ranking.md) remains an unchanged record of the preceding HI/SI workflow.

## 1. The distinct method

Method identifier: `ewaf-ses-es-pa-hm-dataset-v1`.

Canonical criterion signature: **SES, ES, PA, HM**. The code checks the actual signature and method, not just the number of criteria. The historical SI/ES/PA/ND method also has four criteria and is incompatible with SES.

| Criterion | Accepted raw value | Source and interpretation | Direction |
|---|---|---|---|
| SES — Socioeconomic Status | Average household monthly income in PHP | Explicit income assessment, supporting evidence, bound period and discrepancy review | Lower income contributes more |
| ES — Employment Status | Accepted category, encoded 1–4 | Accepted employment finding | Higher encoded value contributes more |
| PA — Previous Assistance Received | Nonnegative count | Successful, non-voided releases under the bound scope, dates, recording cutoff and accepted history coverage | Fewer qualifying releases contribute more |
| HM — Number of Household Members | Positive whole-person count | Accepted household assessment under the approved household definition | More household members contribute more |

**SES is an income-based proxy.** It is not a new qualitative hardship index. The method has exactly four contributions: no additional HI term, no SI term, no income-per-person division, no expense subtraction and no employment adjustment inside SES.

Employment encoding remains:

| Accepted finding | ES value |
|---|---:|
| Full-Time Worker | 1 |
| Part-Time Worker | 2 |
| Seasonal Worker | 3 |
| Unemployed | 4 |

Mixed or unlisted employment remains unresolved until an authorized supported finding or policy resolves it. Staff cannot substitute Unemployed.

## 2. Evidence supplies findings, not points

Registration supplies declarations and documents. Membership approval and a general review note do not establish accepted scoring inputs. An authorized reviewer must record a new-method acceptance against the exact bound policy.

4Ps information, a Certificate of Indigency and other permitted documents support verification. They do not add points or replace the accepted numerical amount. Accepted PHP 100,000 remains PHP 100,000. A material inconsistency requires review of dates, circumstances and supporting evidence; it does not automatically mean fraud or rejection.

The SES acceptance form records either a reviewed consistent finding or a resolved discrepancy. A resolved discrepancy requires its explanation. An unresolved discrepancy blocks acceptance. Missing income is unresolved, not zero. Absence of 4Ps membership or an indigency certificate does not automatically fail SES; the reviewer uses the policy's permitted evidence alternatives.

The approved income policy specifies the number of complete calendar months, inclusions/exclusions and basis. The existing averaging service uses complete months immediately before the approved application-closing month. It averages the accepted amounts exactly; there is no universal three-month default for SES.

PA counts only actual successful, non-voided release records. Existing inclusive, calendar-month-clamped date boundaries and records-entered-by-cutoff treatment remain. Unknown history coverage blocks acceptance, including an apparently empty ledger. Applications, attendance and selections without delivery do not count as releases.

Evidence must be current, verified, owned by the member and compatible with the policy's allowed types. A previously verified document may support a new acceptance when compatible, but historical HI/SI findings are not relabeled or automatically accepted as SES. Changes to declarations, document reviews, member versions or assistance history can invalidate current use. That freshness check is not a document bonus.

## 3. Editable weights and AHP

Use the existing **EWAF Configuration Vault** and choose **SES / ES / PA / HM — income-based SES**. Its route is `/ewaf/vault/?method=ewaf-ses-es-pa-hm-dataset-v1`.

If no matching proposal exists, four starting percentage boxes are blank. An Admin must choose the starting values and save an **unapproved weight draft**. No equal-weight, document-example, prior version number or converted five-criterion vector is supplied. Once saved, the matching draft opens in the existing cascading slider editor.

- Each slider has a full 0–100% visual range in 0.01 percentage-point steps.
- Increasing a criterion takes weight proportionally from those below it; earlier values remain fixed. Decreasing it releases weight below it.
- The last criterion receives the remainder. Move it higher with the priority arrows to adjust it directly.
- Every criterion can occupy every priority position. The proposed values remain keyed by criterion code throughout calculation.
- Proposals must total 100%, remain positive, follow the chosen non-increasing priority order and keep the largest value within nine times the smallest. Server validation repeats these checks.
- Zero and 100% endpoints are not generally feasible stored values.

For each of the six distinct pairs, the existing algorithm projects the proposed ratio onto Saaty's supported 1–9 values or their reciprocals. It minimizes multiplicative distance and retains the smaller-integer tie rule. It builds a reciprocal 4×4 matrix with ones on its diagonal.

```text
S[j] = sum_i A[i,j]
N[i,j] = A[i,j] / S[j]
w[i] = sum_j N[i,j] / 4
WSV[i] = sum_j A[i,j] * w[j]
CV[i] = WSV[i] / w[i]
lambda_estimate = sum_i CV[i] / 4
CI = (lambda_estimate - 4) / 3
CR = CI / 0.90
```

Approval requires `0 <= CR < 0.10`, compatibility with the chosen priority order, and the retained precision contract. Genuine equal calculated weights are permitted. The five-criterion engine retains its original arithmetic and RI 1.12.

The editor distinguishes **proposed slider percentages** from **calculated AHP weights**, displays consistency, and identifies the saved version and provenance. These are slider-generated comparisons processed by AHP, not independently elicited stakeholder judgments. The system does not manufacture an operational CR of zero by reconstructing ratios from final weights.

Save a changed proposal as a draft before approving it. Approval creates a new immutable version from the unchanged reviewed draft. The approved calculated weights, stored as exact decimal strings, control scoring. Rounded percentages and display remainder adjustments do not replace those coefficients.

### Retained precision restriction

AHP uses 50-digit, half-even decimal arithmetic. The existing total validator permits a bounded negative rounding residue but rejects **any total above 1**, including a tiny positive rounding residue. This revision preserves that contract for both old and new workflows; it does not renormalize coefficients.

For example, the synthetic proposal 40/30/20/10 passes CR but its calculated stored total exceeds 1 by `1.5 × 10^-50`. It can remain a draft, but SES approval is blocked and the preview explains why. The Admin can choose another proposal. Changing this asymmetric precision contract would require a separately authorized revision; it has not been silently broadened here. The requested operational fixture 44.78/23.22/16.01/15.99 has a retained residue of `-10^-50` and passes the existing contract.

## 4. Policy and program binding

Approved weights and ordinary program prerequisites can permit publication and intake while scoring rules are pending. The scoring-policy gate applies to calculation and subsequent EWAF selection, not to every publication.

Use **Configure calculation rules** for the SES method. The same versioned policy storage is reused. Review all three groups:

| Group | Required review |
|---|---|
| A | Exact compatible locked weight version, provenance and precision |
| B | Income-based SES measure, assessor authority and discrepancy-review procedure |
| C | Income period/basis, evidence and accessible alternatives, household definition, PA scope/coverage/cutoff rules, unresolved-input treatment, ties, corrections, authority, scope and effective dates |

No qualitative SES rubric or legacy 4Ps/indigency-points prerequisites appear in the SES policy. Institution-specific choices remain unspecified until an authorized Admin records them. Saving a policy draft creates no approval. Policy approval records explicit review of A, B and C.

On the program's EWAF workspace, choose **Assign approved calculation rules**. Select the compatible approved policy and enter the assessment cutoff, at or after application closing and inside policy validity. The binding retains the exact program terms, method, policy, approved weight version and cutoff.

New unconfigured program drafts inherit the active approved Vault version through the existing service. Existing programs keep their prior configuration. A published weights-only intake may receive its first compatible scoring policy only under the existing procedure and with the same retained weight version. Existing old-method bindings cannot be converted to SES through this screen. Scored or historical programs remain protected by the existing revision restrictions.

Dataset minimums and maximums are obtained at evaluation time. They are not fictional pre-opening policy limits.

## 5. Calculation and ranking

After closing and cutoff, the system resolves the entire application inventory. Verified ineligible outcomes stay outside the scored pool. Every eligible applicant must have accepted, current SES/ES/PA/HM findings. Unresolved applications block generation; the system does not silently omit them or calculate all registered members.

For each criterion, determine the minimum `L` and maximum `U` from the complete frozen accepted eligible pool:

```text
SES and PA: z = (U - x) / (U - L)
ES and HM:  z = (x - L) / (U - L)

EWS100 = 100 * (wSES*zSES + wES*zES + wPA*zPA + wHM*zHM)
```

Raw SES is the accepted PHP income and is normalized once. Exactly four contributions are retained. All scores use exact rational arithmetic from the stored coefficients and accepted values. The presentation rounds half-even to two decimal places.

```text
rank(i) = 1 + count(applicants whose exact score is strictly higher)
```

Exact ties share competition ranks, such as 1,2,2,4. Two scores that merely display the same rounded value may still have different exact ranks. A tie crossing the capacity boundary either holds selection or requires the approved reasoned-human procedure. No timestamp, reference or ID decides the beneficiary.

If any column is constant (`U = L`), generation stops, including for a one-person pool. There is no clipping, midpoint substitution, epsilon, removed criterion or redistributed weight. Missing/stale/disputed/invalid inputs also block generation. Classifications remain disabled.

The retained run includes the policy/configuration/weight references, cutoff, complete inventory, accepted evidence references, bounds, exact contributions, scores, actor, timestamp and predecessor. Filters and pagination do not change the pool or bounds. Source corrections require reassessment and a new complete-pool run; prior versions remain retained.

## 6. Human decisions, release and public results

Ranking does not select beneficiaries or record delivery. Authorized officers make reasoned decisions within the approved capacity. Existing release services record actual delivery separately.

The existing permitted-publication services produce their restricted public projection. They do not publish income, evidence, exact scores or the private ranking snapshot. The Admin-only **Download private calculation (JSON)** link exports the retained run with permission checks and `no-store, private` caching. It remains a historical snapshot, not a claim of current readiness.

## 7. Admin sequence after authorized operating setup

1. Open **EWAF & Selection → Configuration Vault**, select SES and choose four starting percentages. Save the unapproved draft.
2. Review and adjust sliders and priority arrows. Check proposed versus calculated weights, CR, storage compatibility and version provenance. Save changed drafts; an authorized approver approves the unchanged reviewed draft.
3. Open **Configure calculation rules** for SES. Select the exact approved compatible weight version, complete institutional choices, save the draft and explicitly approve A/B/C.
4. Create or use an appropriate new SES program draft. Complete the ordinary program terms/authority prerequisites. Publication/intake can precede scoring-policy completion where the existing weights-only workflow permits it.
5. Open that program under **EWAF Ranking → Assign approved calculation rules**. Bind the compatible approved policy and immutable cutoff. Do not substitute another method into an existing old-method program.
6. Complete eligibility and document verification. After cutoff, use each eligible applicant's **Enter / verify EWAF information** link to record income months, income-consistency review, accepted ES/HM, PA coverage and supporting evidence, then select **Accept evidence-backed inputs**. Resolve every application's status.
7. When the complete pool is ready, choose **Generate EWAF Ranking**. Review the score breakdown and retained calculation. Resolve any boundary tie under the bound procedure, then record authorized human decisions.
8. Use the existing permitted results-publication and actual-release actions. If sources change, follow the approved correction procedure and regenerate the complete pool while retaining previous runs.

The current implementation supplies these technical paths. It does not supply selected live weights, institutional authority records, income/household/history/evidence definitions, real program bindings or accepted applicant findings.
