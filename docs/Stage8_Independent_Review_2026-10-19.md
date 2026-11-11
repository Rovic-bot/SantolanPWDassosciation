# Stage 8 Consolidated Independent Review — 19 October 2026

## Decision

**GO for closure of the consolidated, disposable-only technical development sprint.**
**NO-GO for declaring the full Stage 8 / 80% system milestone accepted under the previously described operational EWAF scope.** A *demonstration-only* 80% milestone would require an explicit narrower acceptance definition and owner/adviser approval. The existing accepted milestone therefore remains **70%**.

This decision does not authorize operational scoring, actual beneficiary ranking or selection, application/production database migration, deployment, or the promotion of the proposed four-criterion framework to an effective policy.

## Independently verified materials

- The uploaded ZIP opens with **110 entries** and has no CRC errors.
- **108/108** manifest payloads match SHA-256 and byte size; **109/109** `SHA256SUMS` records match.
- Both separately uploaded Markdown documents are byte-identical to the ZIP copies.
- **61/61** packaged Python files pass Python AST parsing.
- The supplied baseline-relative patch was reversed and **22/22** prior source hashes matched. Line-ending handling required a file-by-file patch mode; `programs/views.py` had one mixed-CRLF/LF context line that was restored byte-for-byte for the verification.
- Three packaged screenshots were opened and inspected; they show a fictional EWAF Admin laboratory and two-version historical calculation view in the existing minimalist portal.
- No complete working-tree, staged-index, runtime database, or deployed system was accessible to this reviewer; those preservation and isolation claims depend on the packaged reports and logs.

## Execution evidence examined, not rerun

The archived final logs report:

| Run | Logged result |
|---|---|
| EWAF tests | 804 passed, no final failures/errors/skips |
| Domain regressions | 463 passed, no final failures/errors/skips |
| Full project | 1,397 passed, no final failures/errors/skips |
| Browser | 1 passed, no final failures/errors/skips |
| Django checks | Zero issues |
| Migration drift | No changes detected |

Earlier unsuccessful runs and corrections are preserved. Test totals overlap. Django was not available in the independent container for rerunning the MySQL-backed test suite, so none of these are claimed as newly executed tests by the reviewer.

## Independent mathematical replay

Using the four-criterion matrix (SI, ES, PA, ND), normalized-column row-average AHP, 50-digit Decimal context, and RI=0.90, independent recalculation matched the reported full-precision weights, lambda, CI and CR exactly:

- SI: `0.47085905179088958208889183867613548372823610097122`
- ES: `0.28401252184686179509302891528948474591270104643702`
- PA: `0.17148293179354439061082719408862635782394194818699`
- ND: `0.073645494568704232207252051945753412535120904404772`
- λ: `4.0513654728589442612068089407860696967972113290515`
- CI: `0.017121824286314753735602980262023232265737109683833`
- CR: `0.01902424920701639303955886695780359140637456631537`

The illustrative fictional 0–10 benefit-scale inputs independently produced approximately `63.0417026172` for DEMO-A and `49.4037521294` for DEMO-B. These tests do not approve actual SI/ES/PA/ND measurements or weights.

## Supported technical findings

1. The consolidated code includes scoped generation-invalidation adapters across the documented source writer families, with an ordered Terms/Authority/Program/SourceState prefix, native-audit binding and fail-closed token checks. The archive includes integration/concurrency/rollback tests and test logs for these paths.
2. The generation-aware *five-criterion* development processing service contains request binding, complete-pool capture, result graph, promotion CAS, sticky expiry invalidation and immutable history inspections, and is expressly confined to a registered disposable session.
3. The *four-criterion* implementation is a separate AHP calculator and fixed fictional demonstration with `BLOCKED_POLICY`. It is **not** saved as an authorized four-criterion operational configuration, nor processed through the five-criterion historical engine as if it were the same algorithm.
4. The Admin screenshots and browser log support a private fictional demonstration, a guided six-comparison UI, readiness explanations, and historical results using the preserved eight-module layout. They do not prove WCAG compliance or real officer/PWD user acceptance.
5. The documented 128-retained-application ceiling fails explicitly instead of truncating silently; it is a nonproduction development limit, not proof of capacity for every future real assistance program.

## Blocking conditions for full Stage 8 / 80% acceptance

1. The Association must finalize/confirm the revised *four-criterion* effective configuration and exact, versioned program scope, approver and effective date.
2. Approve missing rule semantics: SI measure, employment and dependents evidence/measurement, PA scope/lookback, normalization directions/bounds, missing/disputed/equal-bound handling, classifications and ties.
3. Define program-specific **functional-need/relevance as pre-EWAF eligibility**, including evidence, informed consent for visits, accessible alternatives, reassessment/appeal and independent human decisions.
4. Implement and validate the final four-criterion policy as a real end-to-end authorized **development** workflow against a fully verified fictional application pool, preserving historical five-criterion runs and independent approval/selection/release boundaries. Any required new persistence/migration design needs separate approval.
5. Complete Admin decision UX and owner/adviser acceptance against a written Stage 8 checklist. Wider scale, security/accessibility/UAT and production/deployment remain separate Stage 9/10 work and must not be implied by these tests.

## Recommended immediate action

Close the consolidated disposable-only sprint as technically reviewed. Do **not** create further micro-gates for the already reviewed source integrations. Obtain the missing Association decision sheet and write one narrowly defined final Stage 8 acceptance specification: approved four-criterion algorithm, evidence criteria and normalized measures, applicability, human selection, and auditable outcomes. Then request a single focused implementation/acceptance pass. Continue to show **70% accepted** until the owner approves advancement; a narrower demonstration-only milestone needs explicit acceptance rather than an assumed policy change.
