# G17 — Recalculation and history implementation plan

Date: 2026-10-15 (Asia/Manila). Branch: `feature/events`.
Reviewed baseline HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`, with the
16 pre-existing staged G16 files preserved.

**Planning only. Baseline remains 70%. G17 and G18 remain pending.**
The 80% milestone requires complete, tested and accepted Stage 8 EWAF work.
This document does not authorize runtime code, migrations, new permissions,
persisted runs, UI, background jobs or operational activation.

## Authority and current repository contracts

Read with `../../CURRENT_SYSTEM_SPECIFICATION.md`, `../../Guide for Development.md`,
`../../05 - Development/Development Roadmap.md`, `API and Workflow Contracts.md`
in that same directory, and `../../00 - Project Overview/Open Decisions.md`.
The October 10 implementation-impact note describes its dated boundary; later
scoped repository validation documents establish the retained implementation.
See [G12](g12-verified-evidence-validation-2026-10-13.md),
[G14](g14-configuration-foundation-validation-2026-10-13.md),
[G15](g15-scoring-diagnostics-validation-2026-10-13.md),
[G16](g16-ranking-diagnostics-validation-2026-10-14.md) and the
[fresh G16 revalidation](g16-revalidation-2026-10-15.md).
G17 maps to the implementation-gap analysis G17 and AT-15/16/22.

| Current implementation | Consequence for G17 |
| --- | --- |
| `ewaf/evidence.py`, `evidence_rules.py`, `readiness.py`, `evidence_services.py` retain source manifests, latest criterion findings and B1/B2/B3 checks | Reuse provenance semantics; a recorded VERIFIED finding or historical readiness snapshot is not operational approval. |
| `configuration_services.py`, `configuration_records.py`, `ahp_validation.py` retain drafts, validation, review and non-effective authorization evidence | A complete draft and passing AHP diagnostic cannot activate a configuration. |
| `scoring_inputs.py:evidence_token`, `evaluate_application`, `validate_readiness_payload` | Retain score-free applicant output, evaluation date/timezone and current source checks. |
| `CalculationDiagnosticRun` and related G15 items/traces | Keep the database `READINESS_ONLY` constraint, one-application graph and private score-free history. Do not repurpose these tables for numerical runs. |
| `ranking_diagnostics.py:compare_fixture` and `ranking_readiness.py` | The public numerical entry accepts four pinned synthetic fixture names only. Real readiness stays separate and operational ranking always rejects. |
| Historical `Configuration`, `ApplicationInput`, `RankingRun`, `Snapshot`; `ewaf/services.py` | Preserve old rows and disabled mutation/current-ranking entry points. Their presence does not establish a usable current run. |
| `programs/terms.py:terms_lock` and protected-term guards | Existing terms are frozen. G17 cannot relax submitted/published-program restrictions or substitute for G06-B2/B3. |
| `assistance/services.py` and `announcements/results.py` | Human decisions/releases and explicit publication remain distinct. EWAF decisions and publication remain blocked. |

## Changes that can cause reassessment or recalculation

These are target trigger categories, conditional on approved operational policy
and separately authorized integration. **No live recalculation is permitted by
the current implementation.** A change first invalidates dependent currentness;
only a complete, authorized and reviewed replacement input set may be calculated.

| Change | Existing source/owner | Required treatment |
| --- | --- | --- |
| Authorized new configuration, judgments, scoring/evidence policy or normalization version | G12/G14/G15 revision records | Retain the old version; require effective authorization, scope and effective time. Recompute the entire affected program pool. Recording a proposal alone never qualifies. |
| Verified correction to income, employment, dependents or relevance evidence | `members/services.py`, `ewaf/evidence_services.py`, required document/rubric reviews | Retain before/after and source actor/reason; require fresh latest assessments and eligibility as applicable before using the changed input. No direct score edit. |
| Document replacement, verification/revocation, photo correction, expiry or dispute | `documents/services.py`, `programs/workflow.py`, G12 findings | Invalidate dependencies immediately; stale, rejected, disputed or incomplete evidence blocks a usable replacement result until required review completes. Expiry must be detected even without a write. |
| Eligibility, membership validity or candidate-pool change | `assistance/services.py`, `members/services.py`, `programs/services.py` | Rebuild the complete pool under an approved admission/cutoff policy. Do not silently omit a difficult applicant or turn missing evidence into ineligibility. |
| Confirmed actual release or retained void/correction | `assistance/services.py:record_release`, `void_release` | Determine every dependent program for that member under the approved PA scope/window/cutoff. Reassess PA and recompute each full affected pool; never count attendance, application or undelivered selection. |
| Approval binding, terms or external authority change | `programs/terms.py`, approval records/control | Block consumption and require the future G06-B2/B3 suspension/reassessment/resumption contract. A recorded offline PDAO decision does not authorize EWAF. |
| Approved evaluation-date/window rollover | G12/G15 evaluation-date and expiry semantics | Recheck expiry and PA cutoff; record the new evaluation context. Do not silently adopt a new window or cutoff. |

Display formatting, public CMS edits and retries with identical accepted context
do not justify new numerical policy or arbitrary reranking. An approved engine
revision would be a new replay version and governed recalculation, not a silent
change to existing engines. Post-selection/publication changes retain old
decisions and publications and require an approved review policy (OQ-09/15);
G17 must not reopen cases, revoke a beneficiary decision or republish automatically.

## Proposed result and history contract

Future operational storage needs an additive, reviewed schema. Suggested logical
artifacts are a recalculation request, immutable attempt/result graph, source and
pool manifest, and a separate current-result pointer/promotion event. Names and
fields are proposals, not models to create in this task.

Each attempt must identify:

- Program, predecessor/result superseded, initiating source event and its before/
  after references, reason, requesting actor and system execution identity/times.
- Exact evidence-policy, configuration, AHP validation, scoring, normalization,
  classification (only if approved), admission/cutoff and ranking/tie policy
  versions, with identities, content digests and effective authorization evidence.
- Program/terms/binding/control versions; complete candidate and exclusion
  manifest with governed reasons; member/application/eligibility review versions;
  latest criterion assessment IDs and digests, including rejected findings.
- Private raw accepted values, encoding, units, source reviews and hashes,
  observation/expiry dates, PA release IDs/state/scope/cutoff, normalized values,
  actual bounds, full weights and per-criterion contributions. Do not copy private
  file contents or identifying profile fields into general audit logs.
- Schema, engine/profile, criterion order, precision/rounding/exponent/trap
  settings, evaluation UTC timestamp, local date/timezone and source watermark.
- Both score scales, exact equal-score groups and, only after policy approval,
  rank-number conventions/classification; complete manifest and result digests.
  Rank/score never implies selection, waitlisting or actual release.

Preserve all old rules, inputs, runs, traces, decisions, releases and publication
revisions byte-for-byte in their existing representations. Append successors and
supersession events; never overwrite a historical result or backfill missing
authority. Unknown historical provenance stays unknown. Retain engine versions
needed to replay their results. Digests establish content consistency, not approval
or proof against privileged database modification.

Preserve G14/G15's explicit 50-digit `ROUND_HALF_EVEN` calculation profile and
G16's direct Decimal comparison. No float conversion, negated sort keys, epsilon,
display rounding or ID/submission/reference tie-breaker. The synthetic
`SI, ES, PA, ND, PR` order remains pinned; source documents' different display
order must not silently change replay. Any institutional precision or ordering
revision requires explicit versioning and approval.

## Proposed execution, stale evidence and failure behavior

1. A permitted source change commits its normal retained history and mandatory
   audit. Future durable invalidation/request recording must commit atomically
   with that change; a process-local callback alone cannot guarantee recovery.
   Design transaction ownership and failure behavior before integrating writers.
2. Resolve affected programs server-side from recorded dependencies, including PA
   effects across programs. A client cannot submit a favored applicant subset.
   Capture the entire governed pool, exact accepted input context and evaluation
   date. Missing admission/exclusion policy blocks the attempt.
3. If any required source is incomplete, stale, disputed, rejected, expired,
   corrupt or unapproved, retain a blocked attempt and reasons. Do not fall back
   to an older favorable assessment, impute values, clip bounds, renormalize a
   partial vector, or publish a successful subset. Human review resolves evidence;
   the calculation service does not manufacture it.
4. Calculate against the immutable accepted snapshot using preserved engines.
   Fixed versus pool-derived bounds must be explicit policy. Pool-derived bounds
   are not implemented by current G15 and need their own authorized work.
5. Before promotion, re-resolve the full pool, authorization, latest versions,
   source digests and evaluation-date validity under compatible locks. A source
   change or expiry during execution makes the attempt stale; retain its evidence
   and arrange a governed retry. No older completed attempt may replace a newer
   current generation.
6. Promote only a complete, internally consistent, still-current result graph in
   one transaction with its matching promotion audit. Keep the previous result
   accessible as history. A stale previous pointer is not usable while a new
   attempt fails or awaits review; consumers must verify currentness themselves.
7. Deduplicate work using program + accepted context/pool + policy/engine/evaluation
   identity. Retain distinct retry attempts and outcomes; retries cannot create
   duplicate current promotions. Recover interrupted work without deleting history.

Current locks are Terms mutex → Program → Application → Member → relevant
assessment rows. G14 program-only work stops before applicant locks. G15 captures
one application; it does not establish a multi-application snapshot contract.
Before implementing a pool transaction, inspect every competing writer and
define deterministic ordering for all applications/members. Do not acquire a
second program lock after a member lock. Cross-program PA invalidation should
record dependencies for later per-program work rather than nest reverse locks.
Test with actual independent MySQL connections, not mocked concurrency. The
durable queue/outbox, worker identity, retries, crash recovery and locking changes
require separate schema/operational review; none is enabled here.

Retain inclusive expiry semantics (`expires_on < localdate()` means expired).
Read-time and pre-promotion expiry checks are necessary even if a future scheduler
is added. Historical photo/direct-upload records lack verification-time hashes;
observed current hashes cannot retroactively certify their original bytes.

## Permissions and audit

Reuse `core.permissions.require_workspace_permissions` and the complete private
read sets in `ewaf/scoring_inputs.py:READINESS_VIEW`; program-only readers must not
gain applicant evidence. Future operational request/retry, policy authorization,
history access and human selection need separately reviewed action permissions
and assignments. Active authenticated staff/dashboard access alone is insufficient.
No new role, permission grant or superuser business-policy override is implied.

New mutations, if later authorized, need service-level ownership/permission
checks, reason, expected context and confirmation; browser mutations additionally
need CSRF. Private reads must remain read-only and no-store. An automated worker
must retain the initiating authority and recheck its governed execution scope;
it cannot invent an officer approval.

Follow G12/G14/G15 protected artifact/`ProgramLog` association patterns: server
actor/time/digest, program/application linkage, mandatory neutral audit metadata,
private detailed reasons, atomic writes and supported-path append-only guards.
Audit source invalidation, blocked/started/completed/failed/stale/retried attempts
and promotion separately. Preserve failure evidence through a deliberate separate
failure-record transaction after a rolled-back result transaction, without
retaining partially usable results. Reads must not create logs or control rows.

## Proposed files and development increments

All paths below are **future proposals**, not files added by this planning task.

| Increment | Proposed files or integration points | Boundary |
| --- | --- | --- |
| G17-A: isolated simulation, first recommended implementation scope | `ewaf/recalculation_diagnostics.py`, `recalculation_fixtures.py`, `tests_data/g17/`, `scripts/g17_synthetic_diagnostics.py` | Pinned invented fixtures and pure in-memory event/history simulation; no ORM/settings, arbitrary upload/path, real IDs, saved run, route or worker. |
| G17-A tests | `ewaf/test_recalculation_diagnostics.py`, `test_recalculation_preservation.py` | Synthetic transition/replay checks; existing disabled gates and source/index preservation. Disposable DB only if testing existing barriers. |
| Later persistence, separately authorized | `ewaf/recalculation_records.py`, `recalculation_services.py`, additive models/migrations after schema review | Immutable graph, request/attempt history, current pointer, idempotency and atomic audit; never alter G15 READINESS_ONLY or backfill legacy results. |
| Later integration, separately authorized | `ewaf/evidence_services.py`, configuration/scoring services; `members/services.py`, `documents/services.py`, `programs/workflow.py`, `programs/services.py`, `programs/terms.py`, `assistance/services.py` | Governed invalidation triggers and accepted-input consumption; preserve existing lock/approval boundaries. |
| Later consumers, coordinated with G18 and publication work | `assistance/services.py`, `announcements/results.py`, `ewaf/services.py` | Explicit currentness checks before separate human selection/publication; do not simply remove disabled guards. |
| Later integration tests | `ewaf/test_recalculation_services.py`, `test_recalculation_concurrency.py`, `test_recalculation_migrations.py`; affected assistance/program/publication tests | Database-backed acceptance, privacy, permission, audit rollback, races and historical preservation. |
| Optional later private history interface | Separate approved views/forms/routes/templates using existing Admin design | Retain the minimalist light eight-group portal; no new UI in G17-A. |

G17-A can demonstrate changed-input versus unchanged-input invalidation, full-pool
replay, immutable predecessors, failure/stale attempts, retry deduplication and
simulated promotion. Use copied versioned fixtures and a new G17 digest namespace;
do not edit G16 pins or broaden `compare_fixture`. All output retains diagnostic
labels and false operational/effective-authorization flags. A simulated accepted
state cannot be a production acceptance token. This work is suitable for a later
bounded implementation request; **only this plan is authorized now**.

## Acceptance criteria for later work

1. Independent hand-worked fixtures reproduce every contribution and both score
   scales; true ties remain tied and near ties remain distinct at working precision.
2. Changed accepted input/policy/pool causes full affected-pool recalculation;
   unchanged-context retries are idempotent. Cross-program PA dependencies are
   covered, with unrelated programs unaffected and attendance excluded.
3. Latest rejected/disputed/unverified findings, B1/B2/B3 failures, missing values,
   expiry/date rollover and stale terms/binding/authorization block usable output.
   Zero remains distinct from missing; no favored subset, clipping or imputation.
4. Old source/rule/result/selection/release/publication rows remain identical;
   complete artifacts replay using their own versions. No inferred backfill.
5. Concurrent corrections, policy changes, release/void transactions and competing
   runs cannot promote stale results. Audit failures roll back mutations; crashes
   and retries preserve failure history and never produce partial current results.
6. Unauthorized and cross-program calls fail before private disclosure. A complete
   calculation selects nobody. Stale results cannot authorize selection/publication;
   human reasoned decisions, slots and actual release remain separate.
7. Synthetic scope has no new schema, UI, operational imports/writes or effective
   permissions. Later persistence requires additive migration preservation tests
   on disposable MySQL and explicit authorization before any operational rollout.
8. Record actual focused/full test commands, counts/skips/failures, system checks,
   drift and whitespace results using the verified virtual environment and isolated
   runner. Browser tests apply only to separately approved UI changes.

## Approval-dependent boundaries and milestone gate

Resolve applicable OQ-06/07/08/18/19/23 (measurements, encodings, PA, directions and
evidence), OQ-09/26 plus G06-B2/B3 (authorization, revision, external approval,
suspension/resumption), OQ-10/11/12 (AHP, bounds and numerical policy), OQ-13/15
(ties, waitlists and exceptions), OQ-25 (classification), and OQ-16/22 (access,
retention/disclosure). Conditional identity evidence remains OQ-02/24.
No pending rule becomes approved through a documentary reference or passing test.

Separate authorization is needed for numerical applicant inputs, operational
configuration activation, ranking persistence, migrations, triggers/queues/workers,
current-result promotion, new permissions/UI and G18 selection/publication
integration. No new default policy, automatic beneficiary decision, public ranking,
government integration or operational database change is part of this plan.

G16 synthetic validation and G17 planning advance preparation only. Keep **70%**
until all required Stage 8 behavior is implemented, tested and accepted; G17/G18
and the policy/governance dependencies remain outstanding.
