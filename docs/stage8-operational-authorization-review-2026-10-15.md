# Stage 8 operational authorization package: G16/G17 evidence review

Date: 2026-10-15. Branch: `feature/events`.
Inspected HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1` plus the preserved index and working tree below.
**Review and proposal only. Recorded milestone remains 70%.**

## 1. Decision summary

**Technical recommendation:** the inspected evidence supports accepting G16 and G17
within their authorized synthetic scopes. No blocking defect was identified in
those supported fixture interfaces. This is a scoped source/evidence review, not
owner/client sign-off or a claim that every possible defect has been excluded.

| Gate | A: evidence supports synthetic acceptance | B: owner acceptance recorded | C: operationally implemented and accepted |
| --- | --- | --- | --- |
| G16 | Yes, with the limitations in section 3 | No acceptance record identified; formal acceptance remains pending | No |
| G17 | Yes, for the bounded in-memory simulation | No acceptance record identified | No |
| G18 / Stage 8 | Synthetic tests are preparatory evidence only | No new acceptance sought or recorded here | Incomplete; no 80% claim |

**Recommended next implementation:** an unexposed, default-disabled application
backend for a complete program pool, immutable numerical result history and
same-policy verified-source recalculation. Use actual Django models, services,
permissions, transactions and MySQL concurrency tests with fictional records.
Add a durable request/invalidation mechanism; retain the existing G16/G17 fixture
interfaces as regression oracles. This would produce reusable operational code,
not another fixture-only state machine. It would still be an incremental backend
delivery, not live activation or complete automatic operational G17.

Before live use, every included program needs an explicitly authorized policy
bundle and processing contract. Current G12/G14/G15 documentary artifacts cannot
provide that authority. The plan below separates permission to develop/test the
backend from approval of business policy, runtime exposure, real data and deployment.

## 2. Evidence identity, scope and verification performed

### Snapshot captured before review

- 503 existing tracked/staged/untracked source, test, fixture and documentation
  files captured by path and SHA-256. This includes 16 staged G16 additions and
  21 untracked files: 19 G17 files plus the G16 revalidation and G17 plan.
- Working copies have no tracked differences from the index. All staged entries
  are additions with mode `100644`; full blob IDs appear in section 9.
- SHA-256 of canonical JSON of the sorted 503 path-to-hash map:
  `4aa6626300ecaa750ac8f4158169a5e9906c8392d7255d26d918aeaf058dc965`.
- SHA-256 of exact `git diff --cached --raw --no-abbrev` output:
  `5036180c963560854148b3192d71b93ccb34695568d60ca61edf6c3a0c21d9da`.

Read AGENTS and the current master first, then the development guide, Stage 8
roadmap, active Open Decisions, membership amendment/DEC-027, October 10 impact,
workflow contracts and acceptance criteria. Inspected G12–G15 evidence/readiness,
configuration/scoring records and services; G16/G17 engine, loader, policy,
readiness, test and preservation bodies; terms/binding, member/document writers,
assistance decisions/releases and publication gates. Read all four requested
checkpoint documents. The older implementation-gap/impact documents describe
dated gaps; later validated G12–G17 additions supersede their claims of absence
only within those additions' bounded scopes. Navigation has already been revised;
this package does not propose redoing it.

### Relationship of retained tests to this source

Rehashed all 484 files in `.local/g17-validation-2026-10-15/before-files.json`
and all 19 additions in `preservation.json`: **503/503 match**. The preservation
file itself hashes to `08ac6f93ac573aaf5205c7934356cf99b22de47a18aff22219341da5f3a9898f`.
The saved pre-G17 staged manifest also matches the present index byte-for-byte.
Rehashed the actual retained logs, read their summaries and checked their test
line counts against the reports. These are **reused October 15 implementation
results, not newly run suites**:

| Retained G17-validation artifact | Reported exit | Verified log result | SHA-256 |
| --- | --- | --- | --- |
| `g16-focused.log` | 0 | 54 tests, OK, 8.378 s | `21ae5689f6e5d0f86bec5bbf570e05744695e14ac05c375b7e6cf1224a6f67a5` |
| `g17-focused.log` | 0 | 56 tests, OK, 6.277 s | `67b223297e1b2495f6c57df241be266fa0c71005fee1cf854ec8c95931d8b043` |
| `g12-g14-g15-regression.log` | 0 | 198 tests, OK, 91.706 s | `4484618a2b0775bb3fb968b646d69fc9e8b0284550c721739d8c52eed00c7066` |
| `full-suite.log` | 0 | 809 tests, OK, 224.934 s | `1409128b3aa308828f99543a2e766ea4450681c13508df1a1e7d9d7317b960f2` |
| `system-check.log` | 0 | No issues, 0 silenced | `f87ceb15410bde28ff826ce26228e0576558258fa64d145847921a593a61ee63` |
| `migration-drift.log` | 0 | No changes detected | `93e6e2d5be3c054add80c0f19101608803f7ca8a7df1fa41f76bbb9a1f570f4a` |

All four suites reported zero failures/errors/skips. The 52-test development run
is superseded by the final 56-test run. The five older G16 revalidation log hashes
also match [its table](g16-revalidation-2026-10-15.md#L103); its 753-test full run
predates G17 and is not substituted for the 809-test evidence. Counts overlap.
Exact historical commands are retained in [G17 validation](g17-recalculation-history-validation-2026-10-15.md#L122).

**Targeted verification now:** pure Python reloaded all four pinned G16 fixtures
and five G17 pools, replayed all seven G17 scenarios, and compared their entire
JSON reports with retained `*-output.json` artifacts: **7/7 identical**, exit 0.
No `django.conf`, `django.db`, `config.settings` or `MySQLdb` module was loaded.
The command used `.\.venv\Scripts\python.exe -X utf8 -B -c` with this body:

```python
import sys, json
from pathlib import Path
from ewaf.recalculation_diagnostics import simulate_fixture
from ewaf.recalculation_fixtures import SCENARIOS, POOLS, load_pool
from ewaf.ranking_fixtures import FIXTURES, load_fixture
[load_fixture(n) for n in FIXTURES]
[load_pool(n) for n in POOLS]
rows = [(n, simulate_fixture(n) == json.loads(
    (Path('.local/g17-validation-2026-10-15') / (n + '-output.json')).read_text()))
    for n in SCENARIOS]
assert all(v for n, v in rows)
assert not any(n in sys.modules for n in ('django.conf', 'django.db', 'config.settings', 'MySQLdb'))
```

No Django checks, migrations, focused Django suites, full suite, browser tests or
server were run in this review. The unchanged runner at `scripts/g12_test_runner.py:18`
still creates/validates fresh disposable MySQL, filters environment, disables
`.env`, and uses its explicit interpreter. Historical test setup applied existing
migrations only in disposable databases. Its PDAO setting is disabled in the child
environment; this is not evidence of institutional PDAO cutover acceptance.

**Evidence limits:** local logs/manifests are available and consistent, but are
not signed CI attestations. Logs do not themselves bind a process exit code to a
source hash; exits are recorded in the prior execution/report evidence, and the
post-run manifest establishes the reviewed source relationship. No owner/client
sign-off, live numerical RBAC test, new durable ranking graph, transactional
G17 audit, multi-applicant promotion race, or operational G18 acceptance artifact
exists in these packages. Those gaps block operational acceptance, not the scoped
synthetic acceptance recommendation. No production/private data was inspected.

## 3. Gate-by-gate synthetic assessment

Unqualified Python filenames in this section are under `ewaf/`. Line references
describe the preserved review snapshot, not future implementation files.

### G16

| Criterion | Source and meaningful test evidence | Assessment |
| --- | --- | --- |
| Bounded invented inputs only | `ranking_fixtures.py:12`; `ranking_diagnostics.py:69,141,277`; loader pins, strict JSON/schema/resource limits, synthetic identifiers; `test_ranking_diagnostics.py` tests path/ID bypass, duplicate JSON keys and checksums | Supported; private evaluator remains a developer seam, not an arbitrary-code security boundary |
| Complete common pool/version and reproducible calculations | `ranking_diagnostics.py:186` replays G14/G15 and compares full retained results/digests; tests missing/extra/duplicate candidates and forged/rehashed weights/contributions | Supported; incomplete pool yields no successful subset |
| Precision and ties | `ranking_diagnostics.py:109,123`; tests near ties, equivalent Decimal spellings, ambient precision, permutation invariance and presentation-only ID ordering | Supported at the existing 50-digit profile; no approved numerical rank convention or tie-selection procedure inferred |
| No selection/capacity inference | `ranking_diagnostics.py:253`; capacity-overflow/tie-boundary tests retain every candidate and assert no selection fields | Supported |
| Score-free applicant adapter and closed authorization | `ranking_readiness.py:7,17`, `ranking_policy.py:4,10`; 12 readiness tests cover permissions before reads, wrong program, missing/zero, stale evidence, B1/B2/B3 and forged numerical payload | Supported for real diagnostic reads; not evidence of numerical applicant authorization |
| Preservation | `test_ranking_preservation.py:25` rejects non-SELECT SQL and compares all registered model rows; `:37,44` checks EWAF migration leaf and disabled legacy calls; current source/index unchanged | Supported. Name-based schema assertions alone would be insufficient; actual source/inventory and unchanged schema supplement them |

54 tests comprise 35 engine, 4 policy, 12 readiness and 3 preservation cases.
**No synthetic-scope blocker found.** Missing operational input resolver,
effective policy, persisted current pool, promotion/audit and final-decision
consumer are intentional boundaries. Formal G16 acceptance still needs an
explicit owner decision identifying the exact synthetic scope and snapshot.

### G17

| Criterion | Source and meaningful test evidence | Assessment |
| --- | --- | --- |
| Initial result and separately identified successors | `recalculation_diagnostics.py:304`; tests `:58,70,78,87,97` in `test_recalculation_diagnostics.py` verify first math, changed input, changed judgment, predecessors and unchanged old scores/ties | Supported |
| Deep snapshot isolation and traceability | Engine `:68,76,117,188`; tests `:109,119,134,142,154,160` mutate caller source, loaded pools, exported graphs/events and test version-content conflicts | Supported; hashes provide consistency, not institutional authority |
| Explicit permitted changes / policy blockers | Engine `:208,230,269`; tests `:248,255,263,270,281,292,330` cover unresolved policies, unsupported PA/pool/terms, trigger mismatch, version-only and date/evidence changes | Supported for the documented illustrative rules; no operational trigger policy approved |
| Stale/incomplete evidence | Engine `:89,202,304`; tests `:166–242,307,319` exercise changed-then-restored generations, expired evidence/date rollover, rejected/disputed findings, missing input and full manifest | Supported; flags model outcomes, not verification of real files or eligibility |
| Simulated permission/audit | Engine `:193,269,304`; tests `:341,356,362` check denial before calculation and immutable actor/reason/version/outcome records | Supported as simulation only; whole diagnostic report is not a private-history authorization interface |
| Repetition/interleaving | Tests `:379–425` verify reused result/new attempts, calculator not called, one same-context promotion, repeated finish cannot restore older currentness, unfinished/blocked attempts cannot promote | Supported; explicit event order is not multithreaded/database concurrency or crash recovery |
| Isolation/preservation | `test_recalculation_preservation.py:26,69,97,108,121`: forbidden settings/DB/network/write imports/IO, zero SQL on replay, existing rows/schema/routes/guards unchanged | Supported within the inspected source boundary |

50 behavior tests plus 6 preservation/isolation tests. **No blocking defect found
for the seven supported scenarios.** Limitations: fixed five criteria/fixed bounds,
immutable fixture actor set, no runtime revocation during work, no durable recovery,
and private dependency on G16 `_evaluate_payload`. `report()` at engine line 338
uses the last event to determine `complete`; an observation/denial/repeated finish
can make it false even while a simulated current result exists. This documented
replay-outcome field must never be reused as an operational currentness token.
Attempts preserve their initial outcome; terminal outcome lives in audit events.

Neither gate's successful tests implement classification, real ranking previews,
waitlisting, real permissions for numeric output, persistent numerical history,
transactional result audits or human selection. No tests were weakened to conduct
this review. No corrective source change is proposed as a prerequisite to the
synthetic acceptance decisions.

## 4. Policy-decision matrix

References below use repository-root paths and line numbers. `OD` means
`../00 - Project Overview/Open Decisions.md`; `API` means
`../05 - Development/API and Workflow Contracts.md`. **Approved** means documented
settled requirement, not a completed implementation. Proposed recommendations here
need recording by the appropriate authority. No named institutional approver or
delegation roster for EWAF was supplied; the project owner must identify the
Association's authorized policy signatory. Developer recommendations cannot fill it.

| Issue / definition and source | Status | Implemented diagnostic behavior | Operational dependency / extent | Exact decision and appropriate owner; recommendation if useful |
| --- | --- | --- | --- | --- |
| Pool, admission, exclusions and cutoff: eligible applications only, complete accounting and no favored subset. `API:74`; `docs/implementation-gap-analysis-2026-10-10.md:175`; `ranking_policy.py:4`; OD OQ-04/09/11 | Eligible-only/full-pool requirement approved; admission timing, exclusions and cutoff unresolved | G16 verifies a fixed manifest; G17 blocks pool changes (`:208`) | Initial ranking needs a defined full pool. Later membership/admission changes can remain blocked separately | Association program-policy authority: define who enters at which cutoff, treatment of pending/late/corrected cases, exclusions and reopening. Recommend first slice only after intake closes, with every submission accounted for and any undecided admission blocking the pool; capacity never truncates it |
| **PA = Previous Assistance**, not program approval. OD:17,31 (OQ-08/19); `assistance/models.py:56,61`; `assistance/services.py:20,205,243`; `ewaf/evidence.py:127,169` | Actual non-voided receipt source and exclusion of attendance/unfulfilled selection settled; window/type/cutoff/direction unresolved/conflicting | G12 diagnostic counts all retained successful releases across the member's programs; `evidence_services.py:94,108` supports only explicitly recorded all-retained scope. G17 PA-change path blocks | An approved PA measure is needed for every included five-factor run. A release/void in another program can stale this program; never ignore it because cross-program recomputation is deferred | Association program/EWAF authority: choose all-retained vs period/type scope, as-of cutoff, backdated/late records/void treatment and direction. Existing support makes all-retained simpler, but it is not an approved default. A windowed policy requires a separately versioned source resolver |
| **Protected terms**: program name/description/type/windows/schedule/slots/amount/benefit/requirements/EWAF/method/photo/correction deadline, linked-event terms, configured requirements/document-type references and disability qualifications. `programs/terms.py:12,33,43,55,105,122`; `binding_services.py:38,78` | Existing freeze approved/implemented; major-revision/resumption policy unresolved | G17 `TERMS_CHANGE` blocks; G12 compares actual vs retained terms. Approval records/bindings exist; they do not authorize EWAF | Unchanged terms path may be developed; any changed terms/binding must stop processing. Current contracts still require G06-B2/B3 before operational processing | Association approval authority + owner: decide suspension, reapproval, reassessment and individual/cohort resumption; external PDAO remains manual. Recommend retaining freeze in first slice. A narrower unchanged-terms processing contract requires explicit authorization, not an assumed exemption from G06-B2/B3 |
| Configuration/evidence/scoring authorization and revision: lock before opening; `API:72,91`; OD:18; `configuration_services.py:123,134`; `models.py:238,263` | Lock/new-version/history requirements approved; effectiveness, duties/separation and post-opening revisions unresolved | Review/documentary evidence and scoring proposals never become effective; all guards closed | Blocks any live first calculation. Post-opening replacement can be excluded from first slice without authorizing initial configuration implicitly | Association designates policy approver and allowed separation, scope/effective/withdrawal dates and allowed revisions. Recommend distinct effective authorization artifact bound to exact versions, never flip an existing documentary row to approved |
| Recalculation eligibility/triggers: authorized changes/corrections trigger full affected-pool recomputation. `API:74`; G17 plan:44–59 | Requirement approved; exact allowed events/resumption proposed/unresolved | G17 allows illustrative input/config/evidence/date transitions, rejects mismatched component changes | Same-policy verified-source correction path can be built first. Configuration, pool, terms and post-decision revisions remain blocked paths | Association approves which corrected sources may re-enter and required review sequence; owner approves initial implementation subset. Recommend invalidate immediately and calculate only after renewed complete reviews; no automatic decision changes |
| Stale/incomplete evidence: latest findings; no imputation, fallback or immediate ineligibility. OD:20,35; `readiness.py:18`; `evidence_rules.py`; G17 plan:112 | Conservative blocking and inclusive expiry established; accepted evidence/rubrics, freshness periods/dispute resolution unresolved | G12 checks real current sources; G17 simulates missing/stale/expired/rejected/disputed/B1/B2/B3 reasons | Blocks affected pool's usable result, not unrelated programs. Old snapshots remain historical | Association evidence-policy authority approves source types, review mappings, observation/expiry and dispute/correction procedure. Preserve existing block behavior; direct-upload/alternative evidence without supported provenance stays blocked |
| Identical requests, conflicting changes, concurrency and recovery. G17 plan:120–142; `scoring_services.py:64`; `recalculation_diagnostics.py:269,304` | Preserve history/currentness approved; production deduplication/leases/retry contract proposed | Same-context reuse and interleaved generation checks in memory; G15 locks one application only | Required before any persistent promotion; test interleavings do not prove it | Owner authorizes technical contract with Association authority for who may retry/when. Recommend immutable attempts, content-bound idempotency, one guarded current pointer, stale-generation rejection and durable source events; no silent reuse of older approved-looking data |
| Ranking to human decision. `API:76`; OD:13,22,24; `assistance/services.py:159–198` | Human decision, independent eligibility and slots settled; EWAF handoff, tie resolution/waitlists/exceptions unresolved | `require_ranked` remains disabled. G16 capacity is explanatory; G17 promotes nobody to Selected | Does not block storage of exact score groups; blocks G18 consumption/selection without approved handoff and tie policy | Association final-decision authority defines actionable ties, reservation/release, optional waitlist and exceptional-decision policy. Recommend preserve exact ties and block unresolved boundary-tie decisions; no ID/time/random tie-breaker. Optional exceptions/waitlists may remain unavailable |
| SI/ES/ND/PR measures and accepted encodings. OD:15–16,35; `evidence.py:198`; `scoring_inputs.py:59` | Five reference diagnostics implemented; actual measurement/rubric policy unresolved | SI decimal sources; ES approved category/text; ND whole count; PR structured findings. Government-status source blocked. Numerical encodings are proposals | Blocks live use of each affected criterion/program; no arbitrary new criteria in first slice | Association approves SI source/unit/period/household meaning, ES categories/encoding, dependent definition, PR rubric/aggregation/numeric encoding and evidence. Do not invent zero/maximum values or 4Ps/Listahanan points |
| SI/PA directions. OD:30–31 OQ-18/19; workbook evidence:22–27 | Conflicting workbook ascending vs older inverse wording; client decision required | Both directions are math examples; no default operational direction | Blocks live scoring for the affected program | Association/client method authority signs direction with worked meaning-based examples. Preserve both diagnostic capabilities; do not reuse historical inverse or fixture ascending as approval |
| AHP, criteria count/order and normalization. OD:19–21; `ahp_validation.py:82`; `normalization.py:53`; AT-11/12/30 | Workbook row-average method established; actual judgments/scale/precision adoption and bounds unresolved | Five reference criteria in SI,ES,PA,ND,PR order, RI(5)=1.12, reference CR<0.10, fixed bounds only | Approve exact supported program contract for first slice; different count or pool-derived bounds is a separate blocked path | Association/methodology authority approves matrix, consistent scale, criterion mapping, bounds and edge handling. Recommend fixed bounds and current exact order for first slice only if legitimate for that program. Different programs need approved definitions, not a universal five-factor mandate |
| Decimal storage/display, ties and workbook defects. OD:21–22; `normalization.py:6–13`; `models.py:60`; workbook evidence:22–27 | Preserve validated 50-digit precision/exact ties settled for current code; institutional numerical/display policy unresolved | No float/epsilon/quantization tie-breaking; G16 exact groups | Lossless storage is mandatory for backend. Display/rank-number decisions can be deferred if no UI/rank numbers; do not narrow stored precision | Owner authorizes lossless canonical Decimal text storage; Association/method reviewer approves institutional profile/display. Recommend retain existing 50-digit HALF_EVEN settings and no additional rounding. Broken C29:C33 and pasted caches are not a calculation oracle |
| Classification. OD:37 OQ-25; roadmap:11; workbook evidence:27 | Printed bands are examples; exact endpoints/rounding/internal/public use unresolved | No classification in G16/G17 | Can remain absent in the numeric backend slice; required target classification still blocks final Stage 8 acceptance | Association decides gap-free boundaries and precision usage. Do not add labels or infer eligibility/selection from a label |
| Photo alternatives, final-case reopening, privacy/retention. OD:11–12,25,34,36; `readiness.py:35,49`; `announcements/results.py:22,32` | Existing photo/assisted correction, immutable refs and DEC-025 masks settled; alternative state mapping, exceptional reopening, expanded disclosure/retention unresolved | Ordinary ELIGIBLE/pending-decision/current-photo path only; selected/completed/released reassessment blocks; no new public output | Existing approved required-photo programs can be the bounded test path. Alternative/no-photo, final cases, public output remain separate blocked paths | Association evidence/final-decision authorities and privacy lead: approve alternative state mapping, final-case handling and retention/access. Preserve masks, onsite membership and offline PDAO; no new broad disclosure or forced photo/ID policy |

Decisions already settled and not reopened: onsite Admin-only membership/no member
accounts; secure verified-member applications; immutable references; manual PRPWD;
separate Association and PDAO checklists; explicit human decisions; actual receipt
separate from approval/attendance; no disability/medical-severity EWAF criterion;
no manual final score/rank edits; DEC-025 masks and eight-group Admin navigation.

## 5. Smallest proposed operational backend slice

### 5.1 Scope and genuine dependency boundary

Propose **first complete persisted ranking and same-policy source-correction
history for one governed closed program**, initially tested only with fictional
database records. Include all admitted candidates and a complete accounted-for
submission manifest, one exact effective policy/configuration, existing current
required-photo route, pending human decisions, supported fixed bounds and exact
score groups. Do not set `ProgramApplication.status='RANKED'` yet: G12 readiness
currently accepts only `ELIGIBLE` (`readiness.py:35`), and its source digest includes
status/decision. Changing status would invalidate the very accepted context unless
the later G18 lifecycle contract is deliberately revised.

The code supports real service arguments and persisted foreign-key records, not
SYN-prefixed values or pinned fixture names. Positive tests create fictional
authorization records through the new services and use actual Django permissions;
these test records are not client approval. Unknown policy content remains
unavailable by default. No seed policy, permission grant, historical approval
backfill or permissive `approved=True` bypass is allowed.

**Why this is a useful smaller slice:** current G12 assessments and G14/G15
revision records already supply source/weight provenance, and existing eligibility
and source writers provide transactional boundaries. Durable requests, snapshots,
permission checks and exact replay can therefore be implemented and tested while
live rollout stays off. This is conditional on authorizing the new backend
contract; none of today's guards already permits an operational first run.

**Excluded paths:** post-opening configuration activation, changed admission/pool,
changed protected terms/binding, PA scope changes, historical final cases, optional
identity alternatives, classification, waitlists/exceptions and G18 consumption.
Detect and retain their invalidation/block reasons; do not silently keep current
results or suppress actual source corrections. Ordinary PA release/void changes
must be detected across all dependent programs even if recomputation awaits review
or a missing PA policy. Initial PA scoring itself still requires a defined policy.

Current contracts call G06-B2/B3 a prerequisite to operational processing
(`docs/g12-verified-evidence-validation-2026-10-13.md:180`). A backend test path
may exercise a proposed unchanged-terms processing authorization. **It cannot be
activated live** unless the owner/Association either authorize that narrower
processing contract explicitly, or complete the required G06-B2/B3 work first.
Binding validity alone is never the missing processing authorization.

### 5.2 Reuse and schema analysis

| Existing structure | Reuse / incompatibility |
| --- | --- |
| `CriterionAssessment`, `EvidencePolicyRevision` (`models.py:74,101`) | Reuse exact latest IDs/digests, reviewed values, source/supporting-review manifests; validate anew. Do not reinterpret recorded references as effective approval |
| G14 `ConfigurationRevision/Validation/Review/AuthorizationEvidence` (`:169–256`) | Reuse immutable exact mathematical/review inputs. Last type is explicitly **non-effective**; needs a separate effective authorization artifact |
| G15 `ScoringPolicyRevision` (`:263`) | Reuse proposal content as a versioned referenced input only after explicit new approval. Latest proposal is not the active approved version |
| G15 `CalculationDiagnosticRun/Item/Trace` (`:292–374`) | Cannot hold numeric multi-applicant runs: database CHECK `READINESS_ONLY`, strict score-free validator and one-application equality contract. Preserve unchanged |
| Legacy `Configuration/ApplicationInput/RankingRun/Snapshot` (`:6–68`) | Preserve historical reads. Wrong configuration lineage, mutable one-to-one inputs, mandatory classification/integer rank and Decimal(24,20) conflict with current precision/group/history. Do not retrofit unknown provenance or store new results here |
| `ProgramTermsRevision/ApprovalBinding/ApprovalControl` (`programs/models.py:411,446,472`) | Reuse terms/binding identities and freshness. This controls manual external approval/intake; not an EWAF current-result pointer or authority store |
| `ProgramLog` and protected artifact patterns (`scoring_records.py:28`, `scoring_services.py:19`) | Reuse neutral mandatory audit association and append-only patterns. New operational actions need their own validated payload/domain; don't claim a G15 diagnostic audit authorizes a numerical run |

**Additive migration is necessary for this proposal.** Proposed logical tables
(names provisional for implementation review), with no data migration/backfill:

1. `ProcessingAuthorization`: immutable program-scoped revision with predecessor;
   exact evidence-policy/configuration/validation/review/scoring-policy IDs and
   digests; approved operational policy JSON (admission, cutoff, PA, numeric and
   processing rules); terms/binding/control context; issuer/authority reference,
   scope, effective time, reason and mandatory audit. Revocation/replacement is a
   new event/version, not editing history. No automatic grants from old evidence.
2. `ProgramCalculationControl`: one row per program with active authorization,
   generation/version and current-result FK; mutable only through guarded services.
   No global PDAO-setting reuse and no inference from `Program.version` alone.
3. `RecalculationRequest`: durable immutable request/source-event record with
   source identity/version, initiating actor/audit/reason, kind and idempotency key.
   Store writer-side source scope without locking unrelated Program rows (see 5.5).
   This doubles as the outbox; a separate queue system is unnecessary initially.
4. `RecalculationAttempt`: immutable accepted capture, request, program, captured
   generation/authorization, predecessor result, evaluation date/timezone and UTC
   time, complete pool/exclusion manifest, source versions/digests and input graph.
   Each retry is separately identifiable. Blocked captures retain reasons with no
   partial successful result; terminal lifecycle is append-only events.
5. `OperationalRankingResult`: immutable program/run sequence and predecessor,
   attempt, authorization, context digest, complete manifest/result digest and
   canonical JSON graph of inputs, bounds, full weights, contributions, both score
   scales and exact groups. Store calculated decimals as validated canonical text
   in JSON, not legacy Decimal(24,20), binary floats or SQL lexical score sorting.
   One atomic whole-pool graph avoids a mandatory extra item table in this initial
   slice. Retained application IDs must be server-resolved and program-validated;
   JSON alone does not enforce ownership. Set explicit size limits before coding;
   do not silently adopt the 32-candidate synthetic cap as a business rule.
6. `RecalculationEvent`: immutable started/blocked/stale/failed/reused/completed/
   promoted/invalidated transitions tied to request/attempt/result, actor/executor,
   generation, reason and matching `ProgramLog`. Current-pointer mutation and its
   promotion event commit together. Events also record per-program request handling.

Use PROTECT for real ownership/history FKs, unique program/revision, result per
accepted context/authorization/engine, request-key/content consistency, constrained
states and service/model/queryset guards for append-only artifacts. Cross-program
and predecessor integrity needs validation beyond ordinary FKs; MySQL checks cannot
validate arbitrary JSON ownership. No new table should grant an editable Admin
surface by default. Migration numbering follows verified leaf `ewaf.0004`; proposed
`0005_operational_ranking_history.py` is a filename proposal, not a created file.

### 5.3 Calculation and input boundary

- Reuse `ahp_validation.validate_ahp`, `weighted_scoring.replay_weights`, and
  `normalization.normalize/number/decimal_text/arithmetic_context`. Preserve the
  explicit 50-digit HALF_EVEN settings, traps, full traces and exact comparisons.
- G16's `_evaluate_payload` enforces SYN IDs/source units; it is **not** a runtime
  adapter. G15 `calculate_synthetic` also promises diagnostic output. Authorize a
  narrow extraction of common WSM/exact-group arithmetic into `ewaf/calculation_core.py`
  with existing wrappers returning byte-equivalent diagnostic outputs. Operational
  services call the shared pure kernel through validated accepted inputs, not by
  relabeling real applicants as synthetic or flipping diagnostic authority flags.
- New `operational_inputs.py` resolves the whole program manifest server-side,
  validates current evidence through G12 logic and replays G14 artifacts, then
  extracts private accepted values from exact assessments. It must never strip
  unconditional barriers from a G15 response and call that approval. An explicit
  new authorization/processing guard is a separate prerequisite.
- `scoring_inputs.weight_evidence` currently requires the latest proposal and
  current configuration context (`:32–48`), not a locked active policy. Preserve
  that diagnostic behavior; implement separate active-version semantics so a new
  unapproved draft cannot silently become active or make an old proposal approved.
- Pre-opening authorization also needs a deliberate publication transition:
  G14/G15 source contexts include `Program.version`, which publication can change.
  New active-policy checks must distinguish an authorized publication transition
  with identical protected terms from changed evaluation rules. Retain the original
  artifact context; record the transition and revalidate binding/terms/authority.
  Do not rewrite old contexts or waive arbitrary version changes to make the first
  post-close calculation succeed. Add a pre-opening-to-post-close test to O1/O2.
- Include complete source context, assessment IDs and full-policy digests,
  normalization definitions/actual bounds, encoding versions, terms/binding,
  evaluation date/timezone and PA release-state IDs in the snapshot. Unknown old
  photo/direct-upload verification hashes remain unknown; current-byte hashes do
  not certify old verification. Unsupported sources remain blocked.

### 5.4 Proposed service APIs, permissions and audit

New internal service entry points (no routes/commands/UI in the first delivery):

```text
authorize_processing(program_id, user, exact_versions, expected_context, reason, confirmed)
request_recalculation(program_id, user, expected_context, request_key, reason, confirmed)
record_source_change(source_identity, source_version, initiating_audit, actor, reason)
process_request(request_id, executor, expected_generation)
current_result(program_id, user) / result_history(program_id, user)
```

The first method creates effective authorization only through the approved duties
and scope contract; test authorizations stay inside disposable databases. Code
development may proceed before real policy values are supplied if missing values
always block the operational path; no successful live configuration can be claimed.

Require `core.permissions.require_workspace_permissions` plus complete private
read permissions and new action codenames for authorize/revoke, request/retry,
execute and view operational history. Reuse `READINESS_VIEW` as a minimum basis,
then add new artifact permissions. Do not automatically assign them. Validate
program ownership on every supplied artifact/application. Current Django permissions
are model/action based; no inspected per-program assignment roster establishes an
institutional access allocation. Confirm whether all authorized officers have
global program scope or require explicit program grants before implementing scope.
Staff/superuser status cannot supply missing business-policy approval.

Check permission before private reads; recheck executing authority before promotion,
including revoked/inactive users and expired/withdrawn authorization. Reads never
create control rows or audit records; future HTTP reads must be private/no-store.
Raw inputs stay in protected artifacts, not generic audit notes/public payloads.

Every source change + durable request + existing source audit must commit atomically.
Every result graph + current pointer + promotion audit must commit atomically.
If required audit fails, rollback the corresponding mutation. Record technical
attempt failure separately after rollback only under deliberate transaction
ownership; if the database/audit store is unavailable, leave the durable request
pending for recovery and never fabricate a successful outcome. No private values
or credentials in failure logs.

### 5.5 Locking, freshness, repetition and recovery

Current writer evidence matters: G12/G15 use Terms → Program → Application → Member;
`members/services.py:15` and `documents/services.py:49` start at Member;
`assistance/services.py:34` takes Program/Application then Member and release/void
can change another program's PA dependency. Adding a second Program lock while
holding Member would create an inversion. Merely decorating every writer with an
extra transaction is insufficient.

Proposed capture/promotion order: Terms mutex → target Program/control → all its
application rows in deterministic PK order → distinct Member rows in PK order →
relevant assessments/control artifacts. Re-resolve after lock acquisition and
restart/reject if the candidate manifest changed. One program per transaction;
do not nest cross-program calculation while holding member locks.

Member/release writers append a source-scoped durable event while holding their
existing source locks; they do not synchronously update each target program's
control row. Avoid even incidental FK checks against unrelated Program parents
on that writer path. Resolve dependent programs afterward from all the member's
applications, including pending candidates; acknowledge handling per program only
with a completed/blocked attempt event. No global auto-increment high-water mark
alone proves transaction commit order. Use exact source versions/event identities
and current manifests. This design and actual MySQL FK/lock behavior require
independent-connection tests before acceptance.

Persist accepted capture/STARTED before calculation, release locks, calculate from
that immutable snapshot, then reacquire the same lock order for promotion.
Re-resolve the entire governed pool, source bytes/manifests, latest reviews,
authorization and evaluation date. Any changed input, new source event, expired
evidence or changed generation rejects promotion; old history remains intact.
Read-time currentness must independently recheck context/outstanding dependencies,
so a cached pointer cannot be consumed while an outbox event awaits handling.
Logical invalidation is immediate through source-version/currentness checks;
physical pointer clearing may occur in the target-program transaction.

Recommend content-bound request keys: same key/same content returns the retained
request; same key/different content rejects; same accepted context with a fresh
request appends an attempt/reuse event and reuses the one current result. Concurrent
workers cannot promote twice. Prior-generation completion never restores old
currentness. Distinct retry attempts are retained; no silent last-writer-wins.
These are proposed engineering semantics requiring approval, not an institutional
retry policy inferred from G17 fixtures.

A crash after capture leaves recoverable STARTED evidence; a retry creates a new
attempt referencing it and rechecks authority/context. Proposed minimum: one
explicit processing invocation at a time per program, guarded by generation and
unique-result constraints; no automatic timeout/lease takeover until its policy
is defined. Persisted requests allow later service-driven recovery without losing
source corrections. Initial tests call `process_request` directly. A production
worker/scheduler, service identity, automatic dispatch/retry/backoff and expiry
sweep require later runtime authorization. **Durable invalidation/request capture
alone is not the roadmap's automatic full-pool recalculation completion.**

### 5.6 File and integration scope for the next authorized task

| Proposed file/change | Concrete responsibility |
| --- | --- |
| `ewaf/operational_records.py`, `models.py`, new `migrations/0005_operational_ranking_history.py` | Six additive logical records, permissions/constraints, append-only guards; preserve all old rows/constraints |
| `ewaf/operational_policy.py`, `operational_inputs.py` | Strict approved bundle, current processing guard, complete admission/accepted-input resolver; no default production policy |
| `ewaf/recalculation_services.py` | Request/capture/replay/promote/history, durable source events, audit/invalidation/recovery. Model definitions remain in `models.py`; shared protected-record helpers live in `operational_records.py`, with no duplicate record module |
| `ewaf/calculation_core.py`, narrowly `weighted_scoring.py` and `ranking_diagnostics.py` | Extract reusable math; preserve public synthetic wrappers/pins/output and all prior safeguards via parity tests |
| `ewaf/evidence_services.py`, `configuration_services.py`, `scoring_services.py` | Atomically record dependency events for new findings/policies/drafts; no automatic draft authorization. Same-policy complete re-review may permit a new run |
| `members/services.py`, `documents/services.py`, `programs/workflow.py` | Source correction/status/document/photo invalidation with durable source event; existing evidence/audits/permissions retained |
| `assistance/services.py` | Eligibility/release/void dependency events only; leave `decide_assistance` and release ranking guards disabled for EWAF |
| `programs/services.py`, `binding_services.py`, `approval_services.py` | Detect submission/closure/publication/terms/binding/control changes; expose no revision bypass. Prepare disabled pre-opening EWAF authorization guard for later activation |
| `config/settings.py` | Proposed `EWAF_OPERATIONAL_BACKEND_ENABLED = False` rollout guard; tests explicitly override it. This switch never supplies policy/processing approval. No `.env`, deployed configuration or PDAO setting edits; enabling tests is not enabling runtime |
| New `ewaf/test_operational_policy.py`, `test_operational_inputs.py`, `test_recalculation_services.py`, `test_recalculation_concurrency.py`, `test_recalculation_migrations.py`; focused tests beside touched writers | Acceptance cases in section 6; fictional DB records use real services/permissions |

No first-slice changes to forms/views/URLs/templates/static/sidebar, no new generic
Admin edit routes, no G18 or announcement-consumer enablement. Preserve eight Admin
groups in `core/workspace.py`, onsite membership and verified-member applications.
Before activating intake guard, reconcile legacy EWAF programs and the active
configuration's pre-opening contract; do not silently retro-authorize them.
Default-off source hooks must return before querying the new tables or recording
new events, preserving existing application behavior before any future rollout.
G12/G15 readiness remains score-free; old EWAF services remain fail-closed until a
separate consumer integration is authorized. An existing preservation assertion
hardcoding migration leaf 0004 describes this checkpoint; future additive-schema
tests must explicitly extend that boundary without reducing historical immutability
or no-operational-authority assertions for synthetic APIs.

## 6. Acceptance tests required for that backend delivery

All future Django runs use `.\.venv\Scripts\python.exe scripts/g12_test_runner.py ...`
with `.env` disabled. These tests are **proposed, not executed or passed here**.

| ID | Required demonstration / acceptance criterion |
| --- | --- |
| O1 — authority | Real permissions before reads; anonymous/inactive/nonstaff/insufficient and wrong-program callers denied; documentary reference alone cannot activate; missing/invalid/unresolved policy blocked; authorization/revocation audited atomically; superuser cannot bypass business prerequisites |
| O2 — first full pool | Persist fictional Program/Application/Member/assessment/configuration graphs using existing services; server resolves all submissions, admission/exclusion reasons and one policy/cutoff; no caller subset; no pending/invalid member silently omitted; closed-window and unchanged-terms prerequisites; no decision/status mutation |
| O3 — mathematics | Independently worked nontrivial matrix/pool and corrections; full traces/both scales and exact ties; 50-digit near ties survive MySQL JSON roundtrip and reload; altered ambient context irrelevant; wrapper parity across every G16/G17 fixture; no classification/rank-number/selection inference |
| O4 — immutable graph | Original inputs/policies/results byte-equivalent after correction and new result; predecessor/program ownership; bulk update/delete/upsert and forged audits refused; detached nested JSON cannot mutate persisted history; digest tampering detected; legacy models/G12/G14/G15 unchanged |
| O5 — evidence/currentness | Latest missing/rejected/disputed/expired/revoked/B1/B2/B3 failures, source bytes unavailable, term/binding mismatch and source-version change block; expiry without write and midnight during run; zero distinct from missing; no old favorable fallback; unhandled event/read-time drift makes cached pointer unusable |
| O6 — actual source integration | Authorized member/document/photo correction and fresh reviews create durable event in source transaction; complete same-policy pool recalculates on processing request. Source or required-audit rollback leaves neither event nor partial source mutation. No-op/display changes do not manufacture a new policy/run |
| O7 — PA/dependencies | Release/void in program A invalidates every dependent program B/C for that member; unrelated members unaffected; source IDs match approved scope; no attendance/approval contribution. Unsupported PA scope blocks a run, not event retention. Never acquire B while holding A's member lock |
| O8 — real races | Independent MySQL connections: competing runs, member/document correction, new assessment/config proposal/binding, release/void, application/eligibility changes and time rollover between capture/promotion; one complete promotion only; stale generations fail; deterministic locks; no deadlock hidden by mocked simulation |
| O9 — repeated/failure/recovery | Same-key/content reuse, same-key/conflicting-content rejection, different-key/same-context distinct attempts; lost response/retry, crash after capture, rollback at result/audit/pointer steps, database unavailable failure recording, restart using durable request; no partial result becomes current |
| O10 — migration/compatibility | Disposable old-to-new migration preserves all historical graphs/constraints without backfill; new constraints reject cross-scope/invalid data through supported paths; no admin/UI route or default permission grant; rollout off rejects direct new entry calls before private reads/writes; PDAO flag unchanged |
| O11 — consumer boundary | Existing EWAF decision/release/publication guards still reject; no selection, waitlist, public numeric preview or automated authority. Later consumer tests must deliberately cover status transition/freshness rather than reinterpret ELIGIBLE-only diagnostics |
| O12 — regression/evidence | New focused + existing G16/G17 + G12/G14/G15 + affected source-writer tests and full suite, checks/drift/diff; actual commands/exits/counts/skips and source hashes; snapshot includes migration files. No count is a fixed target. Independent review before any rollout |

Set accepted pool/resource bounds and performance criteria before running larger
pool acceptance; none is measured by the 32-candidate synthetic fixture cap. Audit
rollback and multi-connection tests are mandatory for the backend, even with
fictional data. Browser acceptance waits for separately authorized UI changes.

## 7. Separate authorization ledger

| Authorization | Present task | Concrete scope to authorize next / later |
| --- | --- | --- |
| A. Edit application code | Not authorized | Explicit backend slice 5.1–5.6, extraction/parity, source-event integration and tests. Name excluded branches and preserve existing diagnostic contracts |
| B. Create migrations | Not authorized | Additive six-record schema/permissions/constraints, reviewed migration file; no historical backfill or legacy/G15 repurposing |
| C. Apply migrations in disposable tests | No application/test DB commands run here | Authorize new migration validation only through the fresh disposable runner; separate from B and from local operational MySQL |
| D. Change an operational database | Not authorized | Separate named environment, reviewed migration, backup/restore/rollback and data-preservation approval; even localhost application DB is operational for this boundary |
| E. Expose runtime/UI behavior | Not authorized | Separate activation of service entry points, pre-opening gates, private views/forms, processing executor/worker and new permission assignments after policy/backend acceptance; preserve eight-group design |
| F. Use real member/applicant data | Not authorized | Explicit data owner/privacy approval, scope/minimization/access/retention, environment and evidence procedure; passing fictional tests grants none |
| G. Deploy | Not authorized | Separate release approval for exact commit/migrations/configuration and environment with recovery/acceptance evidence |

A/B/C can be granted independently for the specified backend increment without
D/E/F/G. No permission to stage/commit/push follows from any of these. Real policy
authorization is a separate Association decision; technical permission to code
the enforcement mechanism does not make a proposed bundle institutionally approved.

## 8. Dependency order and Stage 8 / 80% acceptance checklist

1. Record synthetic G16 acceptance (pending) and, separately, G17 synthetic
   acceptance against the reviewed snapshot. Preserve implementation evidence.
2. Authorize backend A/B/C and its narrow engineering contract; establish exact
   policy schema, officer scope and fail-closed processing semantics. Build/test
   the actual persistence/input/authorization/promotion increment.
3. Resolve and record real program policies; implement effective authorization
   before opening. Complete G06-B2/B3 or explicitly authorize a narrow unchanged-
   terms processing path before any corresponding live operation. Reconcile legacy
   cases without inferred approval. Complete affected alternative-evidence paths
   when their policies apply.
4. Complete operational G16/G17: approved full-pool calculation, persisted replay,
   currentness, permitted policy revisions, automatic affected-pool recomputation,
   durable execution/retries/recovery and all source dependencies, including PA.
5. Only then separately implement G18 handoff: `require_ranked`,
   `decide_assistance`, release guards and current result references. Account for
   G12's ELIGIBLE-only/current pending-decision source contract; selection itself
   must not accidentally stale or recreate its originating calculation. Human
   eligibility/slots/approved tie policy remain independent prerequisites.
6. Integrate authorized EWAF publication at `announcements/results.py:32`, which
   currently rejects EWAF explicitly. Preserve private traces, public allowlist,
   source-freshness withholding and explicit reviewed publication revisions.

### Remaining evidence to close Stage 8 (not merely this backend slice)

- [ ] **Backend:** AT-11/12/13/14/30/31 approved definitions/judgments, correct
  arithmetic, locked-before-opening authorization, accepted inputs, full pool,
  lossless history and approved classification; not just synthetic matrix success.
- [ ] **Backend G17:** AT-15/16/22 real source/configuration integration, automatic
  full affected-pool recalculation, cross-program PA, atomic audits and all
  relevant stale/failed/concurrent/recovery cases under approved policy.
- [ ] **G18 integration:** AT-17/18 explicit reasoned officer decision, no automatic
  selection, concurrent slot enforcement, unchanged scores/ties, Not Selected vs
  Ineligible, approved tie/waitlist/exception boundaries and actual receipt/void.
  No G18 final acceptance is performed by this review.
- [ ] **Required private UI:** authorized configuration/approval and complete-pool
  result/history/recalculation review, readable current/stale/blocked status,
  protected actions with CSRF/expected version, keyboard/mobile/accessibility,
  least-privilege navigation within existing eight groups. A backend-only result
  does not prove that officers can complete the workflow.
- [ ] **Cross-stage consumers:** AT-19/22 safe EWAF result preparation/publication,
  freshness and traceability. Stage 9 publication remains separately scoped; its
  dependency cannot be counted as implemented from a stored ranking.
- [ ] **Acceptance:** owner/client signs exact Stage 8 scope, policy versions,
  backend/UI/UAT evidence and outstanding exceptions. Representative officer/PWD
  review, privacy/access assignments and required recovery evidence remain explicit.
  Broader Stage 10 readiness is not silently declared complete either.

Roadmap `../05 - Development/Development Roadmap.md:11,57` and
`../06 - Testing/Workflow Acceptance Tests.md:23–30,37,49–52` define these targets.
An intentionally deferred classification, alternative evidence, post-opening
revision or G18 path must remain an acceptance gap where required by that target.
No scope reduction in this proposal changes the owner's **70%** baseline or
the requirement for complete, tested, accepted Stage 8 to reach **80%**.

## 9. Proposed checkpoint commit inventories — do not execute

These are exact manifests, not staging commands. Preserve the existing index
until the owner explicitly requests checkpoint commits. No `git add .`, reset,
unstage or broad directory staging is proposed. Review source status again before
any future commit. Commit packaging does not record business acceptance.

### G16 checkpoint: 17 files

Suggested message: **Preserve validated synthetic G16 ranking diagnostics**.

The following 16 files are already staged, with these full blob IDs captured before
review and verified unchanged afterward:

| Existing staged file | Staged blob ID |
| --- | --- |
| `docs/g16-ranking-diagnostics-validation-2026-10-14.md` | `229f0cccee042b0305a97f73e3d382ab80837725` |
| `ewaf/ranking_diagnostics.py` | `32781970f739ba3b275ca5f3ab673a182bdeae09` |
| `ewaf/ranking_fixtures.py` | `061f333d98614f0b6707ed0f8cb145bad7feaae5` |
| `ewaf/ranking_policy.py` | `1d3242791d727c76e1d5329ba9fb59de3d15c367` |
| `ewaf/ranking_readiness.py` | `16b41db7e7ba044494286ac97a5633b4f38818f2` |
| `ewaf/ranking_testsupport.py` | `fd055b931ecb647cce2168db70c980adda0a7a28` |
| `ewaf/test_ranking_diagnostics.py` | `95afee13e0a9c2d8e4f6e1eaa29370e71517c544` |
| `ewaf/test_ranking_policy.py` | `aec1738725b69d2bc6368d575e11a9640fe16cc0` |
| `ewaf/test_ranking_preservation.py` | `d81ce01e3c3b95114dae9528366819341219d1b7` |
| `ewaf/test_ranking_readiness.py` | `cae270a5b6f9c7762da7ca387d28480e70eeb488` |
| `ewaf/tests_data/g16/README.md` | `cb045657cb23d258fc9469319676350f7cbff540` |
| `ewaf/tests_data/g16/high-first-v1.json` | `a392e0a2ce42e5c5a7f6786ffd6f45ad5e00499f` |
| `ewaf/tests_data/g16/incomplete-v1.json` | `e3e817b1aa2a3ad8e2069e08084927fd985ba394` |
| `ewaf/tests_data/g16/low-first-v1.json` | `f5761ea414bc4928d5e82fca10e0c1eb362113fc` |
| `ewaf/tests_data/g16/precision-v1.json` | `de32f13dc21c5a39cdd0e0a8f98f87ad31bfa567` |
| `scripts/g16_synthetic_diagnostics.py` | `0aa5ade13f5c58188b92a4152d8fedbaa795c169` |

Add to that proposed checkpoint only:

```text
docs/g16-revalidation-2026-10-15.md
```

The October 14 report belongs with its G16 implementation; the October 15
revalidation records environment recovery/fresh G16/regression evidence and belongs
in the same checkpoint. It is currently untracked, not part of the existing index.

### G17 checkpoint: 20 files

Suggested message: **Add isolated G17 recalculation history simulation**.

```text
docs/g17-recalculation-history-plan-2026-10-15.md
docs/g17-recalculation-history-validation-2026-10-15.md
ewaf/recalculation_diagnostics.py
ewaf/recalculation_fixtures.py
ewaf/test_recalculation_diagnostics.py
ewaf/test_recalculation_preservation.py
ewaf/tests_data/g17/README.md
ewaf/tests_data/g17/history-v1.json
ewaf/tests_data/g17/incomplete-v1.json
ewaf/tests_data/g17/pool-base-v1.json
ewaf/tests_data/g17/pool-configuration-v2.json
ewaf/tests_data/g17/pool-corrected-v2.json
ewaf/tests_data/g17/pool-incomplete-v2.json
ewaf/tests_data/g17/pool-precision-v1.json
ewaf/tests_data/g17/precision-v1.json
ewaf/tests_data/g17/repeat-v1.json
ewaf/tests_data/g17/stale-v1.json
ewaf/tests_data/g17/unauthorized-v1.json
ewaf/tests_data/g17/unresolved-v1.json
scripts/g17_synthetic_diagnostics.py
```

The G17 plan is a pre-existing planning checkpoint, included here for provenance;
its planning-only statements are historical and were superseded only for the
bounded simulation by the later implementation instruction. Its future operational
proposals remain proposals. The G17 validation report belongs with the 19-file
implementation set. These 20 files are all currently untracked/outside the index.

Keep this new review document separate from both validated implementation packages:
`docs/stage8-operational-authorization-review-2026-10-15.md`.
Optional later documentation-only commit message: **Document Stage 8 operational authorization boundaries**.
No `.local/` logs/helpers, `.env`, credentials or private uploads belong in any
checkpoint. Retain local evidence securely; do not imply that uncommitted ignored
logs are automatically available to a future reviewer from Git alone.

## 10. Preservation and concrete decisions for the next task

Final read-only comparison: all 503 original file hashes, branch, HEAD and the
16-entry staged raw manifest remain unchanged. Only this document was added,
unstaged. `git diff --check`, `git diff --cached --check` and tracked
`git diff --exit-code` return 0; this untracked document is checked separately for
trailing whitespace/conflict markers. No source/fixture/test/checkpoint document,
production configuration, credential or database was changed; no staging, commit,
push, merge or deployment occurred.

Decisions needed before issuing the next implementation instruction:

1. **Owner acceptance:** record accept / return-for-correction separately for G16
   synthetic scope and G17 synthetic scope, identifying this snapshot. Neither
   decision accepts operational EWAF or Stage 8.
2. **Backend scope:** authorize or revise the first complete closed-pool/same-policy
   correction slice, its six additive logical records, source outbox and the
   narrow shared-math extraction. Confirm default-disabled service-only delivery,
   no G18/UI/worker activation, and whether A, B and C are each granted.
3. **Engineering contract:** decide officer program scope, distinct authorize vs
   execute permissions/separation, lossless Decimal text storage, exact-context
   reuse/conflicting-key rejection, generation rechecks, whole-pool size limit,
   and explicit recovery without an automatic lease/timeout default.
4. **Policy ownership and first program:** identify the Association signatory and
   supply/commission the exact SI/ES/ND/PR evidence and encodings, PA scope/cutoff/
   direction, SI direction, AHP judgments, fixed bounds and complete admission
   rules. Development may enforce missing-policy blocks before those values arrive;
   they are required before any claim of a usable live run.
5. **Governance boundary:** choose full G06-B2/B3 completion first, or commission
   an expressly approved unchanged-terms/pre-decision processing contract that
   blocks every revision/resumption/final-case path. There is no existing permission
   to bypass that prerequisite. Keep post-opening config/pool changes blocked until
   their separate revision policies are recorded.

Waitlist, exception, classification, alternative-identity and expanded-publication
decisions may remain deferred for the bounded backend task, with their affected
paths explicitly unavailable and their Stage 8 acceptance gaps retained. D/E/F/G
remain separate later authorizations. **No blanket approval is requested or inferred.**
