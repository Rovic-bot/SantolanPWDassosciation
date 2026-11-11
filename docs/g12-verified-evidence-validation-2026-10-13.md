# G12 — Verified evidence and eligibility foundation

Implementation for independent owner review. The owner-defined development baseline remains **70%**. G12 does not establish completion of Stage 8 or authorize operational EWAF use.

## 1. Authority, preflight and scope

Read both supplied governance documents:

- `../00 - Project Overview/G12/G12_Verified_Evidence_Read_Only_Audit_2026-10-12.md`
- `../00 - Project Overview/G12/G12_Stage8_Governance_Handoff_2026-10-12.md`
- `../00 - Project Overview/G12/g12-final-independent-review-2026-10-13.md` (complete independent review, B1/B2/B3 corrections)

Correction preflight reconfirmed the expected branch/HEAD and the existing 27 changed/new files. All were preserved; an ignored local source backup was taken before editing. The correction adds two files, for 29 proposed files total (5 modified tracked files and 24 new files). No additional Association policy approval was inferred from the review.

The consolidated system specification, development guide, Open Decisions, membership/PDAO amendment, implementation impact and G06-B1B.1 validation were also consulted. Both G12 documents were readable. Preflight confirmed branch `feature/events`, HEAD `bc73a954200731d8608ffc59c2516af7613fed9a`, and an initially clean working tree. Subsequent changes are the bounded G12 work listed below.

Existing membership, document review, photo/application, eligibility, release/void, terms/binding and audit paths were inspected. New evidence operations do not call eligibility invalidation, decision, release, publication refresh or ranking operations.

## 2. Complete implemented file inventory

| File | Change |
| --- | --- |
| `core/templatetags/workspace_navigation.py` | Permission-controlled Applications & Verification entry and correct active group |
| `core/tests/test_workspace_navigation.py` | Explicit evidence permission/navigation regression |
| `ewaf/models.py` | Three additive evidence artifacts; historical models retained |
| `ewaf/services.py` | Expose isolated evidence operations; retired entry points still raise |
| `ewaf/urls.py` | Private evidence, policy, readiness, review and history routes |
| `ewaf/evidence_records.py` | Supported-path append-only guards, canonical artifact digest and matching audit validation |
| `ewaf/evidence.py` | Policy schema, allowlisted sources, finite typed values, minimal source manifests and digests |
| `ewaf/evidence_rules.py` | Criterion-specific evidence mappings, structured relevance findings and exact reusable-type validation |
| `ewaf/evidence_services.py` | Transactional policy/finding/snapshot recording with permissions and stale-source checks |
| `ewaf/readiness.py` | Independent eligibility, criterion, governance and processing diagnostics |
| `ewaf/evidence_forms.py` | Labeled forms, explicit confirmation, review reasons and expected-source fields |
| `ewaf/evidence_views.py` | Private no-cache views, pagination and controlled POST operations |
| `ewaf/migrations/0002_verified_evidence.py` | Additive schema, constraints and permissions only |
| `ewaf/evidence_testsupport.py` | Synthetic evidence and authority fixtures; never production seeds |
| `ewaf/test_evidence.py` | Recording, privacy, access, immutability, audit, value and rollback tests |
| `ewaf/test_evidence_corrections.py` | 26 B1/B2/B3 regression tests using distinct synthetic criterion evidence |
| `ewaf/test_readiness.py` | Freshness, expiry, completeness, provenance and independent gates |
| `ewaf/test_evidence_concurrency.py` | Nine actual MySQL transaction/race scenarios |
| `ewaf/test_evidence_migrations.py` | Complete business-row and historical-migration preservation |
| `scripts/g12_test_runner.py` | Fresh local MySQL isolation, environment filtering, instance verification and shutdown |
| `scripts/g12_browser_qa.py` | Synthetic live-server browser fixture |
| `scripts/g12_browser_qa.cjs` | Six-page layout, labels, keyboard, blocked incomplete PR verification and actual review/snapshot flows |
| `templates/ewaf/evidence_queue.html` | Private paginated application chooser |
| `templates/ewaf/evidence_form.html` | Shared labeled form and error presentation |
| `templates/ewaf/evidence_policy.html` | Record definitions for review and inspect retained policy history |
| `templates/ewaf/evidence_review.html` | Declaration/finding entry, source information and supporting review IDs |
| `templates/ewaf/readiness.html` | Four independent readiness results, reason codes and snapshot action |
| `templates/ewaf/evidence_history.html` | Retained assessment and diagnostic history |
| `docs/g12-verified-evidence-validation-2026-10-13.md` | This implementation and validation report |

## 3. Models and migration

`EvidencePolicyRevision` retains sequential program revisions, schema version, canonical definitions, digest, authority reference, applicable terms revision/digest, recording officer/retained label/time/reason and a mandatory protected audit reference. Every policy is **recorded for review**. There is no activation or operational-approval flag.

`CriterionAssessment` retains application, program, criterion, sequential revision and previous finding, policy, DECLARED/NEEDS_REVIEW/VERIFIED/REJECTED state, typed value/unit, observation dates and justified expiry, dispute indicator, source manifest/digest, supporting review identities, reviewer/retained label/time/reason and mandatory audit. The newest revision always controls diagnostics; there is no fallback to an older favorable finding.

`EligibilityReadinessSnapshot` retains the independently evaluated result, source manifest, service/schema version, evaluation time, artifact digest, actor/reason and audit. It is a historical diagnostic observation and cannot authorize processing.

The new migration creates three tables and seven explicit uniqueness/check constraints, with protected foreign keys and new permissions. It contains no data migration, scoring defaults, inferred verification, group assignments or alteration of an existing model. No earlier migration was edited.

Confirmed application migration leaves before G12: accounts 0001; announcements 0004; assistance 0003; audit 0002; core 0001; documents 0003; events 0005; ewaf 0001; members 0003; membership 0004; programs 0005. G12 advances only EWAF to `0002_verified_evidence`, depending on EWAF 0001 and programs 0005. Migration tests restore the complete migration graph after testing old-to-new schema transitions.

No migration was applied to an existing application database. Eventual rollout requires a separately authorized backup/migration procedure.

B1/B2/B3 corrections use the existing JSON policy and source-manifest structures. No further model or migration change is required. New manifests identify evidence contract version 2; diagnostic service version is `g12-v2`. Existing findings without that contract are retained and require review; they are not upgraded or backfilled.

## 4. Criterion sources and provenance

Historical calculation order remains **SI, ES, PA, ND, PR**. No historical mathematical code, snapshot or result was rewritten.

| Criterion | Implemented source/finding | Boundaries |
| --- | --- | --- |
| PA | Server-resolved non-voided `AssistanceRelease` records for the member, with receipt IDs, linked applications, dates, recorders, type and release/void state digest | Excludes undelivered selections, pending assistance and attendance. Diagnostic all-retained count is not an Association counting policy. VERIFIED findings require an explicitly recorded supported all-retained scope; other/unresolved scopes remain pending. No inferred cutoff, type restriction or external history. |
| SI | Monthly income and a separately entered socioeconomic assessment have distinct source types; finite nonnegative decimals with storage precision checks | Stored income begins as a declaration. VERIFIED findings require current supporting reviews and explicit officer confirmation. Government-program status is a reserved, blocked source type; no 4Ps/Listahanan values or classification are created. |
| ES | Original employment text is preserved; optional categorical finding references documented categories and authority | No predefined category set or numerical encoding. Unlisted outcomes are rejected. |
| ND | Exact recorded nonnegative integer, including explicit zero | Missing finding remains missing. VERIFIED requires a supporting review. No dependent definition, roster or observation period is invented. |
| PR | Documented outcome against recorded program-specific rubric/category definitions and current eligibility-review findings | No numerical relevance value or bonus. Relevance cannot override eligibility. |

Policy JSON accepts only evidence definitions, source types, units, documented categories/rubric, observation rule, freshness interval, rule-authority reference and PA scope. Categories, rubric, observation/freshness and scope rules require their separate recorded authority reference. Recording these references does not certify Association approval or permit scoring. No definitions are seeded. The numeric limits enforced by validation are storage/finite-value limits, not scoring bounds.

Manifests retain application/member/program versions; submission provenance digest; minimal membership approval/manual-verification audit identities; profile-value digest; current photo/review identities and observed hash; required document identities/hashes and latest verification metadata; requirement snapshot and answers digest; eligibility case digest/checklist/log identity; approval-control version/binding/terms revision/digests; and PA source set/digest. Reviewed values and original employment text remain private. Names, birthdates, addresses, identification numbers, file paths and document contents are not copied into these manifests.

Review IDs supplied by a browser are resolved against the application's member. Current review identity, verified state, member version, expiry and file digest must all match. Actor, timestamps, digests, revision numbers, expiry and derived profile/release values are server-controlled. Client metadata cannot replace them.

### Independent review corrections

- **B1:** `evidence_mappings` is optional in draft definitions, but mandatory for a VERIFIED SI/ES/ND source. Each mapping identifies the exact membership requirement and document type, a criterion/source-specific substantiation basis, and its authority reference. The policy recorder's permission and confirmation are mandatory; the server validates type/requirement relationships. Every supplied verification must match that source's mapping. A generic unrelated review, extra irrelevant review, forged relationship, approval flag or missing authority fails. Alternative socioeconomic assessments require their own mapping. Tests use distinct SI, ES, ND and PR documents, never one generic proof. Claimed authority is retained evidence, not a certification of Association approval; operational acceptance remains blocked.
- **B2:** `rubric_definition` identifies program, positive rubric version, current approved terms digest, authority reference and stable item IDs. Each item names an actual program requirement, documented categorical outcomes, evidence mappings and explicit applicability. The currently supported applicability contract is only explicitly recorded `all_applications`; conditional/exempt rules remain pending. VERIFIED PR requires matching current retained terms and approval binding, current eligibility-review provenance, one documented evidence-backed finding per item, and separate officer attestation. Answer findings retain answer digests and supporting current verifications; document findings require the exact current verified reused program document. Bare descriptions/categories, missing items, unrelated program/requirement IDs, stale answers/requirements, absent binding, forged reviews and missing attestation fail. No outcome is converted into points or eligibility. Direct-upload relevance verification without a current supporting source contract remains pending.
- **B3:** Program-document manifests now retain program requirement/type, source membership requirement/type, source document, current verification identity and both source/current program-file hashes. Readiness requires exact agreement with `reusable_document_type_id` in the immutable application requirement snapshot. Missing historical type definitions return `REUSABLE_TYPE_DEFINITION_PENDING`; no guessed fallback or snapshot rewrite occurs. Mismatches return `REUSABLE_TYPE_MISMATCH`, while unrelated verification/source or changed bytes fail source validation. Existing valid/current, revoked and expired cases remain covered.

`ewaf/test_evidence_corrections.py` maps B1 to `CriterionMappingTests`, B2 to `RelevanceFindingTests` plus its exact-document provenance test, and B3 to `ReusableTypeTests`. Shared enforcement is in `ewaf/evidence_rules.py`, called by recording and readiness. Review forms expose structured relevance findings and a separate attestation; restricted history retains the immutable item provenance.

Current file hashes describe bytes observed during G12 capture. Existing photo/direct-upload records do not retain verification-time hashes, so this increment makes no retrospective authenticity claim. Establishing that historical byte identity remains a prerequisite for any future operational acceptance contract that requires it.

## 5. Readiness logic and reason codes

`assess_readiness()` is permission checked and read-only. It returns `eligibility_readiness`, `criterion_completeness`, `governance_readiness`, `processing_authorization_readiness`, grouped reasons with source references, criterion references and the source manifest/digest. It makes no eligibility decision and never changes application status.

Eligibility checks current active membership and retained verification/approval provenance; submission provenance; an ordinary ELIGIBLE candidate; applicable active disability qualifications; current manual photo verification and available bytes; every required snapshot document/answer; a complete passing checklist; current active Eligible status; pending human decision; matching eligibility audit; and current member/program review versions. Original submission member versions remain historical and are not overwritten or required to equal today's member version. An expired submission session is not itself a blocker.

Criterion diagnostics use the latest finding for each identity. Missing, unverified, rejected, disputed, expired, superseded, changed-source and corrupted-audit/artifact findings block completeness. Supporting-document expiry is checked at evaluation time even without a database change. Source comparisons are deliberately conservative: a change in captured member evidence or PA context may require renewed criterion reviews rather than silently preserving an acceptance claim.

Governance independently checks EWAF applicability, publication/internal policy, explicit binding projection, actual terms digest and policy/terms linkage. `CRITERION_POLICY_UNAPPROVED` always remains present: G12 has no operational evidence-policy approval contract. `PROCESSING_GATE_UNAVAILABLE` always blocks processing. `require_operational_evidence()` unconditionally raises that code; snapshots are never acceptance tokens.

Reason vocabulary:

- Membership/application: `MEMBER_INACTIVE`, `MEMBERSHIP_PROVENANCE_REVIEW_REQUIRED`, `APPLICATION_INVALID`, `SUBMISSION_PROVENANCE_REVIEW_REQUIRED`, `APPLICATION_NOT_CANDIDATE`.
- Eligibility/evidence: `QUALIFICATION_REVIEW_REQUIRED`, `QUALIFICATION_FAILED`, `IDENTITY_REVIEW_REQUIRED`, `REQUIRED_EVIDENCE_MISSING`, `EVIDENCE_REFERENCE_INVALID`, `EVIDENCE_REJECTED`, `EVIDENCE_EXPIRED`, `EVIDENCE_DISPUTED`, `ELIGIBILITY_PENDING`, `ELIGIBILITY_INELIGIBLE`, `ELIGIBILITY_STALE`, `CHECKLIST_INCOMPLETE`, `CHECKLIST_FAILED`, `HISTORICAL_DECISION_REASSESSMENT_REQUIRED`.
- Criteria/integrity: `CRITERION_MISSING`, `CRITERION_NOT_VERIFIED`, `CRITERION_REJECTED`, `CRITERION_POLICY_CHANGED`, `SOURCE_CHANGED`, `ARTIFACT_INTEGRITY_FAILED`.
- Governance/processing: `EWAF_NOT_APPLICABLE`, `PROGRAM_POLICY_UNAUTHORIZED`, `PROGRAM_UNAVAILABLE`, `BINDING_INVALID`, `TERMS_CHANGED`, `POLICY_TERMS_CHANGED`, `CRITERION_POLICY_UNAPPROVED`, `PROCESSING_GATE_UNAVAILABLE`.
- Corrected evidence contracts: `EVIDENCE_MAPPING_PENDING`, `EVIDENCE_MAPPING_INVALID`, `CRITERION_EVIDENCE_UNSUPPORTED`, `EVIDENCE_CONTRACT_REVIEW_REQUIRED`, `REUSABLE_TYPE_DEFINITION_PENDING`, `REUSABLE_TYPE_MISMATCH`, `PR_RUBRIC_PENDING`, `PR_REQUIREMENTS_STALE`, `PR_ATTESTATION_REQUIRED`, `PR_FINDINGS_INCOMPLETE`, `PR_EVIDENCE_INVALID`. Recording returns explicit validation errors; readiness returns applicable reason codes with assessment/document references.

No suspension or resumption state was invented. That contract belongs to G06-B2/B3.

## 6. Permissions, privacy, audit and concurrency

All entry points require an authenticated active staff user, `accounts.access_dashboard`, existing program/application/member view permissions and explicit view permissions for all three new artifacts. Separate permissions govern `declare_criterionassessment`, `review_criterionassessment`, `record_evidencepolicyrevision` and `record_eligibilityreadinesssnapshot`. No existing staff account or group receives new permissions automatically.

Private views use the existing Admin layout, labeled controls, text state indicators, pagination, CSRF protection, method restrictions and `never_cache`. Historical/final applications remain diagnostic-only; G12 cannot reopen them. Existing protected attachment routes remain responsible for file access. No public/member-facing evidence route was added.

Each new artifact and its mandatory `ProgramLog` commit atomically. The model validates program/application/actor/action/digest association. General program logs retain a neutral message and digest, not confidential review explanations or economic values; those remain in restricted G12 records. Instance saves/deletes, queryset updates/deletes, bulk creation/replacement and existing-primary-key insertion are blocked through supported APIs. Protected foreign keys retain dependencies. These are application safeguards, not claims of protection against privileged SQL or storage administrators.

Writes retain **Terms mutex → Program → Application → Member** order. Existing photo, eligibility, document and profile writers are serialized by their existing parent locks; G12 does not acquire unrelated program/release locks after Member. Expected source digest includes program/application/member counters and independent approval-control state. The latest policy and criterion revision are checked under lock.

Cross-program PA capture uses the same Member lock already held by `record_release()` and `void_release()`. Tests hold an actual writer transaction after its write, start a competing PA capture, verify it blocks, then commit the writer and verify the old digest is rejected. A release committed after an earlier capture makes that retained finding outdated on subsequent diagnostics. No release/void transaction implementation was changed.

GET requests never call the write lock helper, create a technical control row or retain a snapshot. Snapshot retention requires explicit POST and fresh revalidation.

## 7. Actual validation

Every database-backed command used `scripts/g12_test_runner.py`: a newly initialized loopback-only local MySQL instance, new temporary datadir, random synthetic credentials, verified `@@datadir`/port and empty-instance check, restricted grants for `g12_empty` and distinct `test_g12_disposable`, filtered inherited environment and `PYTHON_DOTENV_DISABLED=1`. Existing `.env`, application databases, uploads and hosted services were not accessed. Each runner shuts down its temporary server and Django destroys its test database. No production enforcement setting was enabled.

Final checks:

| Check | Actual result |
| --- | --- |
| Focused G12 and navigation suite | **108 passed**, 31.009 seconds |
| Full Django regression suite | **592 passed**, 179.727 seconds; **94 new backend tests** relative to the 498-test baseline |
| Explicit isolated migration/preservation rerun | **2 passed**, 4.031 seconds; also included in focused/full counts |
| Explicit G12 headless-browser suite | **1 passed** |
| `makemigrations --check --dry-run` | Passed: no changes detected |
| `check --database default` | Passed: no issues |
| Syntax, Git whitespace and unexpected-file checks | Passed: 21 Python files parsed; tracked and new-file whitespace clean; exact 29-file inventory; nothing staged |

All database-backed commands used `.venv/Scripts/python.exe scripts/g12_test_runner.py` followed by:

- Focused: `test ewaf.test_evidence ewaf.test_readiness ewaf.test_evidence_corrections ewaf.test_evidence_concurrency ewaf.test_evidence_migrations core.tests.test_workspace_navigation --noinput --verbosity 1`
- Full: `test --noinput --verbosity 1`
- Explicit migrations/preservation: `test ewaf.test_evidence_migrations --noinput --verbosity 2`
- Browser: `test scripts.g12_browser_qa --noinput --verbosity 1`
- Drift: `makemigrations --check --dry-run`
- Checks: `check --database default`

Final correction logs: focused `santolan-g12-tests-czlibwip`; full `santolan-g12-tests-0fibiunr`; explicit migrations `santolan-g12-tests-h3632g7d`; browser `santolan-g12-tests-h6dxv1si`; migration drift `santolan-g12-tests-7pmc2fsf`; explicit check `santolan-g12-tests-_byedihe`, under the local Windows temporary directory. Logs contain synthetic execution evidence. The browser directory also retains `g12-history-mobile.png`, visually inspected after the run. Browser runtime: 8.145 seconds.

Final Git review confirms 5 modified and 24 new proposed repository files, exactly matching the inventory above. Branch and HEAD remain the preflight values; nothing is staged. The static check used the ignored local helper `.local/g12_static_check.py`, which is a validation artifact outside the proposed file inventory. No credentials, private uploads or generated test data are included in the proposed changes. The corrected review ZIP is `.local/g12-final-review-corrected-2026-10-13.zip`: all 29 proposed files, synthetic validation logs, the inspected screenshot and a SHA-256 manifest. This is a changed-source package; the baseline repository and installed dependencies are required to rerun it.

Browser coverage: six private pages at 320/390/768/1440px; horizontal-overflow checks; heading/control labels; keyboard confirmation; no file/budget/score/rank controls; incomplete PR VERIFIED submission rejected with `PR_FINDINGS_INCOMPLETE`; actual disputed-finding POST; retained snapshot POST; no JavaScript errors. This is focused accessibility/layout QA, not a screen-reader certification or institutional UAT.

The correction's first focused run passed 106 tests (`santolan-g12-tests-8eeia2nh`, 33.247 seconds). Two additional negative/positive boundary regressions were then added and the final focused/full runs above passed. There were no failing correction validation runs. During the original pre-correction G12 implementation, diagnostic runs had corrected test expectations for CSRF/method order, an escaped navigation label and browser label punctuation. The correction results above supersede the original 82-focused/566-full/1-browser report; they are locally executed results, not independent owner acceptance.

## 8. Preservation validation

Synthetic preservation tests compare complete rows across membership, members, documents, programs, assistance, announcements, events and the historical EWAF models, excluding only the newly appended G12 audit entries/artifacts. Fixtures include original application references/tokens/statuses/versions/answers/snapshots, membership/doc review histories, eligibility logs, successful and voided releases, explicit terms/approval bindings/control state, published announcement/revision payloads, and historical Configuration/ApplicationInput/RankingRun/Snapshot values. Both evidence operations and migration down/up preservation checks passed in the focused run.

New tables remain empty after migration; no old declaration becomes verified. Historical criterion order and mathematical fields remain unchanged. No Program.version bump, budget editing, PDAO enforcement activation, retired EWAF mutation, automatic beneficiary decision or publication change was introduced.

## 9. Policies intentionally pending and G14–G18 blockers

Pending Association decisions remain: SI measure/basis/period/evidence and government status handling; ES categories/mapping/reviewer/freshness; ND dependent definition/verification; PR rubric/outcomes/reviewer; PA scope/cutoff/types/external coverage; observation/expiry/disputes/corrections; alternative/no-photo evidence; review during suspension; reassessment and resumption; AHP judgments/weights; normalization directions/bounds; classifications; ranking ties and exceptions. Test-only definitions do not approve any of them.

- **G14:** needs approved evidence policies plus versioned calculation/configuration authorization; G12 policy records alone are insufficient.
- **G15:** needs approved encodings, directions, bounds, weights, precision and thresholds. G12 stores typed findings but performs no normalization or scoring.
- **G16:** needs a fully revalidated eligible/evidence-complete pool, common approved configuration/cutoff and the future processing gate. Every G12 operational attempt is currently blocked.
- **G17:** needs governed affected-pool recalculation and history integration for source, review, expiry, policy, binding and cross-program release/void changes. G12 detects stale provenance but does not automatically recalculate anything.
- **G18:** needs a current complete ranking and independent eligibility/processing authorization before existing human selection/slot/publication/release workflows can consume it.

G06-B2/B3 remains a required external dependency for operational processing, suspension, final-case reassessment and resumption. PDAO enforcement cutover, deployment and institutional acceptance remain separately authorized work.

## 10. Independent review recommendation

**GO for independent review of the bounded private evidence/provenance and diagnostic foundation. NO-GO for operational EWAF scoring/ranking, accepted-input consumption, beneficiary processing through G12, production rollout or PDAO cutover.**

The 70% baseline remains unchanged. Work stops after validation/documentation. No staging, commit, push, deployment or existing application-database migration is part of this increment.
