# G18-B Gate 2 proposal: durable invalidation and atomic promotion

**PROPOSAL ONLY. No Gate 2 code or migrations are authorized or implemented.**
Accepted milestone: **70%**. This proposal follows the [Gate 1 inventory](g18-b-gate1-source-coverage-2026-10-18.md).
Approval of this design would not approve four-criterion weights, evidence rules,
live scoring, ranking, selection, publication, or PDAO enforcement changes.

## Problem and proposed durable records

Gate 1 records repeated source observations and commits an all-or-nothing
historical calculation graph. Some sources lack a shared writer lock or revision.
Equal observations therefore cannot prove that no intervening change happened.

Subject to separate schema review, introduce additive records, leaving every old
table, migration, artifact digest and numerical engine intact:

| Proposed record | Required content and invariant |
|---|---|
| ProgramSourceState | Unique program FK, monotonic generation, current development-run pointer, pointer generation; version/CAS field. Initially no current pointer. Generation never reset/reused, including value restoration. |
| SourceInvalidation | Append-only event ID, transaction/batch correlation, source kind + stable source ID, affected program, before/after generation, reason code, actor or system actor, source audit FK/reference, occurrence time. Unique `(program, resulting generation)`; no raw medical evidence, income, document bytes or file paths in general audit. |
| RunSourceBinding | Immutable unique run association, source generation, dependency-envelope version, ordered complete inventory digest, exact config/policy/engine IDs, authority generation, expiry boundary. Legacy runs have no binding and are historical only. |
| PromotionEvent | Append-only candidate/previous pointer, expected/accepted generation, graph/manifest digest and actor. Pointer transition and audit are in the same transaction. Failed attempts cannot restore an older pointer. |
| AuthoritySourceState (if separated) | Monotonic processing-authority generation for user/group changes, referenced by requests/runs. Alternatively fan out into all affected ProgramSourceState rows under the same lock. Choose one scheme before migration design; do not combine unfenced alternatives. |

Exact model/column names and migration ordering require review. No backfill may
declare a historical run current. Existing records must replay without using
new tables. New schema defaults must be fail-closed, not authorization defaults.

## Proposed shared lock contract

Use the existing installation-wide Terms mutex as the first migration-stage fence
for **every participating source writer**, including admin saves/M2M changes and
future imports. Do not introduce a second independent mutex with competing order.

Proposed order within one transaction:

1. Terms mutex T (before any source row or program lock).
2. Resolve affected scope under T; lock Programs ascending PK and each associated
   ProgramSourceState in that same order. Scope resolution and generation creation
   must be inside the fence; an application added concurrently cannot be missed.
3. Lock affected Applications ascending PK, then distinct Members ascending PK.
4. Lock remaining source rows in a reviewed fixed order: intake, eligibility status,
   approval control, configuration/evidence revisions, document/review/photo rows,
   assistance receipt, auth/group/M2M rows as applicable. Preserve existing local
   prerequisites; document any necessary order adjustment in its writer tests.
5. Write source mutation + its existing audit + invalidation(s) + generation
   increment; clear the matching current pointer and append its invalidation audit.
   Commit all of these together. No on-commit-only invalidation and no best-effort
   signal outside the source transaction.

The initial global T fence sacrifices concurrency to avoid cross-program cycles.
Existing non-T writers currently lock P/A/M first; they MUST acquire T at entry,
not after taking those locks. Simply calling an invalidation helper at the end
would invert the order and is unacceptable. Read-only diagnostics may remain
unlocked if they explicitly make no current-result claim. Any future partitioning
of T is a separate design/test change, not an optimization assumed here.

## Precise integration list (requires separate authorization)

| Existing entry point / boundary | Required integration and affected programs |
|---|---|
| `members.services.update_member`, `change_status` | Acquire T first; resolve every program with applications for member; audit/increment/clear in same transaction, including archive/restore ABA. |
| `membership.services.submit_application`, `record_verification`, `decide_application` | Preserve pending-only/manual PRPWD rules. Add fence for prospective membership dependencies; member creation/program application creation must register scope before a run can reference it. No new approved-intake reversal flow. |
| `documents.services.verify_document` | T before current M lock; fan out across all member programs (supporting and reused evidence), append review + existing MemberEvent + invalidation atomically. |
| `programs.services.submit_application`, `change_application` | Submission already has T; status writer must join T before P/A. Inventory generation changes for every retained row, not only eligible or before cutoff. |
| `programs.workflow.review_photo`, `correct_application`, photo/document storage helpers | T before P/A/M; increment generation alongside A version and existing review/revision/case audits. Introduce immutable content versions and bound verification digests only with an explicitly approved storage contract. Stage files before DB commit; failed DB transaction must not overwrite retained evidence. |
| `assistance.services.review_eligibility`, `decide_assistance`, `record_release`, `void_release` | T before any P/A/M. Review/decision affects source program; receipts/voids affect ALL application programs for member, regardless of receipt's program/status/date/type. Lock entire affected program set sorted before any member lock; no cross-program lock acquired late. Keep unsupported EWAF decisions disabled. |
| `ewaf.evidence_services.record_policy`, `record_assessment`, `record_readiness` | Already T; shared invalidation service inside transaction for actual policy/assessment changes. Readiness-only audit records should not increment source generation unless deliberately included in approved dependency semantics. |
| `ewaf.configuration_services.record_configuration`, `record_validation`, `record_review`, `record_authority_evidence`; `scoring_services.record_scoring_policy` | Already T; one-program invalidation with immutable revision and audit. Diagnostic-only persistence must be distinguished from authoritative source changes. |
| `programs.services.save_program`, `save_requirement`, `change_publication`; `approval_services.record_pdao_approval`; `binding_services.capture_terms`, `bind_approval` | Already T; invalidate one program on relevant version/history/terms/control changes. No relaxing term guards or enabling/changing PDAO enforcement. |
| `events.services.save_event`, `change_publication` | Already T; invalidate affected linked application program on relevant terms/status/version changes, including unlink/relink if ever authorized. Protected-term restrictions stay intact. Attendance/unrelated observance changes do not become EWAF inputs. |
| `documents.admin.MembershipDocumentRequirementAdmin`, `DocumentTypeAdmin`; `members.admin` DisabilityType | Explicit transactional admin save/M2M integration, or route through new authorized services. Snapshot affected scope BEFORE mutation under T. Membership requirements conservatively affect all evidence-using programs until a narrower dependency mapping is reviewed. Protected program reference guards remain. |
| `accounts.admin.AdministratorAdmin`, `RoleAdmin` and auth user/group permission through-tables | Fence entire admin transaction including `save_related`/M2M and deletes; update durable authority generation or all affected programs. Actor/group topology changes and change/restore must leave monotonic history. Raw ORM helpers/imports must join the same service or be prohibited. |
| Expiry worker and result consumer | Determine earliest evidence valid-until under approved date/timezone rules; deadline crossing invalidates with a system audit. Consumer always checks actual deadline/generation even if worker is delayed. Clock rollback policy and trusted clock must be specified. |
| Imports, repair commands, storage administration | Inventory before rollout. Reject source mutations without the fence. Privileged SQL/storage tampering is outside app-layer guarantees; operational controls and reconciliation need a separate approved contract. |

Do not use broad post-save signals as a substitute for pre-mutation scope/locks.
No new integration should modify membership checklist/PDAO behavior, the approved
minimalist portal, or historical math as a side effect.

## Calculation and atomic current-pointer protocol

1. Under T and ordered scope locks, revalidate complete inventory, exact approved
   policy/config version, actor authority, source generation and expiry. Persist
   request with expected generation and envelope version. Retain incomplete
   applicants; fail closed rather than calculate a subset.
2. Calculate from the immutable accepted snapshot using its explicitly versioned
   engine. Expensive numerical work may occur outside source locks; intent is not
   current-result authority.
3. Reacquire T and the SAME ordered scope/state locks. Compare expected generation,
   authority generation, latest source/config/policy identities, inventory and
   deadline. Reject mismatch without updating a current pointer.
4. Persist all results, one complete criterion trace set per applicant, replay
   validation, completion outcome and run-source binding. Promote by conditional
   update against the same generation and expected prior pointer; require one row
   updated. Append PromotionEvent in this transaction. Pointer/audit failure rolls
   back the whole transition. Another request cannot partially replace a pool.
5. A source writer arriving next acquires T, increments generation and clears the
   pointer with audit in its mutation transaction. Consumers use a protected
   current-result service validating generation, graph completeness, authority,
   version and expiry; callers cannot cache a run ID as permanent authorization.

This protocol only supports an atomicity claim after ALL shared writers have
joined it. Even then a development pointer is not permission to select beneficiaries
or publish results. Operational activation remains a separate review.

## Required validation and approvals before implementation

- Owner approval of additive schema, data-retention/backfill strategy, source writer
  changes/admin integrations and transaction/lock contract. Migration dry-run and
  disposable MySQL migration preservation tests before any deployment authorization.
- Policy decisions: approved four-criterion configuration, measurement/normalization,
  PA period/scope, eligibility evidence and disputes, ties/classification, approval
  role/effective date/program binding, expiry boundaries and effect of signer revocation.
  PR-removal approval alone supplies none of those missing values.
- Race tests in both directions for every writer family, lock ordering across
  multiple programs/members, concurrent pool additions/removals, permission/M2M
  revocation, generation ABA, expiry boundary, CAS losers, retries, interrupted
  attempts, invalidation-audit failure and promotion-audit failure.
- Preserve old snapshots/digests/trace replay, no old-run current backfill, zero
  partial pools, no auto-restoration after replacement failure, and default-disabled
  operational consumers. Load/lock-duration testing before deciding whether to
  replace the coarse T fence.

**Stop boundary:** this file is a proposal. Gate 1 does not create these records,
modify any source writer, or execute migrations on the application database.
