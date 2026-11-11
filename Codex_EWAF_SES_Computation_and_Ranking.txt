# CODEX — UPDATE EWAF TO SES / ES / PA / HM WITH EVIDENCE-BASED VERIFICATION

## 1. Task and authority boundary

Use `Computation_Updated_SES_ES_PA_HM.docx` as the reference for this NEW revision.

Extend the existing versioned calculation and policy integration; do not build another unrelated engine or restart completed work.

The requested direction is to replace the separate HI and SI weighted entries with one Socioeconomic Status (SES) entry, alongside Employment Status (ES), Previous Assistance Received (PA), and Number of Household Members (HM).

This prompt follows the user's SES direction, rather than the alternative of simply retaining the HI name. Its fully computable demonstration defines SES narrowly as an **income-based proxy after evidence review**. This is not a supplied or validated multidimensional SES index.

4Ps information, Certificates of Indigency and other permitted documents support verification. Their possession, absence or quantity must not automatically award or remove EWAF points.

This authorizes a scoped source-code extension, synthetic tests and a permission-controlled Admin preview for the new method. It does not supply institutional adoption, new approved weights, genuine evidence findings or real-data activation.

Preserve historical models and runs. Internal ranking remains analytical support; public ranks, automatic beneficiary approval, working-database migrations, schedule changes and deployment are not authorized by this prompt.

## 2. Read the sources and reuse the actual implementation

Read the new computation document in full, including its definition of the income-based proxy, example-weight derivation and revision record. Also read the available:

- OVERALL_SYSTEM_SPECIFICATION_INTEGRATED.md and BRAINSTORM_INTEGRATION_LOG.md.
- Current decisions, recorded overrides and workflow guide.
- Latest dataset-policy integration, approved-policy storage, accepted-evidence and preservation reports.
- Existing configuration, calculation, ranking, selection, release and publication services.
- Older HI/SI/ES/PA/HM documents and prompts only as historical sources.

Locate the actual files; do not assume a particular requirements directory. If the new DOCX is absent, report that blocker rather than rebuilding the instructions from an older file.

Inspect the current branch, worktree and existing migrations before editing. Do not infer database state from an older report or reapply a previously applied migration. Preserve unrelated and uncommitted work.

Keep the supplied source documents unchanged. Record this revision under a distinct method/policy version. Four criteria alone do not identify the method: the new SES/ES/PA/HM set is NOT the historical SI/ES/PA/ND set.

## 3. New criterion contract and evidence boundaries

Use this order in matrices, inputs, breakdowns, tests and private exports:

| Code | Criterion | Raw input for this demonstration | Direction |
|---|---|---|---|
| SES | Socioeconomic Status — income-based proxy | Accepted household monthly income in PHP | Inverse |
| ES | Employment Status | Accepted employment category, encoded below | Increasing |
| PA | Previous Assistance Received | Qualifying confirmed, non-voided actual release count | Inverse |
| HM | Number of Household Members | Accepted household headcount | Increasing |

Household income remains a recorded source field. It is not also scored as a separate HI criterion in this new version.

Do not retain a standalone SI contribution, append document bonuses, reuse the proposed older three-domain SI levels, or calculate SES plus HI for the same financial input.

Do not quietly divide income by HM, subtract expenses, add employment effects, or introduce new hardship sub-scores. Those would change the measure and can overlap with the separately scored ES and HM. A broader SES assessment requires its own specified rubric and authorization.

Keep these distinct:
- Raw declaration and its dates.
- Submitted documents and their dates/status.
- Authorized findings and accepted income for the policy's period.
- Evidence-readiness state.
- Normalized SES contribution.
- Final EWAF result and human beneficiary decision.

For the demonstrator, the explicit measurement rule is:

    SES raw input = accepted_household_monthly_income_php

An existing registration approval, a generic review note or an upload success is not accepted scoring evidence. Reuse the existing accepted-evidence service and preserve provenance and invalidation behavior. Never bypass it by reading a raw profile field as verified.

## 4. Resolve document conflicts without rewarding documents

Use the following behavior for the proposed new workflow:

1. A declared income of PHP 100,000 accompanied by 4Ps/indigency documentation can require review of dates, periods and circumstances. It is not an automatic bonus, membership rejection or fraud finding.
2. If review accepts PHP 100,000 for the applicable period, use that amount. The document does not override it or create a second scored value.
3. If material inconsistency remains unresolved, retain Needs Review and the existing complete-pool safeguard. Do not choose whichever claim produces the highest score.
4. An applicant without 4Ps may use the approved evidence/assisted routes. Absence of 4Ps is not a zero-need score or automatic failure of the SES criterion. A separately authorized program eligibility requirement remains separate.
5. Additional copies or types of evidence do not add numerical points. Evidence sufficiency and confidence must not become hidden multipliers.
6. Corrections retain earlier information and create new accepted assessment versions. Changes after a cutoff and corrections to information at the cutoff follow the applicable existing policy.

A Certificate of Indigency must not be assumed to prove a particular income amount by itself. No employer, bank, government API, investigation power or new document requirement is introduced here.

Income basis, included sources, assessment period, approved alternatives and accepting authority still require the applicable recorded operating policy. Do not invent them to activate the feature.

## 5. Four-criterion AHP and the teaching-only weight fixture

No new approved four-criterion weights or pairwise judgments were supplied with this revision.

Do not add the old HI and SI weights together. Do not import, merge, silently normalize or relabel any live five-criterion vector, including the reported version 6 weights. Preserve them for their original methods.

For a reproducible SYNTHETIC FIXTURE ONLY, the new DOCX removes the old SI term from its earlier example and rescales the remaining example values:

    retained = [0.3421, 0.1774, 0.1223, 0.1222]
    total = 0.7640
    q = [3421/7640, 1774/7640, 1223/7640, 1222/7640]

Approximate percentages are 44.77748691%, 23.21989529%, 16.00785340% and 15.99476440%.

This is a transparent arithmetic fixture, NOT recommended official defaults, an approved merging policy or a migration rule. Store it only as synthetic test/demo data, never as an approved policy seed.

For n = 4, retain the source's column-normalization/row-average method:

    A[i,j] = q[i] / q[j]                   # fixture reconstruction only
    s[j] = SUM_i A[i,j]
    N[i,j] = A[i,j] / s[j]
    w[i] = SUM_j N[i,j] / 4
    WSV[i] = SUM_j A[i,j] * w[j]
    CV[i] = WSV[i] / w[i]
    lambda_estimate = SUM_i CV[i] / 4
    CI = (lambda_estimate - 4) / 3
    CR = CI / 0.90

Expected exact fixture results:

    w = q
    WSV = [3421/1910, 887/955, 1223/1910, 611/955]
    CV = [4, 4, 4, 4]
    lambda_estimate = 4
    CI = 0
    CR = 0

Use exact fractions for the fixture. The matrix's rounded display cells are not calculation inputs.

Validate positive reciprocal comparisons, diagonal ones and the documented strict consistency condition 0 <= CR < 0.10. Apply a reviewed numerical-precision policy; do not hide substantive inconsistency behind a broad tolerance.

CR = 0 is guaranteed for a ratio-reconstructed matrix. Label this “Illustrative reconstructed matrix”; it is not independent stakeholder elicitation, truthful evidence or fairness validation.

A real four-criterion AHP configuration needs six recorded independent comparisons and its own authorization. Use RI = 0.90, not 1.12. Do not silently substitute another weight-extraction method.

## 6. Adjustable weights and policy storage

Preserve adjustability through versioned configuration; do not hardcode the fixture percentages for every program.

The former five-criterion slider minima/maxima do not automatically apply to the new four-criterion model. Do not invent replacement ranges or reuse an old SI range for SES.

For a draft preview only, the source's residual-control idea can be adapted as:

    wHM = 1 - (wSES + wES + wPA)

Show all four contributions and validate the total and permitted positivity server-side. Do not silently redistribute other weights. Direct HM editing or a different adjustment rule requires an explicit UI/weighting contract.

Preserve weight provenance. Slider-selected percentages are not independently AHP-derived; reconstructing a ratio matrix must never manufacture approval. A separately authorized manual-weighting method must be labeled accurately.

Reuse existing append-only policy storage and immutable program bindings where compatible. Bind by full method/criterion signature, policy version, compatible weight version and cutoff—not by a dynamic “latest” reference or criterion count alone.

For this new version, official readiness requires explicit adoption of the income-based SES measure, complete data/evidence definitions, new four-criterion weight authority and the existing program prerequisites. Do not require an unrelated legacy SI rubric for this explicitly income-based variant. Do not claim a broader SES model unless one is supplied.

Policy drafts remain drafts. No genuine approvals or accepted evidence may be created by migrations, fixtures or this instruction.

## 7. Encoding and dataset-based Min–Max normalization

Retain this ES encoding from the supplied computation for the fixture:

- Full-Time Worker = 1
- Part-Time Worker = 2
- Seasonal Worker = 3
- Unemployed = 4

Unlisted, mixed or unresolved categories follow the authorized mapping/review rule; do not default them to unemployed.

PA uses actual qualifying releases, not applications, undelivered selections, referrals or attendance. Retain the authorized counting period, scope and coverage checks. Unknown historical coverage is not verified zero.

HM is the accepted household count, not historical ND. Do not invent the household definition or silently include/exclude household members.

For each scored criterion j in the complete frozen eligible/evidence-ready pool:

    L[j] = minimum accepted raw value
    U[j] = maximum accepted raw value

For SES income and PA:

    z[i,j] = (U[j] - x[i,j]) / (U[j] - L[j])

For ES and HM:

    z[i,j] = (x[i,j] - L[j]) / (U[j] - L[j])

The numerical SES contribution is obtained from accepted income once. Do not first create an arbitrary 1–4 SES level or normalize the already normalized contribution again.

Use these directions to reproduce the explicit example. Their operating adoption belongs to the new approved policy; no fixed-bound or historical method is overwritten.

Preserve:
- One complete frozen pool per run; page filters must not determine bounds.
- The required handling of all in-scope applications; no silent exclusion of unresolved cases.
- Blocking on missing, stale, disputed, non-finite or invalid required inputs.
- A clear constant-column stop when U[j] == L[j], including single-applicant pools.
- No midpoint, epsilon, clipping, dropped criterion or redistributed weight unless a separate approved method explicitly supplies it.
- New runs with shared bounds recalculated after accepted input/pool changes; earlier runs retained.
- Full-precision arithmetic and ranking; round display values only.

Dataset-derived bounds belong to the evaluation run, not invented poverty brackets required before any application exists. Do not globally change current publication/opening rules through this task. Reconcile the new version's readiness with the current authorized program workflow without weakening legacy gates.

## 8. Weighted score and optional classification

For this new four-criterion method:

    EWS[i] = wSES*zSES + wES*zES + wPA*zPA + wHM*zHM
    EWS100[i] = 100 * EWS[i]

For the synthetic fixture only:

    EWS100 = (100/7640) *
             (3421*zSES + 1774*zES + 1223*zPA + 1222*zHM)

Do not retain a fifth HI/SI contribution or multiply a percentage-point total by 100 twice.

Raw income, evidence status, encodings, normalized values, weights and contributions must remain distinguishable in records and explanations.

The DOCX retains the old example classification bands only for teaching:
- 80 <= score <= 100: High Assistance Need
- 60 <= score < 80: Moderate Assistance Need
- 40 <= score < 60: Low Assistance Need
- 0 <= score < 40: Minimal Assistance Need

Do not activate these labels where the existing accepted policy disables classification. An operational SES version needs explicit classification adoption; ranking does not require classification. Apply adopted boundaries to unrounded values.

These are relative scores, not a certified poverty status, diagnosis, probability or guarantee of assistance. Do not compare scores across different pools as though they were an absolute socioeconomic scale.

## 9. Internal ranking and separate human decisions

Retain the uploaded prompt's proposed competition-ranking convention for the new Admin preview:

    rank(i) = 1 + count(scores strictly greater than score[i])

Rank unrounded scores from high to low. Exact ties share a rank (1, 2, 2, 4). Presentation order within a tied group must not imply allocation priority.

Do not use names, IDs, time of submission, references, rounded scores or dragging rows to choose winners.

Use the authorized tie procedure or hold a capacity-boundary tie unresolved. A rank never automatically creates a beneficiary decision or assistance release.

No public ranks, scores, full references or sensitive evidence are introduced. Preserve the current allowed public-result projection, permissions and explicit publication controls.

## 10. Mandatory reproducible fixtures and adversarial cases

The source fictional income, ES, PA and HM are retained; the old SI assessed numbers are removed:

| Applicant | Accepted SES income (PHP) | ES encoded | PA | HM |
|---|---:|---:|---:|---:|
| A | 5000 | 3 | 1 | 4 |
| B | 12500 | 4 | 0 | 2 |
| C | 20000 | 1 | 3 | 6 |

Criterion order: SES, ES, PA, HM.

    L = [5000, 1, 0, 2]
    U = [20000, 4, 3, 6]

    zA = [1, 2/3, 2/3, 1/2]
    zB = [1/2, 1, 1, 0]
    zC = [0, 0, 0, 1]

With q from Section 5:

    A = 15075/191 = 78.926701570... -> display 78.93, rank 1
    B = 47075/764 = 61.616492146... -> display 61.62, rank 2
    C = 3055/191 = 15.994764397...   -> display 15.99, rank 3

Demonstration labels, if the teaching bands are explicitly enabled: A Moderate, B Moderate, C Minimal.

Derive the results; do not hardcode them. Use exact reference arithmetic to check the production-precision implementation.

Retain older example tests (83.90 / 62.81 / 12.22) and any recorded version 6 tests under their original method keys. They must not be replaced with the new results.

Add independent scenarios showing:
- Identical accepted input values and accepted status give identical scores regardless of document count or 4Ps status.
- Adding a Certificate of Indigency does not increase a numeric score.
- High income plus conflicting documents is unresolved until reviewed, not automatically max-priority or fraud.
- Accepted high income uses the inverse financial measure despite document possession.
- Low income without 4Ps can be assessed through the authorized alternative route.
- Missing accepted income cannot become zero.
- A document change that invalidates acceptance blocks stale use; this is different from awarding points for the new document.

Do not assert how much a PHP 100,000 applicant scores without specifying the complete frozen pool and all four accepted inputs.

## 11. Admin integration, history and readiness

Keep the eight Admin groups and approved minimalist design. Place new-method controls within EWAF & Selection and reuse existing policy screens, evidence acceptance, calculation storage and authorized decision services.

Show:
- The exact method and criterion signature.
- “SES — income-based proxy” where that is the adopted definition.
- Accepted income source and evidence readiness, separately from the normalized score.
- New weight provenance, policy version and genuine readiness blockers.
- Synthetic versus operational labels.
- Complete contribution trace, private internal rank and tie groups.
- Separate human selection, actual release and public publication states.

Do not rebuild already delivered dataset-policy storage. Add a narrow method-aware extension only where required. Test legacy routes and direct requests, not just visible buttons.

Retain method/policy/weight versions, program, cutoff, applicant inventory, accepted evidence versions, bounds, precision, contributions, actor, timestamps and predecessor for every stored run.

A changed source can invalidate dependent work through existing services; it must not automatically overwrite a historical result, reselect beneficiaries or publish changes.

In-program updates to criterion sets or weights require the authorized revision process. Do not convert existing programs or run both new and old policies opportunistically to obtain a preferred beneficiary list.

## 12. Development restrictions and tests

Preserve legacy code paths, old weights (including version 6), prior migrations, evidence findings, calculations, decisions, releases and publication history. Use a new method identifier containing the full SES/ES/PA/HM meaning; do not select it merely because n = 4.

This is not permission for unrelated registration, referral/email, UI-redesign or government-integration work.

Use synthetic data, verified disposable MySQL and separate test media. Any schema proposal must be additive, narrowly scoped and dependency-reviewed. Do not alter historical migrations, the working/production database, startup guards, credentials, feature activation or approval records. No automatic commit, push, merge or deployment.

Test at minimum:

1. The full four-criterion AHP fixture, n = 4 and RI = 0.90.
2. New exact applicant scores and contributions; preservation of older fixtures.
3. Document/4Ps invariance once equal inputs are accepted; no hidden fifth contribution.
4. Discrepancy review, acceptance provenance, stale documents and privacy permissions.
5. Correct increasing/inverse normalization and no double normalization of SES.
6. Missing, invalid, stale, disputed, unlisted, constant and single-applicant cases.
7. Complete-pool bounds unaffected by pagination or filters.
8. Full-precision ranking, close scores, exact ties and capacity-boundary controls.
9. Four-criterion weight compatibility; rejection of legacy vector/code mismatches.
10. No automatic merging, relabeling or rescaling of approved historical weights.
11. Draft/approved version separation and immutable program binding.
12. Current publication, human-selection, release, audit and concurrency protections.
13. Historical fixed-range and both old four-/five-criterion regressions.
14. Official use blocked without the new measure/weight/policy authority and accepted evidence.
15. No public rank disclosure, document bonus, approval seed or real-data activation.

If a new capability conflicts with a protected contract, report the specific dependency; do not weaken legacy tests or bypass an evidence gate.

## 13. Execute and report

Implement independently safe new-version preview/calculation work and its tests using the explicit demonstration contract above. Do not stop all arithmetic work merely because live policy choices are pending; keep those live features gated.

Return:
- Actual source document and code revision reviewed.
- Exact file changes, any additive schema proposals and dispatch changes.
- Explicit interpretation: an income-based SES proxy, not an invented broad SES index.
- Full computed fixture results and evidence/document-invariance tests.
- Actual test commands, passes, failures, overlaps and untested areas.
- Historical weight/configuration/result preservation evidence.
- Which readiness checks are implemented and which approvals remain genuinely missing.
- Any behavioral difference from current dataset-policy integration, with no silent changes.
- Demonstration availability versus real-data activation status.

New four-criterion weights and institutional adoption are still required; test fractions and successful tests do not supply them. Preserve the recorded accepted milestone unless the owner separately updates it.

Update progress without overwriting earlier records. Stop after the implementation report. Do not activate official scoring, modify schedules, migrate the working database or publish rankings automatically.
