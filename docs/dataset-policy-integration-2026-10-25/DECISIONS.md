# New dataset EWAF decision package

Status: REVIEW ONLY. No institutional policy adoption, working database record, activation, publication or schedule change is made by this artifact. Every operational choice starts unspecified. Supported software options are candidates for explicit review, not approved policy. The original DOCX and prior draft remain unchanged.

## A. Existing locked weights and proposed compatible reuse

Existing system record: Vault revision 6, recorded 2026-10-25 12:55:41.082185 UTC. Digest: `cc6641ddf83bc8402f8af3952f6b8e9caafe68454b7c3aae59c4c622a1c2004e`. Source contract: `registered_household_vault_v1`, scope `weights_and_sources`.

| Criterion | Exact stored decimal |
|---|---|
| HI - Household Monthly Income | `0.30653679653679653679653679653679653679653679653678` |
| SI - Socioeconomic Indicator | `0.24795093795093795093795093795093795093795093795094` |
| ES - Employment Status | `0.18937950937950937950937950937950937950937950937951` |
| PA - Previous Assistance Received | `0.14215728715728715728715728715728715728715728715729` |
| HM - Number of Household Members | `0.11397546897546897546897546897546897546897546897547` |

The existing weight authorization/provenance is retained. Its slider-ratio origin is not independently elicited AHP validation. The displayed proposal percentages are not substituted for these weights. The exact sum is 1 - 10^-50. Proposed reuse preserves every stored decimal without rescaling; adoption of that reuse/precision treatment for the new method is still required. Fixed encoded SI or older PA/SI/ES/ND/PR and SI/ES/PA/ND contracts are rejected for reuse.

Decision mapping: `WEIGHT_AUTHORITY` belongs to A. The weight values are already recorded and locked; compatible use with this new policy is proposed, not yet approved.

## B. Full proposed SI rubric

A trained, authorized assessor assigns one level after a documented assessment. This is a new proposal, not a rubric supplied by the DOCX.

Domains: Food access; Stable housing and essential utilities; Access to necessary care and daily support.

| SI | Proposed accepted finding |
|---|---|
| 1 | Accepted assessment confirms no unmet barrier in the listed domains during the assessment period. |
| 2 | Occasional shortfall in at least one domain, without a recurrent or current critical barrier. |
| 3 | A recurrent unmet barrier in one domain, without a current critical barrier or recurrent barriers in two domains. |
| 4 | A current critical unmet barrier in any domain, or recurrent unmet barriers in at least two domains. |

Consider levels 4, 3, 2, then 1; choose the highest supported level. Missing or disputed assessment receives no level. Review must define occasional, recurrent and critical before adoption.

Do not add points for income amount, employment category, household count, past releases, disability label, 4Ps membership, or number of documents. Assess the documented barriers themselves.

Association authority must approve or replace this rubric, assessor qualifications, evidence standards, operational definitions, correction process and consistency checks.

Decision mapping: `SI_RUBRIC_AUTHORITY` belongs to B. Occasional, recurrent and critical definitions; assessor qualifications, calibration, correction checks and adoption authority remain unspecified. Synthetic tests do not adopt this rubric.

## C. Complete data-handling package

The DOCX already discloses the ES mapping, dataset normalization, directions and weighted sum; that is documentary provenance, not a recorded operational adoption. Prior draft proposals are identified below. All choices require explicit completion/review. Blank values cannot be approved. Document type IDs and descriptions are snapshotted; changed definitions require a new reviewed version.

Decision mapping: `DOCUMENT_RULE_ADOPTION`, `CONSTANT_COLUMNS`, `INCOME_SOURCE_RULES`, `EMPLOYMENT_UNLISTED`, `EVIDENCE_ACCEPTANCE`, `HISTORY_COMPLETENESS`, `ASSESSMENT_PERIODS`, `HOUSEHOLD_DEFINITION`, `PA_SCOPE_AND_HISTORY`, `RANKING_AND_TIES`, `COMPLETE_POOL_AND_CORRECTIONS`, `PRECISION_AND_CLASSIFICATION`, `POLICY_AUTHORITY_AND_EFFECTIVITY`.

| Required choice | Existing proposal / remaining specification | Supported implementation options (not adopted) |
|---|---|---|
| Document rules | Unspecified; explicit adoption required | dataset_v1: Full-Time Worker=1; Part-Time Worker=2; Seasonal Worker=3; Unemployed=4. Dataset Min-Max: HI/PA=(max-x)/(max-min); SI/ES/HM=(x-min)/(max-min). Sum exact weight times normalized value, then multiply by 100. |
| Accepted numerical domains | Unspecified; explicit adoption required | reviewed_values: HI: finite nonnegative reviewed monthly amounts; SI: supported levels 1-4; ES: one of the four disclosed categories; PA: nonnegative ledger count; HM: positive whole-person count. Invalid or unresolved values block calculation. |
| Income inclusions, exclusions, gross/net basis and ambiguous amounts | Unspecified: decide gross/net basis, wages, self-employment, irregular work, pensions, remittances, benefits, one-off transfers, in-kind income, exclusions, duplicate counting and zero/negative adjustments. | Explicit authorized text required |
| Number of complete calendar months for HI | 3 (proposal) | Explicit positive whole number |
| HI assessment period | Unspecified; explicit adoption required | before_close: Complete calendar months immediately before the approved application-closing month |
| SI assessment period | Unspecified; explicit adoption required | income_and_cutoff: HI assessment period plus current barriers at the bound evaluation cutoff |
| ES and HM observation date | Unspecified; explicit adoption required | cutoff: The immutable program assessment cutoff |
| Household definition and treatment of ambiguous living arrangements | Include the applicant and people who usually share the same dwelling and food or essential-expense budget. This is a household count, not a dependent count. | Explicit authorized text required |
| Unlisted or mixed employment | Unspecified; explicit adoption required | block: Unresolved; block usable scoring until evidence or a new authorized policy resolves the category |
| Previous-assistance scope | Unspecified; explicit adoption required | all_programs: Confirmed non-voided Association releases across programs; this_program: Confirmed non-voided releases from this program only |
| Previous-assistance window in calendar months | 12 (proposal) | Explicit positive whole number |
| Previous-assistance date boundaries | Unspecified; explicit adoption required | clamped_inclusive: Cutoff minus calendar months through cutoff, inclusive; clamp a missing day to month end |
| Release recording time and retrospective entries | Unspecified; explicit adoption required | recorded_by_cutoff: Count only qualifying releases recorded at or before the bound cutoff. Later entries are outside that cutoff snapshot; changed release history invalidates current use and requires renewed coverage review. |
| Release counting unit | Unspecified; explicit adoption required | existing_unique_release: Existing one successful release per application; exclude voids, applications, undelivered selections, referrals and attendance |
| Incomplete history and zero counts | Unspecified; explicit adoption required | verified_coverage: Require verified supporting evidence of complete coverage; unknown history is not zero |
| Evidence establishing complete PA coverage, justified zero, legacy imports and external assistance | Unspecified | Explicit authorized text required |
| Release units, installments, duplicate records and reconciliation with the one-release-per-application ledger | Unspecified | Explicit authorized text required |
| Accepted evidence | Unspecified; explicit adoption required | verified_documents: Current verified supporting documents of the selected types, including any authorized documented accessible alternative; notes alone are insufficient |
| Evidence acceptance, rejection, dispute resolution, unavailable evidence and authorized accessible alternatives | Unspecified | Explicit authorized text required |
| Authority and qualifications for evidence verification and numerical-input acceptance | Unspecified | Explicit authorized text required |
| Maximum supporting-review age at acceptance and use, in days | Unspecified | Explicit positive whole number |
| Missing, stale, disputed or invalid inputs | Unspecified; explicit adoption required | block: Block the complete-pool calculation; do not impute values or silently remove the applicant |
| Constant-value columns and single-person pools | Unspecified; explicit adoption required | block: Stop calculation with no score, imputation or weight redistribution |
| Internal ranking and precision | Unspecified; explicit adoption required | competition_exact: Descending exact rational scores; competition ranks 1,2,2,4; half-even two-decimal display only |
| Capacity-boundary ties | Unspecified; explicit adoption required | hold_boundary: Hold selection decisions at the capacity boundary; reasoned_human: Authorized human decision within slots, with a recorded tie explanation |
| Authorized tie procedure | Unspecified | Explicit authorized text required |
| Need classifications | Unspecified; explicit adoption required | none: Omit classifications; do not activate example bands |
| Evidence changes and corrections | Unspecified; explicit adoption required | reassess_recalculate: Invalidate current use, reassess accepted evidence, recalculate the complete pool and retain all prior runs |
| Late corrections and treatment of already selected, published or released cases | Unspecified | Explicit authorized text required |
| Complete eligible pool | Unspecified; explicit adoption required | closed_complete: After approved closing and cutoff, resolve every application; retain verified ineligible outcomes outside the scored pool |
| Policy approval authority and scope reference | Unspecified | Explicit authorized text required |
| Programs and circumstances to which this policy applies | Unspecified | Explicit authorized text required |
| Policy effective from, with timezone | Unspecified | Explicit timezone-aware date/time |
| Policy effective until, with timezone | Unspecified | Explicit timezone-aware date/time |
| HI: authorized supporting document types | Unspecified | Explicit authorized private document type IDs and retained descriptions |
| SI: authorized supporting document types | Unspecified | Explicit authorized private document type IDs and retained descriptions |
| ES: authorized supporting document types | Unspecified | Explicit authorized private document type IDs and retained descriptions |
| PA: authorized supporting document types | Unspecified | Explicit authorized private document type IDs and retained descriptions |
| HM: authorized supporting document types | Unspecified | Explicit authorized private document type IDs and retained descriptions |

Unsupported alternatives remain blocked and need a new scoped implementation. In particular, no unlisted employment mapping, constant-column score, automatic tie winner, external-history inference, classification threshold, missing-value imputation or automatic selection exists. The finite operational input and pool limits remain safety limits, not a permission to exclude applicants.

## Authorized Admin sequence after separately authorized installation

1. Open EWAF - Dataset policies. Select the exact compatible locked Vault version; specify each A/B/C choice and its authority. Save Draft.
2. Open Review Policy. Resolve every blocker and inspect the exact weight decimals, full SI rubric and each data-handling rule. An authorized Admin with `ewaf.authorize_operational` explicitly confirms A, B and C and clicks Approve policy version. A new immutable approval row retains actor, time, reason, digest and draft predecessor.
3. Open a new unpublished program without applications. Complete its existing terms and program approvals. Click Bind a new dataset scoring policy, select that exact approved version, enter the authorized assessment cutoff, and Bind exact approved policy. Existing schedules are retained.
4. Use the existing program publication action. Applications remain subject to the approved opening/closing times and existing verification controls.
5. After closing and cutoff, authorized evidence reviewers resolve all applications and accept each numerical input from verified evidence. Once scoring is separately enabled, Generate EWAF freezes the complete accepted pool and derives common bounds. Human selection, result publication and actual release remain separate audited actions.

This report does not authorize any of those operating actions. No working migration or feature-flag change was performed.
