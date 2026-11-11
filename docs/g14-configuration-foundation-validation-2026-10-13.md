# G14 AHP configuration foundation — independent review package

Date: 2026-10-13. Repository: `Rovic-bot/capstone`. Branch: `feature/events`.
Baseline HEAD: `334ad33f80e08a2a7e1cc7631bcb45aed96ca757`.
Owner-approved development baseline: **70%, unchanged**.

## Scope and authority

The initial branch, full HEAD and clean working tree matched the implementation request. Both complete G14 documents were readable and reviewed: `../00 - Project Overview/G14/G14_AHP_Configuration_Read_Only_Audit_2026-10-13.md` and `G14_Stage8_Implementation_Handoff_2026-10-13.md`. The governing system specification, development guide, open decisions, Stage 8/G12 validation and existing governance services informed the boundaries. Neither G14 document authorizes Association weights or production processing.

This increment implements preparatory drafts, mathematical evidence, officer findings and non-effective documentary evidence. It provides no active configuration pointer, effective authorization, applicant scoring, ranking, beneficiary selection or release integration. The existing operational services and G12 `PROCESSING_GATE_UNAVAILABLE` remain disabled. No G06-B2/B3 implementation, PDAO enforcement change, production access, staging, commit, push or deployment was performed.

## Complete changed/new file inventory

Modified existing files (4):

| File | Change |
| --- | --- |
| `ewaf/models.py` | Append four G14 models; retain existing historical and G12 model definitions. |
| `ewaf/urls.py` | Add separate private configuration routes; retain retired routes unchanged. |
| `core/templatetags/workspace_navigation.py` | Permission-gated configuration link and accurate availability notice. |
| `core/tests/test_workspace_navigation.py` | Verify restricted navigation visibility. |

New files (20):

| File | Purpose |
| --- | --- |
| `ewaf/ahp_validation.py` | Pure bounded, deterministic reference validator. |
| `ewaf/configuration_records.py` | Append-only artifact, digest and matching-audit contract. |
| `ewaf/configuration_services.py` | Permission-checked, locked, atomic recording services. |
| `ewaf/configuration_readiness.py` | Separate non-operational configuration diagnostics. |
| `ewaf/configuration_forms.py` | Blank judgment entry and explicit recording confirmations. |
| `ewaf/configuration_views.py` | Private list, diagnostics, recording and history screens. |
| `ewaf/configuration_testsupport.py` | Synthetic shared test helpers. |
| `ewaf/migrations/0003_configuration_foundation.py` | Additive schema only. |
| `ewaf/test_ahp_validation.py` | 16 pure mathematical/resource-limit tests. |
| `ewaf/test_configuration.py` | 23 workflow, permission, audit and preservation-barrier tests. |
| `ewaf/test_configuration_concurrency.py` | 4 real two-connection MySQL race tests. |
| `ewaf/test_configuration_migrations.py` | 2 database preservation tests. |
| `scripts/g14_browser_qa.py` | Synthetic live-server browser fixture. |
| `scripts/g14_browser_qa.cjs` | Chrome workflow and accessibility checks. |
| `templates/ewaf/configuration_list.html` | Private program list. |
| `templates/ewaf/configuration_detail.html` | Independent mathematical, review and governance indicators. |
| `templates/ewaf/configuration_form.html` | Accessible shared recording layout. |
| `templates/ewaf/configuration_history.html` | Draft, validation, review and documentary history. |
| `templates/ewaf/configuration_pages.html` | Independent history pagination links. |
| `docs/g14-configuration-foundation-validation-2026-10-13.md` | This validation and review report. |

The ignored review ZIP and packaging/check helpers under `.local/` are delivery artifacts, not additional application changes.

## Models and migration

All four models retain program ownership, a positive sequential revision, protected predecessor, schema version, server-recorded officer and retained label, timestamp, reason, server digest and a protected one-to-one matching `ProgramLog`.

- **ConfigurationRevision:** exact `SI, ES, PA, ND, PR` order; original judgments and server-canonical numeric input when parseable; method/profile; optional current G12 policy and digest; applicable terms revision/digest; source context containing program version, actual terms digest, approval-control version/binding and current policy identity. Missing policy/terms remain explicit pending context. A draft never increments `Program.version`.
- **ConfigurationValidation:** exact draft identity/digest; engine/profile; complete reproducible result, numerical settings and reference threshold. Every retained result is recomputed by the server during integrity validation.
- **ConfigurationReview:** exact draft and validation identities/digests; `REVIEWED` or `CORRECTIONS_REQUESTED`; explanation and correction requests. Corrections append history. Review completion is not approval.
- **ConfigurationAuthorizationEvidence:** exact draft/validation identities/digests, documentary reference, stated scope and explicit officer attestation. Records always remain non-effective; there is no authorization status or activation date.

Confirmed starting leaves were `ewaf/0002_verified_evidence` and `programs/0005_approved_terms`. New migration `ewaf/0003_configuration_foundation.py` depends on both and the swappable user model. It contains four `CreateModel` and ten `AddConstraint` operations, plus normal field/FK definitions. It has no data migration, historical backfill, default judgments, imported weights, effective configuration, group grants or prior migration edits. New model permissions are created by normal Django migration handling; none are assigned automatically.

## Mathematics and reproducibility

The historical `ewaf/calculation.py` remains unchanged. New engine `g14-ahp-1`, profile `workbook-five-reference-1`, uses normalized-column row averages, not an eigenvector solver. No applicant values enter this calculation.

For matrix A with n=5:

1. Column total `t[j] = sum(A[i,j])`.
2. Normalized matrix `N[i,j] = A[i,j] / t[j]`.
3. Weight `w[i] = sum(N[i,j]) / 5`.
4. `WSV[i] = sum(A[i,j] * w[j])`; `CV[i] = WSV[i] / w[i]`.
5. Estimated lambda is the mean of CV; `CI = (lambda - 5) / 4`; `CR = CI / 1.12`.

RI=1.12 and strict CR<0.10 are identified only as the historical/workbook reference check. Passing never establishes institutional approval. Negative CI/CR is retained as `NUMERICAL_ANOMALY`, never silently clamped into a pass.

Inputs are either ten independent upper-triangle judgments, with diagonal and reciprocal entries derived by the server, or a full 5×5 matrix. Exact criteria order, structure, positive finite numbers, unit diagonal, reciprocal products and positive derived weights are checked. Full-matrix entries are not silently repaired. Missing values remain incomplete; safe malformed/inconsistent drafts and failed validations can be retained for review. Oversized/non-JSON payloads are rejected before persistence.

The explicitly constructed Decimal context uses precision 50, `ROUND_HALF_EVEN`, Emin=-999, Emax=999 and explicit InvalidOperation/DivisionByZero/Overflow/Underflow traps. Ambient precision, rounding, exponents and traps cannot change the result. Diagnostic reciprocity tolerance is 1e-8 and weight-sum residual tolerance is 1e-45. Storage/parser limits are 8 KiB JSON, nesting depth 4, at most 25 collection entries, numeric text at most 96 characters, at most 40 significant digits and absolute raw/adjusted exponent at most 40. These are versioned engineering safeguards, not an Association comparison scale or production numerical policy. JSON floating-point judgments and booleans do not become accepted decimal judgments; users enter decimal strings or integers.

Canonical decimal text, expanded matrix, column totals, normalized matrix, weights, weight-sum residual, WSV, CV, lambda, CI and CR are retained. Comparisons use the working Decimal values without separate display rounding. Screens show the retained decimal text; there is no six-place rounding or precision loss in the verdict. “Unrounded” here means no additional presentation quantization; arithmetic still has its documented 50-digit working precision. Weight display explicitly follows the criterion array because MySQL JSON object key order is not a mathematical ordering guarantee.

Artifacts use domain-tagged server-generated digests over their canonical fields, including identities, context, officer, reason and time. Numerically equivalent judgment text produces identical canonical mathematical reports; separate recording events intentionally have different artifact digests. Future engine changes must preserve this engine/profile implementation for historical replay rather than silently redefine it.

## Independent diagnostics and policy blockers

The screen distinguishes draft recorded; mathematical completeness; structural validity; reference consistency; review pending/completed/corrections; documentary evidence missing/recorded non-effective; effective authorization unavailable; operational scoring unavailable. A newer validation makes earlier review/documentary findings stale. New drafts do not inherit favorable findings from older drafts. Integrity failure prevents a finding from becoming current.

Principal reason codes:

- Structure/math: `INVALID_STRUCTURE`, `CRITERION_ORDER_INVALID`, `INVALID_INPUT_MODE`, `JUDGMENT_MISSING`, `INVALID_NUMBER`, `NUMERIC_RESOURCE_LIMIT`, `PAYLOAD_RESOURCE_LIMIT`, `JUDGMENT_NOT_POSITIVE`, `DIAGONAL_NOT_ONE`, `RECIPROCITY_FAILED`, `WEIGHT_VALIDATION_FAILED`, `ARITHMETIC_FAILURE`, `CR_REFERENCE_FAILED`, `NUMERICAL_ANOMALY`.
- Provenance/review: `CONFIGURATION_MISSING`, `CONFIGURATION_CONTEXT_CHANGED`, `CONFIGURATION_STALE`, `ARTIFACT_INTEGRITY_FAILED`, `MATHEMATICAL_VALIDATION_MISSING`, `CONFIGURATION_REVIEW_STALE`, `EVIDENCE_POLICY_MISSING`, `EWAF_NOT_APPLICABLE`, `PROGRAM_TERMS_BINDING_UNRESOLVED`, `TERMS_CHANGED`.
- Pending policy: `SI_MEASUREMENT_POLICY_PENDING`, `ES_ENCODING_POLICY_PENDING`, `PA_SCOPE_POLICY_PENDING`, `ND_INTERPRETATION_POLICY_PENDING`, `PR_ENCODING_POLICY_PENDING`, `NORMALIZATION_POLICY_PENDING`, `CLASSIFICATION_POLICY_PENDING`, `AHP_JUDGMENTS_AUTHORIZATION_PENDING`, `TIES_EXCEPTIONS_POLICY_PENDING`, `CRITERION_POLICY_UNAPPROVED`.
- Unconditional barriers: `CONFIGURATION_AUTHORIZATION_UNAVAILABLE`, `OPERATIONAL_SCORING_UNAVAILABLE`, `PROCESSING_GATE_UNAVAILABLE`.

Diagnostics carry relevant context and source IDs. They are advisory reads, not a processing authorization token. The standalone G14 authorization guard always rejects consumption. Existing G12 readiness logic and the retired `save_configuration`, `save_input`, `generate_ranking`, `current_ranking` and `require_ranked` functions remain unchanged.

## Permissions, privacy, atomicity and concurrency

Active staff must have dashboard access plus `programs.view_program`, `programs.view_programtermsrevision`, `ewaf.view_evidencepolicyrevision` and view permissions for all four new models. Each recording service additionally requires its distinct permission:

- `ewaf.record_configurationrevision`
- `ewaf.record_configurationvalidation`
- `ewaf.record_configurationreview`
- `ewaf.record_configurationauthorizationevidence`

The same checks protect URLs and service calls. Staff/group membership alone grants nothing; no new permission assignment occurs. Existing superuser semantics are retained. Separation of actual authorizing officers is not invented: no effective authorization workflow exists in this increment.

POSTs require CSRF, explicit confirmation and a reason. The server controls actor, timestamp, audit, digests, reciprocal values and calculations. Client IDs are checked against program ownership and the exact latest draft/validation; expected-context digests detect replay. Private responses use no-store caching. GETs never create mutexes, snapshots, audits or configuration records. The views use existing Admin layout and shared accessible form rendering. No member-facing routes or private applicant document contents were added.

Every write uses the existing transactional lock order **terms mutex → Program → relevant configuration/validation rows**, then context/identity/integrity validation and atomic audit/artifact insertion. G14 does not take Member/Application locks because it never reads or changes applicant evidence values. Policy or terms changes either reject the competing stale capture or make the already captured draft diagnostically stale. New reviews using the same context serialize with only one accepted write. Shared G12 release/void serialization is unchanged.

Supported instance/queryset update, delete and bulk replacement paths are blocked. Protected FKs retain parents, audits and predecessor history. Database uniqueness enforces revision scopes. Audit association verification checks program, absent application association, officer, retained label, action, neutral note and exact artifact/digest changes. General program audits contain neutral recording metadata, not private judgments or explanations. Raw SQL/database administrators are outside the supported-path immutability guarantee; no database-wide audit redesign is claimed.

## Executed validation

All database-backed commands used the unchanged `scripts/g12_test_runner.py`. It creates a new native MySQL 8.4.11 instance and temporary data directory for each command, verifies its actual data directory/port and initial empty state, binds loopback only and uses isolated grants for two disposable database names. The child environment is allowlisted, inherited database variables are excluded, `.env` loading is disabled and PDAO enforcement is explicitly off. Only synthetic fixtures were used. Each runner shut its instance down after its command.

| Final validation | Actual result |
| --- | --- |
| Focused G14 + navigation suite | **61 passed**, 14.362 seconds: 45 G14 tests (16 mathematics, 23 workflow/security, 4 concurrency, 2 preservation/migration) plus 16 workspace-navigation tests. |
| Complete Django regression suite | **638 passed**, 151.358 seconds, no skips reported. Includes the existing G12/business regressions and new G14 tests. |
| Disposable migration preservation | **2 passed**, included in both focused and full results; not counted again as a separate execution. Fresh test databases also applied all migrations, including EWAF 0003. |
| Chrome browser QA | **1 passed**, 11.534 seconds: 7 private pages × 4 viewport widths (320, 390, 768, 1440), actual draft/validate/review/documentary POSTs, blank initial judgments, explicit criterion display order, visible-label associations, keyboard confirmation, no page overflow, no client JavaScript errors and no-store responses. |
| Django `check --database default` | **0 issues**, 0 silenced. Final focused/full/browser commands also reported 0 system-check issues. |
| `makemigrations --check --dry-run` | **No changes detected**. |
| Static/whitespace/repository checks | **Passed**: tracked `git diff --check`, no-index whitespace checks for all 20 new files, 17 Python AST parses, Node syntax, 24-file allowlist, existing model-source prefix preservation, exact branch/HEAD and empty staging index. |

Reproduction commands, each prefixed with `.venv\\Scripts\\python.exe scripts/g12_test_runner.py`:

```text
test ewaf.test_ahp_validation ewaf.test_configuration ewaf.test_configuration_concurrency ewaf.test_configuration_migrations core.tests.test_workspace_navigation --noinput --verbosity 1
test --noinput --verbosity 1
test scripts.g14_browser_qa --noinput --verbosity 1
check --database default
makemigrations --check --dry-run
```

Final retained runner directories under the Windows temporary directory: focused `santolan-g12-tests-5fup2ocs`; full `santolan-g12-tests-72dssyxj`; browser `santolan-g12-tests-kjmifu54`; checks `santolan-g12-tests-q1g6887c`; drift `santolan-g12-tests-ftpywbdl`. The review ZIP includes only their Django logs and the synthetic browser screenshot, not database directories or connection configuration.

An earlier full run also passed 638 tests. Visual inspection of the first browser screenshot then found JSON object keys displayed alphabetically. The screen was corrected to use the explicit criterion sequence, a regression assertion was added, and the final focused, full and browser runs above passed. The corrected mobile screenshot was visually inspected.

Limitations: browser QA is focused Chrome/keyboard/responsive checking, not a complete WCAG audit or assistive-technology certification. Real Association judgments/documents and production data were deliberately not tested. Supported-path immutability is not protection against privileged SQL. No deployment or production migration was performed. The test counts above describe individual suites; overlapping focused/full cases must not be added as unique coverage.

## Preservation and remaining decisions

The synthetic preservation fixture contains historical Configuration, ApplicationInput, RankingRun and Snapshot rows, G12 policy/assessment/readiness records, terms/approval bindings, assistance release/void/replacement history and published results. It compares all rows in EWAF, programs, membership, members, documents, assistance, announcements and events before/after the four G14 writes (excluding the new G14 artifacts and their mandatory logs), and before/after isolated rollback to EWAF 0002 followed by migration to all current leaves. No inferred verification or effective authority is created. A completed G14 documentary workflow still fails retired EWAF operations, human EWAF selection integration and release integration.

The following remain unapproved: SI measurement/source/period; ES categories and encoding; PA counting scope/cutoff; ND definition/interpretation; PR rubric/encoding; evidence freshness/corrections/disputes; normalization methods/directions/bounds; classification thresholds; actual AHP judgments and comparison scale; approved institutional CR/precision/display policy; who may authorize and required separation; effective/withdrawal dates; ties/exceptions; future suspension, reassessment and resumption rules. No default resolves these questions.

G15–G18 operational work remains blocked on independently approved scoring/evidence policies and effective authorization/processing governance, including the future G06-B2/B3 contract. The current foundation is not evidence that those milestones or the 80% EWAF milestone have been achieved.

## Review decision and package

**GO for independent source review only. NO-GO for operational authorization, scoring, ranking or beneficiary processing.** The approved development baseline remains **70%**.

Delivery: `.local/g14-final-review-2026-10-13.zip`. It preserves all 24 changed/new repository-relative paths and includes actual validation logs, corrected synthetic mobile screenshot, a tracked-change diff and a SHA-256 file manifest with the baseline commit. The archive excludes credentials, `.env`, uploads, MySQL data directories and production data. Its entries and bytes are checked after creation. No staging, commit, push or deployment accompanies delivery. Stop here for independent review.
