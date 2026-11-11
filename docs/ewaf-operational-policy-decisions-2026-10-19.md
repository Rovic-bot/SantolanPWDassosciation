# Consolidated EWAF policy decision sheet

Accepted milestone: **70%**. Operational scoring: **disabled**. Proposed 80%: **not accepted**.

This is the single outstanding-policy sheet for the October 19 operational-readiness sprint. It consolidates the earlier Stage 8 sheets; it does not approve their illustrative values. The owner approved creation and disposable testing of `ewaf/0007_development_human_decisions.py` in this conversation. That resolves the former development-persistence authorization blocker only. Application-database migration, real-member processing and operational activation remain unauthorized.

The recorded PR-removal amendment applies to specifically authorized programs. Its actual approval date and program list remain unknown. PR remains mandatory program-specific eligibility. Neither the date on this report nor the migration generation timestamp is an Association approval/effective date.

| Decision needed from the Association | Required recorded decision | Safe behavior until resolved |
|---|---|---|
| Four-criterion configuration | Exact SI/ES/PA/ND judgments, derived weights/method, configuration authority and applicable program IDs | Six-comparison AHP replay and retained fictional revisions only; no operational activation |
| SI | Income/indicator definition, individual or household basis, period, units, evidence, direction and acceptable assessment | Explicit fixture values; unavailable/unverified inputs block the whole affected pool |
| ES | Approved categories, meanings, encoding/order, observation date, evidence and direction | Explicit fictional encoding; unmapped values block |
| PA | Count/value basis, included assistance, cross-program scope, lookback start/end and direction | Test profile uses only successful nonvoided actual release counts across all retained programs, with no lookback. Other window labels are rejected. Applications, selection and attendance do not become assistance |
| ND | Definition of dependent, household scope, observation period, evidence and direction | Verified fictional count only |
| Normalization and exceptional input | Fixed/cohort bounds, equal-bound handling, missing/disputed/expired/out-of-range handling, precision | Explicit fictional fixed bounds; no imputation, clipping or invented favorable value; fail closed |
| PR eligibility and assessment | Program-specific functional-need qualification, evidence rubric, consent/privacy for any approved assessment, accessible alternatives, reassessment/appeal and disputed/incomplete outcomes | Three distinct fictional rubric findings are required before calculation. Disability classification alone is insufficient. No home-visit policy or extra eligibility rule is activated |
| Pool scope and revisions | Cutoff, unresolved cases, rule changes after opening, source corrections, reevaluation/approval timing and how affected applicants receive the same version | Explicit fictional cutoff retains the entire inventory. An unresolved in-scope applicant blocks. Supported source changes invalidate the current result; explicit replacement recalculates the whole accepted pool |
| Classification | Whether to use need labels, thresholds, gap-free exact endpoints, precision/display and permitted disclosure | Classification remains unset; no workbook sample threshold becomes policy |
| Ties and beneficiary selection | Exact-tie procedure, slot allocation, nonselection/waitlist outcomes, exceptions and authorized review duties | Descending numerical comparison with equal counts only. No business ranks/tie-break priority. Saved SELECT_DEMO / DEFER_REVIEW / WITHDRAW_DEMO are fictional human review records, not allocations or real beneficiary approvals |
| Authority and dates | Actual amendment approval date, effective date, approving role, documentary authority, program scope and supersession | All remain unfilled. A passing consistency ratio does not approve policy |
| Operational permissions | Approved officer permission assignments and program scope; separation of configuration, evidence, decisions and publication duties | Existing least-privilege service checks; disposable calculation requests remain scoped to their recorded actor. No production role matrix is seeded |
| Publication/clarification | Approved result projection, small-group handling, clarification/appeal and retention | Existing approved non-EWAF masks remain unchanged. No private scores, evidence or new EWAF result publication |
| Application migration and activation | Separate reviewed application-database migration, operational authorization and deployment instructions, after policy and acceptance | No application DB read/migration, deployment or activation in this sprint. New routes require the registered disposable capability |

For each row, retain the Association's exact answer, authorized program/configuration scope, authority/evidence reference, approver, actual approval date, effective date and superseded version. Blank or disputed answers remain pending. Do not populate them with test fixture values.

Related governing questions remain OQ-02/24 (accessible identity evidence), OQ-23 (criterion evidence), OQ-25 (classification), OQ-22 (disclosure) and the bounds/ties/authority questions in `../00 - Project Overview/Open Decisions.md`. Association membership completeness and manual PRPWD remain distinct from PDAO guidance; nothing here changes those rules.

The four-criterion mathematics, historical five-criterion preservation and new fictional decision persistence can be reviewed now. Full operational Stage 8 acceptance cannot be represented as complete until the required decisions are resolved, implemented where they change behavior, validated, and accepted by the owner. No additional technical micro-gates are proposed.
