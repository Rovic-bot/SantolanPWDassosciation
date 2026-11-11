# EWAF adjustable weight behavior and governance clarification

Date: 25 October 2026. Status: **documented proposal; operational activation not authorized**.

The owner's latest clarification defines four independently editable draft weights and an automatically calculated HM remainder. The proposed defaults total exactly 100%. They are draft starting values, not a newly approved AHP matrix or operational scoring configuration. Until the weight-governance and scoring decisions below are approved, adjustments are exploratory proposals only.

This clarification governs the intended behavior following the earlier [one-click configuration work](../ewaf-one-click-2026-10-25/validation.md). A simple approval UI does not authorize automatic use of manual proposals or establish that the current implementation conforms to this clarification. Existing protected code, runtime files, calculations and history remain unchanged in this task.

## Proposed defaults and controls

| Criterion | Default | Proposed individual limits | Intended control |
| --- | ---: | --- | --- |
| Household Monthly Income (HI) | 34.21% | 26.40%–62.55% | Independently editable draft slider or increment/decrement |
| Socioeconomic Indicator (SI) | 23.60% | 19.48%–34.21% | Independently editable draft slider or increment/decrement |
| Employment Status (ES) | 17.74% | 14.07%–23.60% | Independently editable draft slider or increment/decrement |
| Previous Assistance Received (PA) | 12.23% | 12.23%–17.74% | Independently editable draft slider or increment/decrement |
| Number of Household Members (HM) | 12.22% | No separate policy minimum or maximum approved | Read-only remainder, adjusted indirectly by the other four |

All five contributions can change. HM has no independent editable control. Changing HI must leave SI, ES and PA unchanged; the same rule applies to each of the four controls. HM remains the remainder regardless of display order. The clarification does not authorize automatic priority sorting, redistribution among other criteria, or a constraint that HI must always outweigh SI or HM.

Preserve these exact defaults for a new exploratory proposal and an explicit reset-to-defaults action. Resetting a proposal cannot overwrite an approved version. The input step, storage precision and display rounding still need an explicit implementation decision; two-decimal values do not establish a production rounding policy.

## Supported arithmetic combinations

All quantities below are percentage points. A draft is arithmetically feasible exactly when its four entered weights are finite numbers within their individual intervals and their sum is no more than 100:

```text
26.40 <= HI <= 62.55
19.48 <= SI <= 34.21
14.07 <= ES <= 23.60
12.23 <= PA <= 17.74

HM = 100 - (HI + SI + ES + PA)
HI + SI + ES + PA <= 100
```

These constraints describe the proposed arithmetic domain, not the set accepted for official AHP scoring. In particular, arithmetic feasibility alone does not establish positive-matrix compatibility, an acceptable CI/CR, verified inputs or approval.

For a control `i`, hold the other three entered weights fixed:

```text
effective_upper_i = min(individual_upper_i, 100 - sum(other three weights))
effective_lower_i = individual_lower_i
```

If a policy minimum `m` for HM is later approved, replace the upper-limit expression with `min(individual_upper_i, 100 - m - sum(other three weights))`. No value of `m` is selected here. If the resulting upper bound is below the lower bound, there is no valid setting in that state; show the conflict without changing the other weights. A maximum HM policy, if ever proposed, requires its own approval.

With the other three controls at their defaults, the feasible upper values are HI **46.43%**, SI **34.21%**, ES **23.60%** and PA **17.74%**. These limits change as the other controls change.

### HI and HM boundaries

The minimum sum of HI, SI, ES and PA is `26.40 + 19.48 + 14.07 + 12.23 = 72.18`. Consequently, the mathematically reachable HM envelope under the proposed intervals and nonnegative-remainder rule is **0%–27.82%**. This is a derived envelope, **not an approved HM policy range**. The 12.22% default is neither a minimum nor a maximum.

The greatest arithmetically feasible HI is `100 - 19.48 - 14.07 - 12.23 = 54.22%`, reached only with the other three controls at their minimums and HM at zero. Thus **HI 62.55% is unreachable anywhere within the other proposed limits**: even those minimums would produce HM = −8.33%. The declared 62.55% endpoint is retained as proposed; it is not silently replaced with an operational cap.

The existing positive reciprocal AHP engine cannot use a zero-weight criterion. If all five criteria remain in that engine, HM must be strictly positive for AHP processing, but this mathematical requirement does not establish a policy floor such as 1%, 5% or 12.22%. In a continuous domain, HI then approaches 54.22% without attaining it. Any discrete maximum depends on the approved step/precision. Removing a zero-weight criterion would change the matrix size and RI and requires separate methodology approval.

## Valid and invalid examples

| Scenario | HI | SI | ES | PA | Computed HM | Assessment |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Supplied defaults | 34.21 | 23.60 | 17.74 | 12.23 | 12.22 | Arithmetic valid; exploratory |
| Change only HI to 40 | 40.00 | 23.60 | 17.74 | 12.23 | 6.43 | Arithmetic valid; other controls unchanged |
| All four minimums | 26.40 | 19.48 | 14.07 | 12.23 | 27.82 | Arithmetic valid; HM may exceed HI/PA |
| SI exceeds HI | 26.40 | 34.21 | 14.07 | 12.23 | 13.09 | Arithmetic valid; no descending-priority rule assumed |
| Total boundary | 54.22 | 19.48 | 14.07 | 12.23 | 0.00 | Arithmetic boundary only; incompatible with current positive-weight AHP |
| HI endpoint, others at minimums | 62.55 | 19.48 | 14.07 | 12.23 | −8.33 | Reject: negative HM |
| All four maximums | 62.55 | 34.21 | 23.60 | 17.74 | −38.10 | Reject: negative HM |
| HI below its individual minimum | 26.39 | 23.60 | 17.74 | 12.23 | 20.04 | Reject: HI outside its interval, despite positive HM |

Of the 16 combinations made solely from each control's lower/upper endpoints, seven satisfy the arithmetic constraints. The inequality system above describes all feasible interior combinations; passing an endpoint check is not operational approval.

Invalid edits must not commit to the accepted draft. Keep its previous valid values, explain the proposed limit or remaining-budget conflict, and allow the Admin to revise the attempted input. Show all five current percentages, the computed HM and a 100% total for the accepted draft. Do not silently clamp HM to zero, rescale weights, alter other controls, or claim an invalid candidate has a valid total. Empty, malformed and nonfinite inputs require an understandable error. Future UI validation and server validation must enforce the same rules.

## Relationship to the existing AHP engine

The inspected [five-criterion engine](../../ewaf/household_math.py) takes ten reciprocal pairwise judgments on the existing discrete `1/9 … 1/2, 1, 2 … 9` scale. It normalizes matrix columns and averages the rows to obtain weights. It calculates `WSV = A × w`, `CV_i = WSV_i / w_i`, the mean CV lambda estimate, `CI = (lambda - 5) / 4`, and `CR = CI / 1.12`. Its passing condition is `0 <= CR < 0.10`; exactly 0.10 fails. These are current engine settings, preserved here.

The current [weight proposal adapter](../../ewaf/weight_input.py) requires positive weights, descending priority order and a maximum-to-minimum ratio of at most 9. It converts proposed ratios to the nearest supported discrete comparisons using multiplicative error, then derives a new AHP vector and checks consistency and ordering. Those constraints are current adapter behavior, not newly approved restrictions on this exploratory UI.

Read-only evaluation of the supplied defaults through that exact adapter produces:

| Criterion | Supplied manual proposal | Current adapter's derived display weight |
| --- | ---: | ---: |
| HI | 34.21% | 36.83% |
| SI | 23.60% | 20.64% |
| ES | 17.74% | 20.64% |
| PA | 12.23% | 10.95% |
| HM | 12.22% | 10.94% |

The resulting lambda estimate is approximately **5.013255811363**, CI **0.003313952841**, and CR **0.002958886465**. Passing CR does **not** preserve the proposed percentages or approve them. PA's derived weight is below the proposed slider minimum of 12.23%. PA and HM have identical full-precision derived weights here; their displayed 0.01-point difference comes from the current largest-remainder rounding that keeps the display total at 100%.

Arbitrary positive weights can be used to construct `a_ij = w_i / w_j`; that matrix is perfectly consistent by construction and reproduces those weights. For example, the proposed defaults give `HI/SI = 3421/2360`, which is not one of the existing discrete judgments. Such a construction would make CI/CR zero by construction rather than validate independently elicited judgments. Adopting continuous ratios or direct manual weights is a methodology decision, not a permissible shortcut around the existing engine.

The workbook's recorded formula/cache evidence also remains unchanged: C29:C33 average empty ranges and store `#DIV/0!`; downstream weights are literal copies. The original workbook uses different historical criterion meanings. Neither its caches nor a relabeled historical vector approves this HI/SI/ES/PA/HM proposal. See [Workbook Formula and Cache Evidence](../../../00%20-%20Project%20Overview/Workflow%20References/2026-10-10/Workbook%20Formula%20and%20Cache%20Evidence.md).

## Current implementation gaps

| Inspected behavior | Difference from this clarification |
| --- | --- |
| [Slider cascade](../../static/js/ewaf-weights.js) redistributes weight across all lower-priority criteria | At HI = 40%, it changes SI/ES/PA/HM to 21.52/16.18/11.15/11.15. Intended values are 23.60/17.74/12.23/6.43. |
| Priority arrows reorder criteria; the last position receives the remainder | The intended automatic criterion is always HM. |
| Empty configuration starts with equal 20% proposals; bounds are dynamically calculated | The requested defaults and individual ranges are not implemented. |
| [One-click vault approval](../../ewaf/vault_services.py) projects weights and immediately records a locked revision, reusing active policy where present | The new draft-review/methodology approval boundary is not implemented by that path. A source-only policy blocks calculation, but that does not make every proposal draft-only when a full active policy exists. |
| [Vault page](../../templates/ewaf/vault.html) has no draft-save action and hides the separate AHP preview step | The requested pre-approval review process requires future scoped work. |
| [Vault history](../../ewaf/vault_models.py) and [operational configuration](../../ewaf/operational_models.py) are immutable, audited and versioned | Preserve these controls and existing program-version bindings. |

These findings do not authorize a rollback, runtime restart, new activation or changes to the protected implementation. Existing code is not represented as compliant with the newly clarified proposal. No approval service was invoked during this validation.

## Decisions required before official use

1. **Weight derivation and purpose:** confirm exploration-only use, or approve a defined path from a proposal to official pairwise judgments. Decide whether judgments must be independently elicited/reviewed, whether the existing discrete ratio projection is acceptable, or whether a different method requires a separately approved engine revision. No path is selected by this document.
2. **Defaults and limits:** approve the actual ten-judgment matrix and its derived vector; resolve differences from the supplied manual defaults. Decide whether the intervals govern proposals only or also final derived weights. If they govern final weights, the demonstrated PA result cannot be accepted automatically. Confirm treatment of the unreachable HI endpoint.
3. **HM:** determine whether an explicit policy floor/ceiling is required and how to handle the zero-remainder boundary. No independent HM minimum/maximum has been approved. Preserve a five-positive-criterion engine unless a different criterion-count method is explicitly approved.
4. **Precision and comparison rules:** approve increment size, storage/display rounding, acceptable proposal-to-derived deviation, and whether any priority-order rule is wanted. Do not infer these from the old cascade implementation.
5. **Governance:** confirm the authorized approving capability, effective scope/version and when a new version may be adopted. Proposed edits cannot mutate a configuration already used by an active evaluation or silently rebind that evaluation to a new version.
6. **Complete scoring policy:** resolve criterion encodings, evidence/optional-4Ps handling, income/PA directions, normalization bounds, missing/stale input treatment, classifications and ties before activation. Member data sources and weight percentages do not resolve these rules. See [Open Decisions](../../../00%20-%20Project%20Overview/Open%20Decisions.md), especially OQ-06–13, OQ-18–19, OQ-23 and OQ-25.

## Required approval and locking process

The intended future sequence is **draft proposal → review → approved AHP derivation and complete scoring-policy validation → explicit authorization → new locked version → authorized use**. Draft review must show the manual vector, the exact proposed matrix and its provenance, the independently derived vector, differences, CI/CR and unresolved blockers. Keep labels such as “Manual proposal” and “Derived from reviewed matrix” distinct.

Until the decisions above are approved, draft review cannot lead to operational authorization. After approval of the governance path, one final confirmation may provide the simple approval action the owner requested; it must attest to the exact reviewed version and cannot silently generate and authorize an unreviewed replacement vector. Enforce permissions, stale-version detection, atomic audit/approval and server-side validation. A failing or incomplete proposal stays unapproved.

Persist the approved matrix, exact weights, calculation method/precision, CI/CR/RI, scoring/source rules, actor/time, reason/provenance and predecessor in a new immutable version. Pin an active evaluation to its existing approved version. Later changes start a separate draft; any future migration or recalculation of an active pool needs an explicitly approved transition and preserves earlier results. Configuration approval remains separate from eligibility, human beneficiary selection and actual releases.

## Validation evidence and acceptance boundary

The [reproducible analysis](validate_proposal.py) passed **40,004 single-control checks**, **16 endpoint combinations**, **10,000 seeded combinations**, exact-ratio consistency identities, and comparisons with the existing AHP adapter and slider cascade. [Detailed results](validation-results.json) retain the exact matrix, derived weights and CI/CR. The 0.01-point enumeration grid is an analysis choice, not a newly approved UI precision.

The script imports the pure arithmetic engine and evaluates the adapter's exact arithmetic function bodies without Django setup, ORM models or application settings. It requires no database, server, migration or approval action. This validates the proposed arithmetic and documents current differences; it does not test or implement a new interactive UI, activate a configuration, validate real applicant scoring, or establish institutional acceptance.

Before/after SHA-256 comparisons confirmed **821 protected source and local-runtime files unchanged**; see [preservation evidence](preservation.json). All new files for this clarification are confined to this documentation directory.

Future acceptance must verify all documented boundaries and examples; immediate HM updates; unchanged nonedited controls; rejection without silent adjustment; visible manual/derived differences; review before authorization; failed/incomplete AHP blocking; and preservation of active evaluations and historical results. Implementation remains pending the owner's scoped authorization after policy decisions.
