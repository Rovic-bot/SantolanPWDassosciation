# G18-B Gate 2A review record and change inventory

2026-10-18. **Documentation-only design finalization. Accepted milestone: 70%.**
No Gate 2 implementation, schema change, source-writer edit, database access,
operational activation or Admin UI change was performed.

## Deliverables and decisions

- [Finalized implementation proposal](g18-b-gate2a-design-2026-10-18.md): selected
  single global authority generation; eight additive models with fields/relations,
  indexes/constraints, service-enforced invariants, atomic mutation/audit contracts,
  request/run sidecars, promotion CAS, expiry, preservation, risk and acceptance plan.
- [Verified static transaction/lock graph](g18-b-gate2a-lock-graph-2026-10-18.md):
  all participating writer families, actual versus proposed locking, auth/admin
  hooks, implicit FK locks, adjacent non-source writers and conflict resolutions.
- This review record: exact change inventory, verification boundary and required
  next authorization.

Resolved design choices:

1. **Global AuthorityGeneration**, with immutable AuthorityInvalidation events.
   No per-user/group counters and no per-program authority fan-out. Stale global
   epochs logically invalidate stored pointers; current facade always compares it.
2. **T -> H -> all Programs -> source states -> linked Events -> Applications ->
   Members -> ordered leaves**, with sorted sets resolved before locks. All
   source changes and their native/new mandatory audits share one transaction.
3. **Eight new tables only**, with immutable sidecars instead of modifying old
   request/run payloads or math. One proposed `0006_source_invalidation_foundation`
   migration; four circular new-table links added after table creation; no data
   migration, old-table alterations or automatic old-result promotion.
4. **Development-only promotion**, gated by verified disposable session, complete
   integration coverage, generation/context/permission/expiry checks and whole-graph
   replay. Accepted application behavior outside that session remains unchanged.
5. **Separately authorized 2B-2F increments**; schema foundations first, then
   authority, program/EWAF and shared member/evidence/assistance writer integrations,
   finally complete-pool promotion. Partial integration cannot claim atomic currency.

## Exact file-change inventory

Only these three repository files are added:

| File | Status |
|---|---|
| `docs/g18-b-gate2a-design-2026-10-18.md` | New design and migration/regression acceptance proposal |
| `docs/g18-b-gate2a-lock-graph-2026-10-18.md` | New verified static writer/lock inventory |
| `docs/g18-b-gate2a-review-2026-10-18.md` | New review/verification record |

**Existing repository files changed: none.** The three requested Gate 1/Gate 2
documents remain byte-for-byte unchanged. All prior source, tests, models,
migrations, G12-G17/G18-A/Gate 1 work, four-criterion reference and UI are preserved.
Ignored `.local/g18-b-gate2a/` holds the pre-work hash baseline, status/branch/HEAD/
staged diff snapshots and final verification manifest. Those files contain no
member data, database copies or credentials. `.env` was hashed for preservation,
not loaded as application configuration.

## What was verified during this review

- Read all three requested documents, repository instructions, current TARGET
  authority/development guidance/impact notes and relevant open decisions.
- Inspected application writer code and authentication/configuration declarations
  without importing Django settings or connecting to a database.
- Inspected installed Django 5.2.17 admin save/delete/bulk-delete/password and auth
  signal code. Confirmed M2M/native-audit operation boundaries, distinct password
  entry points, last_login maintenance and post_migrate permission creation.
- Parsed local migration declarations and writer definitions using Python AST/file
  reads. Verified current branch `feature/events` and HEAD
  `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
- Checked new document links, fields/model list, whitespace and final preservation
  manifest. `git diff --check` and cached-diff whitespace checks pass; existing
  line-ending notices are not new changes.

The static review corrected the earlier outline's Assistance lock shorthand:
all program members are locked only for `assistance.decide_assistance`, not all
EWAF receipts/voids. Void has no explicit EligibilityStatus lock. The photo locking
query joins current_photo; approval-control/reference-counter writes carry implicit
locks. The proposed order handles Event -> Member restoration without changing
event-registration semantics. These findings are documented, not implemented.

Local migration leaves inspected:

| App | Existing leaf |
|---|---|
| ewaf | `0005_durable_development` |
| programs | `0005_approved_terms` |
| members | `0003_disabilitytype_member_disability_type` |
| membership | `0004_alter_membershipapplication_options_and_more` |
| documents | `0003_revised_seventy_workflow` |
| assistance | `0003_revised_seventy_workflow` |
| events | `0006_annual_observances` |
| accounts | `0001_initial` (depends on auth `0012_alter_user_first_name_max_length`) |
| audit | `0002_alter_securityevent_action` |

No `manage.py`, migration generation/application, Django tests, server, application
DB query or disposable DB command was run in Gate 2A. This is appropriate for the
documentation-only change; it is not runtime verification of the proposed design.
**999 passing full-project tests / 457 EWAF / 72 focused** remain the actual prior
Gate 1 evidence. No new passing count or measured deadlock-free result is claimed.

## Preservation verification

Pre-work baseline contains **565 entries**, including existing tracked and untracked
repository files, `.git/index` and `.env`. All 565 remain byte-identical. Staged diff,
branch and HEAD match the baseline exactly. Exactly the three documents above are
new repository files. No staging, committing, resetting, cleaning, stashing,
pulling, pushing, merging, deployment or application-data operation occurred.

## Authorization and acceptance boundary

The next bounded candidate is **Gate 2B only**: author eight foundation models,
service/audit helpers, the proposed single additive migration, and their tests;
review generated SQL and run it only on fresh disposable MySQL with fictional
records. Owner approval must explicitly cover creation of that migration and
disposable-only migration testing. A design review or 2B approval does not authorize
application/production migration, later writer integrations, publication, deployment
or operational scoring. No permission question is an instruction to implement now.

Before 2B acceptance, prove additive forward/reverse/reapply isolation, all concrete
SQL constraints, service-only cross-row invariants, bootstrap/overflow/CAS/audit
rollback, historical digest/replay preservation and default non-promotability.
Before 2F acceptance, every writer/admin path requires two-direction real-connection
race coverage, complete cross-program fan-out, ABA and expiry tests, whole-graph
failure injection, all 999 baseline tests plus actual new tests, Django checks and
migration drift checks. The proposal contains the exact planned commands/modules.

Primary risks remain coarse lock contention, missed unfenced paths, MySQL implicit
locks/admin hook boundaries, file/DB non-atomicity, trusted clock boundaries and
misuse of a development pointer. Mandatory audits intentionally protect their
actors from deletion; otherwise permitted target deletion is not blocked by a
target FK. These schema semantics require owner review. Privileged SQL/file
tampering and unresolved Association approval policies stay outside the technical
atomicity claim. The inactive four-criterion proposal and live EWAF restrictions
remain unchanged.

**Stop for owner review. No Gate 2B implementation started. No 80% claim.**
