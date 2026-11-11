# Composite SES: income with a verified household 4Ps adjustment

Implemented candidate, 27 October 2026. This guide describes `ewaf-ses-4ps-es-pa-hm-dataset-v1`, formula `income-4ps-multiplier-90-10-v1`. It does not record institutional approval or activate real-applicant scoring. See [validation evidence](ewaf-composite-ses-2026-10-27-validation.md).

The earlier [income-only SES guide](EWAF_SES_Configuration_and_Ranking_Guide.md) describes a preserved historical method. Its approved versions and calculations are not changed in place.

## Exact calculation

The main criteria remain **SES, ES, PA, HM**. SES is described as **Income-based SES with a verified 4Ps adjustment**.

```text
H = accepted average household monthly income in PHP
L = lowest accepted income in the complete frozen eligible pool
U = highest accepted income in that pool
P = 1 for reviewed current household 4Ps Verified Yes
    0 for reviewed current household 4Ps Verified No

I = (U - H) / (U - L)
SES = I * (9/10 + (1/10)*P)

Verified Yes: SES = I
Verified No:  SES = 0.90*I
```

The adjustment depends on income need. It is not `0.90*I + 0.10*P`, a flat ten-point bonus, or an automatic maximum score for a 4Ps household. A Certificate of Indigency and the quantity of documents do not add points. Accepted PHP 100,000 remains PHP 100,000 after review.

SES already has a 0–1 scale after this formula. The system does not normalize it again, normalize P separately, stretch the highest SES to 1, or stretch final scores to 100.

The main weighted sum is:

```text
EWS100 = 100 * (
    wSES * SES
  + wES  * normalized_ES
  + wPA  * normalized_PA
  + wHM  * normalized_HM
)
```

Exactly four weighted contributions are retained. There is no HI, SI, fifth 4Ps term or indigency bonus. ES keeps Full-Time Worker=1, Part-Time Worker=2, Seasonal Worker=3, Unemployed=4. ES/HM use increasing pool Min–Max; PA uses inverse pool Min–Max. PA remains the qualifying actual successful, non-voided release count under the bound scope/window/recording cutoff and accepted coverage rules.

Income and other inputs use the bound policy's existing measurement definitions and periods. Income is not divided by household size and expenses are not subtracted by this method. No new income bracket, observation period or PHP cutoff is installed.

## Main weights versus internal coefficients

| Configuration | Control |
|---|---|
| Main SES/ES/PA/HM weights | Editable cascading sliders, priority arrows, calculated AHP preview and authorized shared approval |
| Internal SES coefficients | Exact 9/10 and 1/10 for this formula version; main sliders cannot edit them |

The existing positive-weight, 100% total, priority, maximum 9:1 proposal ratio, strict CR, code association and precision checks remain. New composite calculations use the latest approved calculated weight strings from the Vault and retain that exact approval in the saved calculation. Historical calculations replay their saved weights. The existing asymmetric stored-total restriction is unchanged; a tiny positive AHP rounding excess can still block weight approval.

A later internal coefficient change requires a new supported formula and reviewed policy version. The current policy editor supports this exact 90/10 candidate only.

The Configuration Vault and calculation-rule editor now open composite SES by default, without method-selection tabs. The four main weights use the same volume-style cascading slider editor and priority arrows as the former five-criterion tab. A matching saved proposal reopens automatically. Otherwise all four slider rows appear immediately, marked **Not set**, with no percentage-entry form or separate setup button. Move the top slider to select its weight; its remainder is initially shared equally below it, to hundredths of a percentage point. Then adjust the second and third sliders; the fourth receives the remainder. Priority arrows can move any criterion to the top before choosing weights.

No weight vector is selected, calculated or saved on initial page load. The internal initial allocation used on the first gesture supplies equal proportions for distributing the remainder; it is never installed as a default configuration. After that gesture the usual proportional cascade applies. Resetting a fresh unsaved editor clears the proposal; resetting an editor opened from a saved version restores that version's proposal. No five-criterion vector or example is converted into starting weights. Enter a reason, calculate the AHP preview and approve. The server records the draft and approval atomically; a separate draft-save step is optional. A signed preview must match the current proposal and Vault version.

In the displayed priority order, increasing the first weight proportionally reduces the second, third and fourth; decreasing it gives weight back to them. Changing the second adjusts only the third and fourth. Changing the third adjusts only the fourth. Earlier weights stay fixed and the proposed total stays exactly **100.00%**. The fourth receives the remainder and can be moved higher using the priority arrows for direct adjustment.

For example, a synthetic proposal of 50/25/15/10 becomes 50/25/17/8 when the third slider increases to 17%. Decreasing it to 12.5% produces 50/25/12.5/12.5. These are explanatory proposals, not saved defaults or calculated AHP weights. Priority and the positive maximum 9:1 ratio still constrain movement; the editor explains when an earlier weight or priority needs adjustment to create room.

Historical versions, explicit historical method links and already-open forms retain their original signatures. An already approved compatible income-only SES **main-weight vector** can also be explicitly selected and reviewed in the new composite policy. The old weight record is retained exactly. This does not transfer approval of the old scoring formula, convert a five-criterion version, or approve the new formula automatically.

An unpublished draft with no applications can explicitly bind the new approved policy using its same compatible inherited weight version. Already bound income-only policies, published old-method intakes and historical/scored programs cannot be converted through this ordinary binding action. Existing bindings and runs remain immutable.

## Accepted evidence and 4Ps findings

Use **Enter / verify EWAF information** in the program's existing EWAF Ranking workspace. Staff record the approved income-period amounts, employment, household count, history coverage and supporting evidence, then the new fields:

- Reviewed household 4Ps participation: **Verified Yes**, **Verified No**, or **Unresolved / not reviewed**.
- Confirmation that the applicant's household relationship and applicable participation were reviewed under the approved procedure.
- The evidence-supported household finding, relationship and review basis.

Missing, unanswered, disputed or expired information is unresolved. It is never converted to No through a checkbox or programming default. A No finding must be affirmatively reviewed under the approved procedure.

SES's existing verified supporting-evidence selection now covers the income and household 4Ps review. The same permitted assessment can support both when the bound policy authorizes it. Both findings retain their shared SES verification references in the accepted review. This implementation does not demand a new certificate of non-membership, prescribe extra document types, require an old SI indigency finding, or assume access to DSWD databases. The policy must explicitly identify the permitted evidence and alternatives for Yes and No, the household relationship process and the unresolved/correction procedure.

Membership approval, declarations and ordinary notes do not establish accepted inputs. The existing permission-checked acceptance action requires current verified supporting evidence, exact bound periods, the explicit findings and reviewer confirmation. Evidence ownership, expiry, member version, maximum review age, audit history and source-freshness checks remain enforced. Missing approved procedures block policy approval, not independent development.

Material conflicts require a review of dates, circumstances and evidence. The reviewer must record a resolution before accepting a conflicted income finding. The system does not infer fraud, reject the household automatically, replace the income with a lower amount or award a bonus for the conflicting document.

## Complete-pool rules and ranking

The calculation uses the complete accepted eligible **applicant** pool after approved application closing and the bound cutoff. It does not calculate every registered member, omit unresolved applications or use a filtered/page-sized pool.

All P=0 and all P=1 are valid. P is an adjustment, so constant P does not trigger a constant-column error. Constant income (`U=L`) still blocks generation; so do constant ES, PA or HM columns. No midpoint, epsilon, removed criterion or weight redistribution is introduced.

Changes to income, participation, evidence or the pool require renewed acceptance where applicable and a new complete-pool run. Previous runs remain available. Each run retains accepted H and its assessment period, P and its observation date, SES evidence references, L/U, I, the multiplier, final normalized SES, exact main weights, formula/policy/configuration versions, reviewer/calculation actors and predecessor history.

After a ranking is generated, two program tabs appear: **Scoring Explanation** and **How Calculation Works**. Each applicant's name and score link directly to that applicant's explanation for the same saved run.

Scoring Explanation shows H, income need, the Yes/No finding, internal multiplier, final SES, main SES weight and exact contribution separately. It explains rank as the number of strictly higher exact totals plus one, and shows how many other applicants contributed more, the same or fewer points for each criterion. These comparisons use the complete saved pool and exact contributions, including when displayed numbers round to the same value. “Highest” and “lowest” are relative comparisons within that pool, not need classifications or eligibility decisions. Staff cannot type a final SES score. Private JSON exports retain the same calculation trace and frozen evidence snapshot.

How Calculation Works shows the selected run's method, original criterion set, approved coefficient strings, shared numerical bounds, supported employment encoding, income assessment rule, normalization formulas, composite SES adjustment, weighted sum and exact-tie ranking rule. It distinguishes pool-derived bounds from the configured bounds of historical methods. Both tabs retain the selected calculation, indicate when renewed review is needed, require existing private EWAF permissions and perform no calculation or beneficiary decision themselves.

Ranks remain exact-score competition ranks: `1 + count(strictly higher exact scores)`, with ties such as 1,2,2,4. Half-even two-decimal display does not decide ties. The approved capacity-boundary hold or reasoned-human procedure applies. Ranking does not select beneficiaries or record delivery. Existing human decisions, capacity, release and public-result controls remain separate; private income, P, supporting evidence and scores are not added to public projections.

## Required examples — synthetic only

The following pool has accepted endpoints PHP 0 and PHP 100,000. These are derived fixture bounds, not permanent thresholds.

| Accepted income H | Income need I | SES, Verified No | SES, Verified Yes |
|---|---:|---:|---:|
| PHP 0 | 1.00 | 0.90 | 1.00 |
| PHP 10,000 | 0.90 | 0.81 | 0.90 |
| PHP 50,000 | 0.50 | 0.45 | 0.50 |
| PHP 100,000 | 0.00 | 0.00 | 0.00 |

These SES values are fractions, before multiplication by the main weight and 100. With `wSES=0.40` and `SES=0.90`, the contribution is exactly **36 final-score points**.

In this pool, PHP 20,000 with Verified Yes gives SES **0.80**, while PHP 15,000 with Verified No gives **0.765**. Thus the higher-income 4Ps household has the higher SES contribution when the same positive SES weight is used. Other criteria determine the full EWAF ordering.

Changing No to Yes changes SES by `0.10*I`, not a flat 0.10. If all P=0 and the lowest-income applicant is also best on the other three criteria, main weights 0.40/0.20/0.20/0.20 produce **96**, not a score automatically stretched to 100. These weights are a synthetic test vector, not a default or approval.

If the pool's maximum instead becomes PHP 200,000 while its minimum remains 0, PHP 100,000 has income need 0.50. It is not permanently assigned zero need.

This rule can change the order of applicants with similar incomes. It **does not guarantee fairness**, eliminate overlapping influences among criteria, or independently establish poverty or government-program eligibility. These limitations are also disclosed in the policy UI.

## Admin sequence after authorized setup

1. Open **EWAF Configuration Vault**. Adjust SES / ES / PA / HM using the four sliders and priority arrows, select **Calculate AHP weights**, enter a reason and select **Approve configuration**. New rankings in all compatible four-criterion programs use this approved version. A separate draft save is optional. No example vector is supplied as an approved default.
2. Open **Configure calculation rules** for that method. Select the exact compatible approved vector. Specify the existing income/household/history/evidence operating rules plus household 4Ps relationship and evidence procedures for Yes, No and unresolved outcomes. Review the fixed 90/10 formula separately from the main weights. Choose the **Shared assessment cutoff rule** once: each program's approved application close, or one explicit shared cutoff. Neither choice is supplied as an approved default. Save and explicitly approve A/B/C, including automatic application to compatible programs and that cutoff rule.
3. Complete ordinary program prerequisites and select **Publish** on the program review page. This single action records program authorization and publication; no separate authorization step, typed publication reason or confirmation checkbox is required. Central policy approval automatically binds ready compatible programs to the shared settings, and publication applies them to new programs without another EWAF configuration form. If a future policy becomes effective or prerequisites are completed later, **Apply shared configuration to ready programs** on the central policy review performs the same audited application. Approved weights still permit publication/intake while scoring rules are pending; ranking requires the complete approved binding and accepted evidence.
4. Resolve eligibility for the entire application inventory. After cutoff, verify and explicitly accept income, household 4Ps, ES, PA coverage and HM under the bound policy. Use **Needs information** or **Record disputed inputs** for unresolved cases.
5. Open **EWAF Ranking**, select a program and choose **Generate EWAF Ranking**. Click an applicant's name to see their scoring. Open **How Calculation Works** for the method, bounds and approved weights used in that saved run. For later weight changes, repeat step 1 and generate again; accepted evidence does not need another approval solely because weights changed. Make authorized human decisions under capacity/tie rules; use restricted publication and actual-release controls separately.

No live weights, institutional facts, real approvals, bindings, activation settings or applicant findings were created by this implementation.

## Shared configuration and retained history

The owner's 27 October follow-up authorizes the latest approved composite AHP weights for new calculations across existing and new four-criterion programs. Approving weights does not itself generate rankings. Each Generate action captures the current shared approval, and the complete eligible pool uses that same exact vector. Drafts and unapproved slider changes have no effect. A stale generation request must reload after another weight approval. Existing ranking decisions require a current calculation; previous decisions and deliveries are never rewritten.

Existing scoring bindings keep their method, accepted-input rules, evidence references and cutoff. Their original weight reference remains part of history. A new run can retain a newer exact Vault approval separately without rewriting that binding or fabricating a new evidence review. Historical runs use their original weight reference or their saved shared-approval snapshot on replay and export. Historical five-criterion, income-only SES and fixed-range methods retain their earlier behavior. Incomplete policy, unresolved evidence, expired rules, program authorization and constant-column blockers remain enforced.

A saved calculation that fails policy or integrity validation now produces a review notice on the ranking page instead of a server error. That calculation's scores, decisions and private export remain unavailable, and its record stays preserved. A new Vault approval does not repair or overwrite historical results.
