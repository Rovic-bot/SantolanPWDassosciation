# Stage 8 durable calculation schema proposal

Date: October 16, 2026. **Proposal only; no models or migration files created.**

This accompanies the authorized non-schema fallback documented in [the increment report](stage8-pool-backend-validation-2026-10-16.md). It refines [the October 15 proposal](stage8-operational-authorization-review-2026-10-15.md), without treating that proposal as approval. Recorded progress remains 70%; live scoring, G18 and publication remain disabled.

## Authorization boundary

The current user instruction permits application-code development/testing but requires a recorded explicit authorization for new additive migrations and their application to disposable test databases. No record covering this new durable increment was identified in the decisions, current G12–G17 validation/proposals, development notes or relevant local Markdown/text records. The October 15 authorization ledger lists both migration creation and disposable application as not authorized in that earlier review. Older G12/G14/G15 schema work is not an authorization for these additional records.

Accordingly, no registered model, permission, migration, table, data backfill, source outbox hook or durable result was introduced. Existing migrations run only as part of the current instruction's authorized isolated regression tests. No application-database migration is proposed here.

## Proposed additive records

Names are proposed, not registered models. Eight logical records make individual application ownership and criterion traces explicit rather than using G15 readiness storage or the legacy ranking tables.

| Record | Purpose and principal fields |
| --- | --- |
| `ProcessingAuthorization` | Immutable program-scoped revision/predecessor, exact evidence policy/configuration/AHP validation/scoring proposal IDs and digests, approved rule snapshot, terms/binding context, authority identity/reference, effective period, actor/reason, protected audit. Institutional authority must be checked separately from Django permissions. Withdrawal/replacement is a new event/version. |
| `ProgramCalculationControl` | One row per program, generation, active authorization reference and current-run reference. Mutated only by guarded services; does not reuse the PDAO setting or infer currentness solely from `Program.version`. |
| `RecalculationRequest` | Immutable source/request identity, content-bound request key, source version/digest, initiator/reason and required audit. Can represent a source-scoped outbox event before affected programs are resolved. Do not force a member/release writer to acquire unrelated Program FK locks. |
| `RecalculationAttempt` | Immutable request/program/authorization relationship, captured generation, predecessor run, full retained-submission accounting and admission manifest, accepted-source snapshot, engine/profile, evaluation date/timezone/UTC instant, actor and audit. Terminal outcomes are appended events. |
| `EvaluationRun` | Immutable successful run sequence, attempt, predecessor, program, authorization, complete pool and result manifests/digests, engine/profile and numerical settings. One run is accepted only with its whole result graph and promotion audit. |
| `ApplicationResult` | Protected run/application relationship, canonical EWS on both scales, accepted-input provenance, per-criterion trace manifest, exact tie-group identity/position interval where approved. No inferred integer rank, classification, selection or waitlist. |
| `CriterionTrace` | One trace per result/criterion: exact assessment/source/policy identities/digests, raw accepted value and unit, encoding snapshot, fixed bounds/direction, AHP weight provenance, normalized value and contribution. Private, retained for reproducibility. |
| `RecalculationEvent` | Append-only started/blocked/failed/stale/completed/reused/promoted/invalidated outcome, request/attempt/run/program/generation references, executor/reason and mandatory protected audit. Tracks each dependent program's handling of source requests. |

Proposed integrity requirements:

- `PROTECT` on relevant program/application/source/history/audit foreign keys; no automatic deletion of history.
- Unique program/revision and program/run sequence; unique run/application; unique result/criterion; exact-context/idempotency uniqueness with deliberate MySQL concurrency tests.
- Cross-program and predecessor-chain validation in services plus model/queryset guards. A predecessor must belong to the same program, exist earlier in the chain, and represent the permitted predecessor relationship.
- Store calculated numbers as canonical decimal strings using the existing 50-digit numerical profile, without float conversion, SQL lexical ranking or legacy `Decimal(24,20)` narrowing. Rank/group using the shared Decimal engine.
- Application update/delete/bulk paths deny historical edits. Record later invalidation/supersession separately. These controls do not claim protection against privileged direct SQL.
- An empty/missing trace, omitted candidate, incorrect ownership, replay mismatch or required audit failure rolls back the entire successful result graph.
- New action permissions remain unassigned. No generic Admin editing of result/history records.

The eventual migration would follow `ewaf.0004_scoring_diagnostics`, use additive operations only, and contain no seed policy, inferred verification, permission assignment or historical backfill. Creation and disposable validation await explicit authorization for this increment.

## Operational capture and calculation contract still to implement

1. Check technical permission, program scope and effective institutional authorization before private source consumption. A feature flag, superuser, consistent AHP or PDAO approval cannot supply missing authority.
2. Resolve the explicit evaluation/admission/cutoff policy. Inventory all retained submissions; classify in-scope/out-of-scope and eligibility outcomes with approved reasons. Pending cases cannot silently disappear. No submitted application subset, pagination or slot limit may define a whole pool.
3. Acquire the reviewed deterministic lock order, resolve current G12 sources and exact effective G14/G15 context, and capture all candidates. Any eligible application with missing/stale/disputed evidence blocks a usable complete result.
4. Save the immutable attempt and source manifest. Extract shared mathematics narrowly from the existing engines if necessary, preserving G15/G16/G17 outputs and fixture checksums. Do not relabel real applicants as synthetic to use their public fixture APIs.
5. Reacquire the lock order, re-resolve the complete pool, authority, sources, date and generation. A changed context blocks promotion. Commit run/results/traces/current-pointer/promotion audit atomically.
6. Recheck currentness at every future consumer. A pending source event, expired evidence or changed source prevents use even before physical pointer clearing. G18 consumers remain disabled in this increment.

Current G14/G15 draft contexts include program version. The first real authorization contract must explicitly handle pre-opening approval through publication and post-close evaluation without rewriting old contexts or silently tolerating arbitrary term/version changes.

## Locking and writer analysis

Inspected current sources:

| Writer | Existing lock boundary | Durable extension requirement |
| --- | --- | --- |
| G12 evidence and G14/G15 configuration/proposals | Terms mutex, Program; application capture additionally Application then Member | Append source-scoped request atomically with existing artifact/audit. A new proposal is not automatically effective. |
| Member profile/status | Member first | Preserve order; no synchronous traversal acquiring other Program locks while Member is held. |
| Document verification | Member, then protected document/review work | Record invalidation in the same source transaction; retain review provenance and audit rollback. |
| Program submission | Terms, Program, Member and application creation | Detect entering pool, granted verification/version and closed-intake/cutoff conditions. Do not infer admission from submission alone. |
| Photo/eligibility/corrections | Program, Application, Member and relevant review/case rows | Include current-photo identity, required evidence, eligibility/audit/source versions, not only status. |
| Assistance release/void | Program/Application, Member, affected release | PA can affect another program. Record source event under existing locks, resolve dependent programs later. Do not synchronously acquire a second Program lock. |
| Protected terms/approval bindings | Terms mutex then Program/control | Preserve frozen terms and G06-B2/B3 barriers. No narrow-contract exemption is silently approved. |

Proposed capture/promotion order remains Terms mutex → target Program/control → all relevant applications in deterministic PK order → distinct members in PK order → evidence/configuration dependencies. Re-resolve membership after locks. This requires real MySQL tests, including foreign-key locks, uncommitted events, empty-to-nonempty dependencies and admission changes. A global auto-increment high-water mark is not proof of commit order.

The delivered non-schema readiness service intentionally adds **no locks or source hooks**. It compares two autocommit observations, refuses an outer transaction and returns no stable diagnostic token when observations differ. This detects tested committed changes but cannot prevent a later write or a changed-then-restored (ABA) context. It is never a promotion or current-result mechanism.

## Retry, interruption and audit contract still pending

Proposed technical behavior is exact-content idempotency: same key/content reuses the request; conflicting content rejects. Every attempt is retained. A successful context can be reused only after full current-source and authority rechecks, with a recorded reuse event. Concurrent attempts must not produce duplicate successful effects.

Crash recovery requires a durable STARTED attempt and an explicit retry, with current authority and complete-source revalidation. No timeout/lease/takeover or institutional repeat-evaluation rule is invented. After a required audit/storage failure, no completed current run may appear. Old runs remain historical and must not become current merely because replacement failed. Automatic workers/schedulers are excluded.

## Decisions and acceptance still required

- Schema creation and disposable application authorization for these new records.
- Institutionally approved income basis/period, employment encoding, dependent definition, relevance rubric, PA scope/window/cutoff/direction, all directions/bounds and source evidence rules.
- Admission/cutoff, authority/effectiveness, officer program scope, corrections/repeat rules, and protected-terms processing dependency (G06-B2/B3 or an expressly authorized narrower contract).
- Classification and business tie handling remain separate decisions; no defaults from fixtures.
- Dedicated tests for additive migrations and preservation, accepted-input calculation, Decimal storage/replay, predecessor integrity, graph/audit rollback, exact-context retries, real concurrent promotion, interruption recovery and read-time currentness.

The new readiness tests and existing synthetic simulations do **not** satisfy those durable acceptance requirements. No permanent history, accepted operational run, G18 acceptance or 80% milestone is claimed.
