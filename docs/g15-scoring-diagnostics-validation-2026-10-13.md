# G15 diagnostic foundation — independent source review

Report filename date: 2026-10-13. Validation completed locally on 2026-10-14 (Asia/Manila).
Repository: `Rovic-bot/capstone`; branch: `feature/events`.
Starting HEAD: `7f250e5268ea3a402d96ee1db089992d06ea6032`.
Owner-approved development baseline: **70%, unchanged**.

## 1. Authority and scope

Preflight confirmed the exact branch/HEAD and a clean working tree and index. The complete supplied `../00 - Project Overview/G15/G15_EWAF_Calculation_Technical_Audit_2026-10-13.md` was read. Its SHA-256 is `6868b0d942360516cb82acd803f54e485b0d8069ed891b2ac9a94c55e1f456cf`. The current system specification, development guide, Open Decisions, membership amendment, implementation-impact notes, G12/G14 source, migrations, tests and validation reports informed the implementation. The audit and engineering profiles do not approve Association policies.

Implemented: pure synthetic Min–Max/WSM diagnostics, immutable program-scoped policy proposals, current applicant evidence-readiness adapters, immutable diagnostic captures and five criterion provenance traces, private staff screens, mandatory audits and regression evidence.

Applicant-linked database artifacts are deliberately **READINESS_ONLY**. Their schema has no numeric score, encoded value, normalized value, weight or contribution fields. Synthetic numerical fixtures run through the pure engine in tests/development; their full JSON traces are retained in the review package, outside applicant tables. There is no synthetic calculator web endpoint, arbitrary applicant-input calculator, live cohort selector or promotion path. This implements the audit's smallest safe increment and its requirement to keep synthetic examples separate from applicant records.

No operational scoring, ranking, classification, activation, effective authorization, beneficiary decision, release integration, G06-B2/B3 or PDAO enforcement was added. No production data, credentials, private uploads or existing application database was accessed. Nothing was staged, committed, pushed or deployed.

## 2. Complete changed/new source inventory

Four modified files:

| File | Change |
| --- | --- |
| `ewaf/models.py` | Append four G15 models; existing definitions remain unchanged. |
| `ewaf/urls.py` | Add four separate private diagnostic routes. |
| `core/templatetags/workspace_navigation.py` | Explicitly permission-gated diagnostic link. |
| `core/tests/test_workspace_navigation.py` | Verify G15 navigation visibility and access. |

Twenty-five new files:

| File | Purpose |
| --- | --- |
| `ewaf/normalization.py` | Versioned Decimal context, separate input/output parsers and Min–Max diagnostics. |
| `ewaf/weighted_scoring.py` | G14 mathematical replay and pure synthetic WSM traces. |
| `ewaf/scoring_policy.py` | Bounded canonical proposals, pending definitions and governance barriers. |
| `ewaf/scoring_inputs.py` | Permission-checked current G12/G14 provenance adapters; score-free applicant schema. |
| `ewaf/scoring_records.py` | Domain-specific immutable artifact and matching-audit contract. |
| `ewaf/scoring_services.py` | Atomic locked policy/capture services and complete graph validation. |
| `ewaf/scoring_readiness.py` | Unconditional operational-consumption rejection. |
| `ewaf/scoring_forms.py` | Blank policy proposal and explicit reason/confirmation forms. |
| `ewaf/scoring_views.py` | Private program proposals, current readiness and history. |
| `ewaf/scoring_testsupport.py` | Synthetic pending-policy and capture fixtures. |
| `ewaf/migrations/0004_scoring_diagnostics.py` | Additive G15 schema and permissions only. |
| `ewaf/test_normalization.py` | 12 normalization, resource and reproducibility tests. |
| `ewaf/test_weighted_scoring.py` | 12 WSM, replay, residual and payload tests. |
| `ewaf/test_scoring_inputs.py` | 10 provenance, freshness and B1/B2/B3 tests. |
| `ewaf/test_scoring_services.py` | 18 service, permission, audit, immutability and interface tests. |
| `ewaf/test_scoring_concurrency.py` | 6 real two-connection MySQL race tests. |
| `ewaf/test_scoring_migrations.py` | 2 migration/business-row preservation tests. |
| `scripts/g15_browser_qa.py` | Isolated synthetic live-server fixture. |
| `scripts/g15_browser_qa.cjs` | Headless Chrome workflow/layout/accessibility checks. |
| `templates/ewaf/scoring_list.html` | Private program diagnostic entry. |
| `templates/ewaf/scoring_policy.html` | Pending proposal entry/history and restricted applicant links. |
| `templates/ewaf/scoring_diagnostics.html` | Separate evidence, mathematical and governance findings. |
| `templates/ewaf/scoring_history.html` | Captures with integrity and current-context indicators. |
| `templates/ewaf/scoring_pages.html` | History/list pagination. |
| `docs/g15-scoring-diagnostics-validation-2026-10-13.md` | This validation report. |

Total: **29 proposed repository files**. Ignored `.local/` packaging helpers and the review ZIP are delivery artifacts, not application changes.

## 3. Models and additive migration

All four models use a G15-specific digest domain, schema version, protected program/actor/audit references, retained actor label, server timestamp, reason, positive revision and protected predecessor. Audit identities, timestamps and digests are server generated.

- **ScoringPolicyRevision:** exact SI, ES, PA, ND, PR order; canonical proposal; engine/profile; optional exact G12 evidence-policy, G14 configuration/validation and terms identities/digests; full configuration context. Program-scoped sequential revisions; no active pointer, approval flag or effective date. Empty criterion definitions are explicitly pending. Missing configuration/evidence context can be represented without inventing defaults.
- **CalculationDiagnosticRun:** program sequence/predecessor; exact policy/configuration/validation digests; READINESS_ONLY mode; engine/profile; evaluation local date/timezone and UTC timestamp in the result; current-source/context digests; result and item manifest. A database CHECK restricts mode to READINESS_ONLY.
- **CalculationDiagnosticItem:** one application per bounded capture, protected application/run, server-derived item key, score-free result and five-trace manifest. No user-entered item identity or numerical aggregate.
- **CalculationCriterionTrace:** exact criterion, optional protected latest assessment, assessment/source/evidence-policy digests, retained type/unit and current-evidence finding. No copied income, employment text, document contents, addresses, birthdates or ID images.

Ordinary MySQL unique constraints cover `(program, revision)` on proposals/runs, `(run, item_key)` and `(item, criterion)`. Model checks enforce same-program/application ownership, exact artifact relations and audit associations. Complete graph validation requires exactly one item and exactly the five ordered criterion identities, recomputes manifests and checks every audit. Child rows use revision 1; subsequent captures append a new complete run graph. An old capture is historical evidence, never a current-source acceptance token.

Confirmed dependency leaves: `ewaf/0003_configuration_foundation`, `programs/0005_approved_terms`, and the swappable user model. New `0004_scoring_diagnostics.py` uses CreateModel, AddField and AddConstraint operations. No data migration, historical backfill, default configuration, imported weights, inferred verification/approval or automatic permission assignment occurs. Earlier migrations are unchanged. `Program.version` is not incremented by G15 recording.

## 4. Mathematical method and reproducibility

Historical `ewaf/calculation.py` and G14 `ahp_validation.py` remain unchanged. New engine `g15-minmax-wsm-1`, profile `synthetic-fixed-bounds-1`, executes only in exact SI, ES, PA, ND, PR order.

For explicit finite synthetic input x and L < U:

    benefit = (x - L) / (U - L)
    inverse = (U - x) / (U - L)
    contribution[k] = weight[k] * normalized[k]
    score_0_1 = sum(contribution[k], in criterion order)
    score_0_100 = 100 * score_0_1

Explicit context: precision 50, ROUND_HALF_EVEN, Emin=-999, Emax=999, traps for InvalidOperation, DivisionByZero, Overflow and Underflow. Parsing/arithmetic/aggregation/scale conversion cannot inherit ambient Decimal settings. Canonical output uses decimal text without extra quantization. Significant trailing zeros are removed textually rather than with ambient-context normalize(). “Full precision” refers to this finite 50-digit profile, not infinite precision.

Judgment/value input parser: strings/integers only; 40 significant digits, 120 characters, absolute raw/adjusted exponent at most 40; oversized integers rejected before decimal conversion. Separate calculated-output parser: 50 significant digits, 1,100 characters and absolute raw/adjusted exponent at most 999. This accommodates expanded full-precision G14 output without relaxing its judgment parser or truncating coefficients. Near-equal/cancellation-sensitive subtraction is compared with a bounded 200-digit subtraction; lost information yields NUMERIC_PRECISION_INSUFFICIENT. No business tolerance equates distinct bounds.

Synthetic fixture structure is bounded to 32 KiB, nesting depth 6, 30 collection entries, bounded keys/strings/integers. Proposals are bounded to 24 KiB, depth 5 and 30 collection entries. These are engineering limits, not socioeconomic bounds.

G14 judgments are replayed server-side and the entire stored validation must exactly match, including method, engine/profile, criterion order, settings, matrix and calculations. Reference consistency must pass. Artifact adapters additionally validate exact current program/configuration/policy/validation ownership, digests, audits and configuration context. RI=1.12 and CR<0.10 remain workbook reference diagnostics; neither approves the weights.

Missing values remain missing; zero is accepted as zero. Equal/reversed/out-of-range bounds, absent direction, unknown categories, unit/source mismatch, malformed/nonfinite/boolean/float inputs and resource/precision failures return structured diagnostics. No clamping, imputation, silent category inference, coefficient substitution, incomplete-vector renormalization or classification occurs. Proposed cohort rules can be recorded but yield BOUNDS_PENDING; live or synthetic cohort-extrema calculation is not part of this fixed-bound increment.

All contributions, canonical inputs/bounds/directions, weights, residual and both scales remain in synthetic result traces. Sum residual tolerance is 1e-45, matching the G14 diagnostic profile. An endpoint excess visible at working precision is retained with SCORE_RANGE_ANOMALY and incomplete status, not clamped. Missing/invalid criteria withhold the aggregate entirely.

Executed independent equal-weight fixture: normalized values 0.2, 0.4, 0.6, 0.8, 1 and weights 0.2 each produce contributions 0.04, 0.08, 0.12, 0.16, 0.2; total **0.6 / 60**.

The retained synthetic full-precision fixture changes only the synthetic SI:ES judgment to 2. Its replayed result is:

    score_0_1   = 0.59111111111111111111111111111111111111111111111112
    score_0_100 = 59.111111111111111111111111111111111111111111111112
    weight-sum residual = 0

`review/validation/g15-synthetic-trace.json` in the ZIP retains full fixture inputs, all five contributions, exact synthetic configuration/validation/policy IDs and digests, G14 validation, numerical settings and false authorization flags. It contains no applicant reference and is not an Association policy seed.

## 5. Current evidence and fail-closed boundaries

Applicant services rebuild G12 source context and invoke current `g12-v2` readiness under explicit permissions. They inspect current ownership, membership/manual verification, submission validity, applicable disability requirements, manual photo review, required documents/checklists, eligibility audit, member/program versions, current terms/binding/control state, latest policy and latest criterion records. They never use legacy ApplicationInput or a retained readiness snapshot as source authority.

Latest assessment identity controls even if DECLARED, NEEDS_REVIEW, REJECTED, disputed, expired or stale. Older favorable records never become current. G12 B1 criterion/source-specific supporting mappings, B2 program-specific rubric findings and attestation, and B3 exact reusable-document type relationships are reevaluated. New supporting review/revocation, member changes, source hashes, terms, policy, G14 validation/review history and PA release/void state invalidate the relevant context.

G15 compares proposal source/type/unit with the reviewed assessment and checks exact category membership without encoding or normalizing applicant values. The result separates eligibility readiness, criterion completeness, current G14 mathematical evidence, unavailable applicant mathematics and unavailable institutional/operational authorization. Even all five verified current findings produce no applicant score.

Expiry follows G12's inclusive expiry date (`expires_on < localdate()` is expired). Tokens retain evaluation date/timezone as well as source and latest-assessment identities/digests. The recording service reevaluates source/reasons after graph creation, before commit, catching expiry/date changes or source changes during capture. Application submission snapshots remain unchanged.

Principal numerical/proposal reasons: VALUE_MISSING, BOUNDS_PENDING, NORMALIZATION_DIRECTION_PENDING, ZERO_RANGE, BOUNDS_ORDER_INVALID, VALUE_OUT_OF_BOUNDS, ENCODING_UNAVAILABLE, MEASURE_OR_UNIT_MISMATCH, INVALID_NUMBER, INVALID_STRUCTURE, CRITERION_ORDER_INVALID, NUMERIC_RESOURCE_LIMIT, PAYLOAD_RESOURCE_LIMIT, NUMERIC_PRECISION_INSUFFICIENT, ARITHMETIC_FAILURE, WEIGHT_SOURCE_INVALID, WEIGHT_VECTOR_INVALID and SCORE_RANGE_ANOMALY.

Current-source reasons retain G12 codes and source IDs, including CRITERION_MISSING, CRITERION_REJECTED/NOT_VERIFIED, EVIDENCE_DISPUTED/EXPIRED, SOURCE_CHANGED, CRITERION_POLICY_CHANGED, ARTIFACT_INTEGRITY_FAILED and B1/B2/B3 findings. G15 adds SCORING_POLICY_MISSING/INCOMPLETE/STALE and stale-write rejection SCORING_CONTEXT_CHANGED.

Every applicant diagnostic includes **CRITERION_POLICY_UNAPPROVED**, **CONFIGURATION_AUTHORIZATION_UNAVAILABLE**, **OPERATIONAL_SCORING_UNAVAILABLE**, **PROCESSING_GATE_UNAVAILABLE**. `require_operational_scoring()` rejects unconditionally. Existing retired EWAF mutation/ranking functions and assistance-selection/release barriers are unchanged. A staff checkbox, latest proposal, documentary reference or PDAO approval cannot authorize use.

## 6. Permissions, privacy, audits and concurrency

All entry points require active authenticated staff and `accounts.access_dashboard`. Proposal viewing additionally requires the established G14 view set and `ewaf.view_scoringpolicyrevision`. Recording requires `ewaf.record_scoringpolicyrevision`. Applicant readiness additionally requires the complete G12 private view set and views of all three diagnostic models; retention requires `ewaf.record_calculationdiagnosticrun`. These checks are enforced in services as well as views. No staff/group grants are installed.

All four GET routes are read-only, no-store and permission-restricted. They do not create terms mutexes, approval-control rows, snapshots or audit records. POSTs require CSRF, reason, explicit confirmation and server-validated context. No score/weight/rank/file input or approve/activate/select action is exposed. Policy-only readers do not receive applicant links without the additional private permissions.

Program-only recording locks Terms mutex → Program. Applicant capture locks Terms mutex → Program → Application → Member → latest assessment rows. Relevant histories are serialized by these existing locks and checked again by identity/digest. Captures intentionally cover one application, avoiding an unsupported multi-application lock scheme. Cross-program release/void writers share the Member lock; no unrelated program lock is acquired after Member. Existing release/void transactions are untouched.

Concurrent proposals with the same stale token permit one commit. Concurrent readiness captures of the same unchanged evidence may both append, with distinct sequential revisions and complete independent graphs; neither becomes an active score. A competing evidence/configuration mutation either rejects the old token or makes an earlier capture outdated. Held-writer tests confirm a new release or void blocks a competing capture until commit, then rejects its stale token.

Every artifact has an exact matching neutral ProgramLog action/program/application/actor/label/digest association. General audit notes contain no socioeconomic values or copied documents. Parent, item, five traces and all audits commit atomically; injected record/audit failures roll back completely. Instance saves/deletes, primary-key overwrite, queryset update/delete and bulk replacement are blocked on supported paths. PROTECT references preserve dependencies. This is not a claim of protection against privileged SQL or out-of-band storage changes; G12's verification-time file-hash limitation remains.

## 7. Actual validation results

Every Django command used the unchanged `scripts/g12_test_runner.py`. It initialized a new native MySQL datadir, checked its loopback port/datadir and empty schema, created isolated synthetic grants, filtered inherited environment variables, disabled `.env` loading and kept PDAO enforcement off. No application datadir was opened. Temporary test databases were destroyed and each disposable server stopped by the runner.

| Executed validation | Actual result |
| --- | --- |
| G15 focused plus navigation | **77 passed**, 46.260 seconds: 60 G15 tests and 17 navigation tests. |
| Explicit G12/G14 regression | **138 passed**, 81.306 seconds. |
| Complete Django regression | **699 passed**, 283.715 seconds. |
| G15 migration/business-row preservation | **2 passed**, included in focused/full suites; not additional disjoint tests. |
| G12/G14 preservation | **4 passed**, included in the 138-test regression. |
| Browser/accessibility | **1 passed**, 9.258 seconds; four pages × four widths and two actual POST workflows. |
| Django checks | **0 issues**, `check --database default`. |
| Migration drift | **No changes detected**, `makemigrations --check --dry-run`. |
| Syntax, whitespace, source inventory and preservation | Final static evidence retained in ZIP. |

Focused command: `test ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_scoring_services ewaf.test_scoring_inputs ewaf.test_scoring_concurrency ewaf.test_scoring_migrations core.tests.test_workspace_navigation --noinput --verbosity 1`.

G12/G14 command: `test ewaf.test_evidence ewaf.test_readiness ewaf.test_evidence_corrections ewaf.test_evidence_concurrency ewaf.test_evidence_migrations ewaf.test_ahp_validation ewaf.test_configuration ewaf.test_configuration_concurrency ewaf.test_configuration_migrations --noinput --verbosity 1`.

Full command: `test --noinput --verbosity 1`. Browser: `test scripts.g15_browser_qa --noinput --verbosity 1`. All are arguments to `.venv/Scripts/python.exe scripts/g12_test_runner.py`, never unisolated manage.py invocations.

Final log directories below `C:/Users/rovic/AppData/Local/Temp/`: focused `santolan-g12-tests-bf0vpunu`; G12/G14 `santolan-g12-tests-xjrthyii`; full `santolan-g12-tests-3x6qc0_d`; browser `santolan-g12-tests-bl0ee92s`; checks `santolan-g12-tests-m3f387jj`; drift `santolan-g12-tests-mt03qqeo`. Only allowlisted synthetic logs/trace/screenshot are packaged; database/configuration/credential files are excluded.

Browser checks covered proposal creation and readiness retention, blank proposal input, history integrity, diagnostic labels, control labels, keyboard confirmation, no horizontal overflow at 320/390/768/1440px, no numeric score/rank/file controls, no-store responses and no JavaScript errors. The 390px screenshot was visually inspected. This is focused accessibility/layout QA, not screen-reader certification or Association UAT.

Validation iterations are not concealed: the first 48-test run passed. An expanded run found duplicate navigation-fixture usernames and a shared helper method-name collision in migration fixtures; both were corrected. A later residual test originally used a perturbation below the 50-digit aggregate's visible precision; the fixture was corrected to test a representable endpoint excess. Browser QA initially caught the JSON field's `null` presentation and mobile overflow of long reason codes; both were fixed and browser QA rerun successfully. Final counts above supersede those development runs.

## 8. Preservation evidence

Synthetic preservation fixtures include complete historical Configuration/ApplicationInput/RankingRun/Snapshot records, all G12 evidence/readiness artifacts, all four G14 artifact types, membership/document/manual-verification histories, original application references/statuses/versions/answers/snapshots, eligibility history, terms/approval bindings/control state, release/void/replacement history and published result revisions. Complete business rows compare equal before/after G15 recording and migration down/up, excluding only newly created G15 artifacts and their audit entries.

The new tables remain empty after schema migration; there is no inferred review or authority. Existing model definitions remain an unchanged prefix of `ewaf/models.py`; historical calculation/validator/migrations, G12/G14 services, program governance and assistance release/void sources remain unchanged. The complete regression includes retired-operation and approval-binding preservation tests.

## 9. Pending decisions and remaining stages

No Association choices were supplied for SI measure/source/unit/period or government-program status; ES category definitions/encodings; PA scope/cutoff/type/external history; ND dependent definition/verification/interpretation; PR rubric aggregation/numerical encoding; any normalization direction/bounds; missing/equal-range/out-of-range policy; evidence expiry/disputes/corrections; actual AHP judgments/authority; institutional precision/display/endpoint rules; classification thresholds; cohort admission/cutoff; ties/exceptions; effective authorization/withdrawal; locking/reassessment/resumption or alternative evidence.

G16 requires an authorized cohort and operational configuration/processing contract. G17 requires governed affected-pool recalculation and promotion. G18 requires current authorized rankings and independent eligibility/processing checks before human decisions. G06-B2/B3 remains an external blocking dependency; this increment does not implement it. Cohort-derived calculation, real applicant previews, classification, ranking, beneficiary actions, deployment and PDAO cutover remain out of scope.

## 10. Review package and recommendation

Review ZIP: `.local/g15-final-review-2026-10-13.zip`. It preserves all 29 source paths and includes a manifest, SHA-256 checksums, tracked diff, final and development validation logs, synthetic numerical trace and inspected screenshot. It is a changed-source package; the expected baseline repository and installed dependencies are needed to rerun tests. No `.env`, secret, private upload, real PWD record, database/configuration file or production export is included.

**GO for independent source review only. NO-GO for operational EWAF scoring, ranking, classification, beneficiary processing, effective authorization, production deployment or PDAO enforcement.**

Development baseline remains **70%**. Stop after validation and packaging; await independent review before any staging.
