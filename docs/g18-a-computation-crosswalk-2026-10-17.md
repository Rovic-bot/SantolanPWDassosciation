# G18-A computation reconciliation and policy crosswalk

Started: 2026-10-17; validation completed 2026-10-18, Asia/Manila. Existing local `feature/events` workspace.
**Accepted milestone: 70%. Stage 8 remains in progress; no 80% claim.**

## G18 policy amendment recorded 2026-10-18 — PR removed from scoring

The owner confirms that the **Association President approved removing Program
Relevance (PR) from EWAF scoring** and making it a mandatory program-specific
eligibility requirement before EWAF. The revised scoring criteria are **SI, ES,
PA, ND**. The approval date of this amendment is **unknown**; the recording date
above is not the approval/effective date, and approximately May 2026 is not used.
The amendment applies only to specifically authorized programs; none are inferred
from publication status, an EWAF flag, an old configuration or this document.

Distinguish these authorities and statuses:

| Item | Status and boundary |
| --- | --- |
| Historical five-criterion Association-approved computation | Described as such by the owner in this amendment. Preserve its methodology, configurations, digests, traces, audits and exact replay as historical evidence. This does not retrospectively establish live software acceptance, dates, program scope or approval of every sample coefficient. |
| Removal of PR from scoring | President-approved amendment, as confirmed by the owner. Only for specifically authorized programs; approval date and effective program bindings remain unestablished. |
| Four-criterion AHP values | **Proposed revised configuration, pending explicit Association confirmation.** Recomputed from the six retained judgments, not manually assigned or renormalized old weights. RI = 0.90 for n = 4. |
| Program Relevance | Mandatory program-specific eligibility requirement, with documented actual functional need and verified evidence before candidate admission; no PR contribution or bonus in revised scoring. |
| Computation.docx | Remains a proposed reference, not a blanket approved replacement of the workbook or an operational scoring authorization. |

The matrix in SI, ES, PA, ND order is:

| | SI | ES | PA | ND |
| --- | --- | --- | --- | --- |
| SI | 1 | 2 | 3 | 5 |
| ES | 1/2 | 1 | 2 | 4 |
| PA | 1/3 | 1/2 | 1 | 3 |
| ND | 1/5 | 1/4 | 1/3 | 1 |

Proposed 50-digit Decimal reference values:

```text
SI = 0.47085905179088958208889183867613548372823610097122
ES = 0.28401252184686179509302891528948474591270104643702
PA = 0.17148293179354439061082719408862635782394194818699
ND = 0.073645494568704232207252051945753412535120904404772
lambda_estimate = 4.0513654728589442612068089407860696967972113290515
CI = 0.017121824286314753735602980262023232265737109683833
RI = 0.90
CR = 0.01902424920701639303955886695780359140637456631537
```

Active verified membership, approved disability/qualification requirements,
required documents/verified evidence, actual functional need/program relevance,
and any additional approved assessment must all precede revised EWAF admission.
A disability label alone does not establish hospital-bed need. Authorized home
assessments require consent, private evidence, reviewer provenance and approved
accessible alternatives; these are design requirements, not a new mandatory home
visit for every applicant. Incomplete or disputed applications stay in the full
inventory for review; only confirmed eligible applications enter a future scoring
pool. No PR score is converted automatically to an eligibility pass/fail.

Remaining gaps include numerical-configuration confirmation, SI/ES/PA/ND measurement
and evidence rules, all normalization directions/bounds, PA measure/lookback,
classification boundaries, ties, program-specific functional-need criteria,
assessment consent/alternatives, designated configuration approver, approval and
effective dates, and explicit program scope. The President's amendment approval is
known; it is not an inferred delegation of every future operational approval role.

See [the separate versioned design and validation report](g18-pr-amendment-validation-2026-10-18.md).
No old `CRITERIA`, engine, schema, migration, runtime workflow or guard is changed.
The existing five-criterion preparatory UI remains historical groundwork; it cannot
create an authorized revised four-criterion policy. G18-B has not begun.

**Historical checkpoint below:** the original G18-A evidence remains for provenance.
References to PR scoring, five criteria or unresolved PR placement describe that
earlier checkpoint and do not override the amendment above.

## Authority and inspection

This implements only G18-A of `../../EWAF_Stage8_to_80_Implementation_Handoff.md`.
`../../Computation.docx` is a newly supplied **reference**, not proof of Association
approval or a replacement of `../../00 - Project Overview/Computation - final.xlsx`.
The governing source priority, Open Decisions, DEC-024/025/027, membership/PDAO
separation and existing operational barriers remain intact. No institutional
decision is inferred from a mathematically consistent matrix or these tests.

Read the DOCX paragraphs and tables directly from OOXML, and extracted and visually
inspected all eight embedded formula images. Formula images establish normalized
cell division, row averages, WSV, CV, estimated lambda, CI, CR and ascending min–max.
Locators below are section/table labels, not unverified page numbers. No full-page
document layout or page-count validation was performed; this is computation review.
Read the original XLSX worksheet XML, shared strings, exact formulas and stored
values separately. Shared-formula followers retain their anchor/index information.
The workbook was not repaired, saved or recalculated in Excel.

| Source | SHA-256 |
| --- | --- |
| Computation.docx | `f91591c4df9e9b3ca15aaf86b457f53da214e2c6844111203749e54849108668` |
| Computation - final.xlsx | `060dee928997f913127e4ba1644416c2a6b0f2df54b066dd93cd3c5f2df3d31f` |
| Stage 8 handoff | `0e0630b8755e58252c23ec084f6f81dfde59b83bc319182e87fe53457533f5eb` |

Source extractions and initial/final hash evidence are retained under ignored
`.local/g18-a/`. No source binary was copied into application/static assets.

## Side-by-side reconciliation

All workbook addresses refer to `Sheet1`.

| Topic | Computation.docx | Workbook evidence | Existing local code / G18-A disposition |
| --- | --- | --- | --- |
| Criterion order | Table 2: PA, SI, ES, ND, PR | C2:G7 and B3:B7 use that order | G14–G17 and durable arithmetic use SI, ES, PA, ND, PR. Fixture maps both axes by name, never by position. |
| Pairwise judgments | Exact fractions, including 1/3 | D3/C6/D7 store decimal approximation `0.33333333333333331` | G14 ten-pair mode derives reciprocals at 50 digits. Source matrix is reference only; no judgments prefilled. |
| AHP weights | Normalize each column, average each row; table 5 displays four decimals | C12:G16 formulas use IMDIV; C20:G24 are literal copies. C29:C33 use AVERAGE(Q10:U10) through AVERAGE(Q14:U14), with stored `#DIV/0!` | Preserve `ahp_validation.py`, `g14-ahp-1`, normalized-column row averages. Independently recompute from original matrix. Never copy error cells or treat downstream literals as repaired results. |
| WSV/CV | Tables 6/7; WSV = A·w and CV = WSV/w | F29:J33 are literal products; F35:J35 sum them. B45:P49 repeat literal inputs and product formulas; C58:E62 hold literal weights/WSV/CV | Test full canonical WSV/CV and independent exact rational results. Preserve source history; no workbook dependency repair. |
| Lambda/CI/CR | Estimated lambda 5.0799, CI 0.0199, CR 0.0178; n=5, RI=1.12, CR<0.10 | E63 `AVERAGE(E58:E62)` cache 5.0798617323630735; E64 `IMDIV(E63 - 5,5-1)` cache 0.0199654330907684; E65 `IMDIV(E64,C71)` cache 0.0178262795453289 | G14 recomputes canonical arithmetic, strict unrounded CR comparison, no negative-CI clamp. Mean CV is the method's lambda estimate, not a separate exact eigenvalue computation. |
| ES encoding | Table 9: Full-Time Worker 1, Part-Time Worker 2, Seasonal Worker 3, Unemployed 4 | D80:E83 same examples | G12 categories and G15 encodings are explicitly recorded proposals; no universal defaults. All category/evidence/expiry/direction decisions remain pending. |
| PR encoding | Table 10: Not Aligned 1, Partially Aligned 2, Highly Aligned 3, Fully Aligned 4 | D85:E88 same examples | G12 requires item-level supported relevance findings; G15 records proposed encoding. Do not map labels to eligibility or points automatically. |
| Normalization bounds | Min-Max section defines min/max **within the dataset** | C81:C85 use particular example cells, not MIN/MAX over a frozen eligible-pool range | G15 `synthetic-fixed-bounds-1` requires explicit fixed L/U plus direction. Proposed cohort rules stay pending. Do not replace this contract in G18-A. |
| SI direction | Ascending min–max; no inverse stated; SI meaning unspecified | C82 `IMDIV(E93-E92,E94-E92)`; sample income 5000/8000/20000 produces 0.2 | Higher income increases example value, conflicting with historical inverse wording. OQ-06/18/23 unresolved; sample income is not authorized policy. |
| PA direction | No inverse stated or scope/window definition | C81 `IMDIV(E102 -  E101,E103 - E101)`; sample 0/1/3 receipts produces 1/3 | G12 derives actual non-voided releases. Scope/lookback/count-vs-amount/direction remain OQ-08/19/23; attendance and undelivered selections never count. |
| ND measurement | Named Number of Dependents; no definition/cap | C84 `IMDIV(E98-E97,E99-E97)`; sample 0/2/5 produces 0.4 | Explicit verified count remains separate from missing. No inferred household definition, cap or bound. |
| EWS | Sum(weight × normalized value) | H80:H84 products of literal F/G inputs, H86 SUM cache `0.40533333333333321`; normalized copies are disconnected from C81:C85 | G15/durable kernel computes both 0–1 and 0–100 scales with full 50-digit traces. No live numerical run, sample-member import or classification. |
| Classification | Table 11: minimal 0–39.99, low 40–59.99, moderate 60–79.99, high 80–100 | F90:G93 same printed bands, not formula-driven classification | OQ-25 pending. Proposed half-open intervals below remain prose; no threshold defaults or band calculator. |
| Ranking and decisions | Human Validation retains administrators' final decisions | No accepted operational tie/capacity/effective authority contract | G16 exact comparisons are fictional; G17 simulated history and durable test-only calculations retain barriers. No business ranks, selections, public outcomes or actual releases added. |
| Workflow conflicts | Member accounts; valid PWD identification; EWS used for eligibility validation | Workbook establishes mathematics, not workflow authority | Preserve no member login, onsite membership/manual PRPWD and separate PDAO guidance. Required evidence and eligibility precede EWAF; no inferred PDAO-ID prerequisite. |

## Exact reference replay

Document matrix (table 2):

| | PA | SI | ES | ND | PR |
| --- | --- | --- | --- | --- | --- |
| PA | 1 | 1/3 | 1/2 | 3 | 2 |
| SI | 3 | 1 | 2 | 5 | 3 |
| ES | 2 | 1/2 | 1 | 4 | 2 |
| ND | 1/3 | 1/5 | 1/4 | 1 | 1/2 |
| PR | 1/2 | 1/3 | 1/2 | 2 | 1 |

G14 named pairs: `SI:ES=2`, `SI:PA=3`, `SI:ND=5`, `SI:PR=3`, `ES:PA=2`,
`ES:ND=4`, `ES:PR=2`, `PA:ND=3`, `PA:PR=2`, `ND:PR=0.5`.
No rounded weight is an input.

Display excerpts below are rounded to 18 decimal places for this report only.
The fixture and assertions retain **all** canonical digits, including every
normalized cell, column total and finite arithmetic residual.

| Criterion | Weight | WSV | CV |
| --- | --- | --- | --- |
| SI | 0.403684469321909458 | 2.071430476690848102 | 5.131310798679823932 |
| ES | 0.248241086884771085 | 1.273272711351802830 | 5.129177958936477116 |
| PA | 0.168025542061551519 | 0.850325629851161809 | 5.060692674567706438 |
| ND | 0.063520251109719051 | 0.320590256026835330 | 5.047055866845947310 |
| PR | 0.116528650622048888 | 0.586263957088618111 | 5.031071362785424552 |

Canonical G14 results:

```text
lambda_estimate = 5.0798617323630758694917007061052639171313216033904
CI = 0.0199654330907689673729251765263159792828304008476
CR = 0.017826279545329435154397479041353552931098572185357
```

The reference passes CR < 0.10. Effective authorization and operational readiness
remain false. G14's 50-digit weight-sum residual is -1e-50 (within its existing
1e-45 engineering tolerance); exact rational weights sum to one. No renormalization
or arithmetic change was made.

The independent fixture calculation uses Decimal arithmetic from the source
fractions without importing G14. Tests then compare G14 exactly to that fixture
and separately compare every stage with an exact Fraction oracle (error < 1e-47).
They also cover order permutations, positional-copy detection, hostile ambient
Decimal settings, source-display discrepancies, input immutability and closed gates.

Discrepancies requiring accurate presentation:

- ES directly rounds to **0.2482 / 24.82%**, not document table 5's 0.2483 / 24.83%.
- CI directly rounds to **0.0200**, not the document's 0.0199.
- The handoff's short weight decimals differ in their final displayed digits from
  this exact-fraction/canonical replay (e.g. SI ends `...943` there versus a properly
  rounded 17-place `...946`). Its matrix and ten-pair mapping agree. Use the full
  tested canonical values, not the handoff's abbreviated weight table.
- Workbook caches/literals and document display values are separate evidence;
  neither is represented as fresh Excel recalculation.

## Historical G18-A policy-readiness inventory

At the original G18-A checkpoint all rows remained **pending Association decision**. The review UI presents this
inventory as prose, not configuration JSON or an approval form.

| Decision | Specified reference | Still required before live use |
| --- | --- | --- |
| Source authority | Two supplied computation sources and handoff | Draft vs approved replacement; attesting role, reference, effective date, program scope (OQ-09/26). |
| AHP | Five names, matrix, row-average method, RI and CR reference | Actual approved judgments/scale, method acceptance, precision/storage/display and failed-draft/revision policy (OQ-10/12). |
| SI | Name and workbook sample monthly income | Measure, household/individual basis, unit, period, range, accepted evidence/expiry and direction (OQ-06/18/23). |
| ES | Four proposed categories/encodings | Exhaustiveness, unknown/self-employment/unpaid-carer/unable-to-work handling, evidence/expiry and direction (OQ-07/23). |
| PA | Name and workbook count illustration | Types, amount/count, period, cutoff, cross-program scope, non-voided release/reversal handling, direction (OQ-08/19/23). |
| ND | Name and illustrative counts | Dependent/household definition, verified integer range/cap, evidence/expiry and direction (OQ-07/11/23). |
| PR | Four proposed categories/encodings | Program-specific rubric, item evidence/outcomes, aggregation, Not Aligned eligibility meaning, expiry and direction (OQ-07/23). |
| Evidence | Human validation | Reviewer authority, accepted alternatives, observation/expiry, dispute, missing/unverified input and source-correction/revalidation (OQ-02/23/24). |
| Normalization/pool | Document dataset min–max; code fixed-bound synthetic profile | Explicit method choice, directions, exact frozen full eligible pool/cutoff, all-equal, missing, outlier and cohort-change behavior (OQ-11/18/19). |
| Scale/bands | 0–1 EWS and printed 0–100 bands | Approved ×100 conversion, exact unrounded boundaries, endpoint inclusion and labels (OQ-12/25). |
| Ranking/selection | Human final validation | Direction, exact ties, capacity, exceptions/rationale, evaluation cutoff, repeat/supersession and separate disclosure (OQ-13/15/22). |
| Operations | Existing locks/history and development-only barriers | Institutional approval/locking, officer scope, source invalidation, atomic current promotion, acceptance; G18-B onward and G06-B2/B3 remain separate (OQ-09/16/26). |

Candidate band convention for review only: `0 <= s < 40`, `40 <= s < 60`,
`60 <= s < 80`, `80 <= s <= 100`, with s on the unrounded 0–100 scale.
Literal closed two-decimal bands would leave 39.995, 59.995 and 79.995 uncovered.
No rounding-to-classify or endpoint choice is implemented.

## Bounded implementation and next review

The existing configuration detail and draft/review forms link to a read-only,
permission-controlled policy checklist. Ten comparison fields remain blank and
now explain importance direction separately from applicant normalization direction.
Existing draft/validation/review/non-effective documentary services, audit locks,
CSRF, stale-context checks and history semantics remain unchanged. Policy questions
can be documented in existing review explanations/correction requests; no new
policy persistence, approval status or migration is introduced.

**Original G18-A review request, now qualified by the amendment above:** establish
source authority and the remaining effective-date/scope and numerical-policy decisions.
The owner has since confirmed that Computation.docx stays proposed and that PR
removal is approved; revised weights, program binding and other policies remain pending.
G18-A stops here for review. Source invalidation/atomic promotion (G18-B), expanded
Admin workflow (G18-C), human selection (G18-D), and acceptance/80% (G18-E) were not
implemented or certified by this increment.
