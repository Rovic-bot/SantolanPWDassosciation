# Migration, activation and recovery readiness

2026-10-24 (Asia/Manila). **Proposal only. Working/production database access, migration and activation have not occurred.** Keep the unchanged startup guard. The owner's development authorization covers synthetic rehearsal, not an identified operational target.

## Frozen additive files and dependency order

| Suggested order | Exact target | Direct prerequisites | SHA-256 |
| --- | --- | --- | --- |
| 1 | `membership.0006_association_pending_intake` | membership 0005; swappable user (existing members prerequisites transitively) | `fc897f9ee2f2f1b2433cccc7bf7f6bd531c199363f0cfa5fe2bdcfb9583b224d` |
| 2 | `members.0006_private_information_review` | members 0005; programs 0005; swappable user | `d7202490dceecda7606d7367b2628fd0097d5fbcad55ae01cf03bbacd32812a1` |
| 3 | `core.0002_resource_publication_metadata` | core 0001 | `25245202eb5c7af929aef66e2664779172c5f165ca2ddcd2d241b36dd4a52454` |

The three are independent once their existing prerequisites are genuinely applied. This order is an operator review sequence, not permission to apply missing historical dependencies. The new Members schema contains only two new review tables/three checks. Core adds four optional metadata fields and expands key choices without changing the column type. No RunPython backfill, Member rewrite, EWAF migration or permission assignment is included.

The startup guard rejects **all three** while pending: none is in its five fingerprinted deferrals. The earlier membership-only recovery proposal is now insufficient for this changed checkout if the other two are also pending. Turning policy gates off does not satisfy schema checks. No allowlist change, alternate launcher, fake history, deleted migration, blanket migration or enabling optional schemas is a recovery step.

## Evidence and its limits

The retained tests use fresh MySQL 8.4.11 datadirs, loopback ports, `.env` disabled, isolated database grants and separate temporary media. Baseline schema is synchronized from models. Explicit **synthetic migration-history fixtures** permit exact plan/history/post-migrate/startup checks. Only fingerprinted additive migration operations are executed or reversed. Historical schema migration plans are not applied; inherited fixture helpers may call Python data-seeding functions from historical modules. That distinction also qualifies the earlier checkpoint shorthand about migrations not being run.

Exact new migration reversal/forward application passes with old synthetic Member data and old PublicContent/title/body/publication/history unchanged. Membership 0006 additionally demonstrates new content-type/permission creation without grants and the actual unchanged startup guard before/after. These tests do not prove upgrade from an unknown real migration history or an old schema with all deferred tables absent.

`scripts.remaining_recovery_tests` successfully exercises native `mysqldump`/`mysql` restore on its verified **test_g12_disposable** database, plus backup/restore of one private synthetic upload. It changes a synthetic content field/file after backup and verifies retained record values and bytes are restored. The dump and file-copy directory are temporary and removed by the test. No real database, cloud storage, real keys, full historical EWAF dataset or disaster-recovery service was tested. This is a local synthetic rehearsal, not a production recovery guarantee or an approved retention schedule.

## Conditional procedure for a separately authorized target

1. Obtain written scope naming database/server/environment, operator, reviewed code revision **and dirty-file hashes**, these exact migration hashes, read-only inspection, backup/restore, apply and startup checks. No commit is inferred. Confirm the institutional/security policy register separately from schema authority.
2. Rehearse the actual intended historical **schema/history shape** with synthetic data and deferred tables absent where appropriate. Historical migration execution would require a separately reviewed test scope; do not reuse current model-synchronization as proof. Confirm existing dependency history and the full pending graph without copying member data.
3. Once target access is separately authorized, inspect its identity/history/table state read-only. Unexpected applied rows, absent prerequisites, partially created tables, changed file hashes or other pending migrations are stop conditions. Do not fake them or infer that extra migrations are approved.
4. Review each exact forward plan. Proposed commands, **not run on the working database**:

   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate membership 0006_association_pending_intake --plan
   .\.venv\Scripts\python.exe manage.py migrate members 0006_private_information_review --plan
   .\.venv\Scripts\python.exe manage.py migrate core 0002_resource_publication_metadata --plan
   ```

   Each inspected plan must contain only its named new forward migration. Recheck the later plan after each successful step. Extra dependencies/reverse operations need a new review; a target name alone does not constrain the plan sufficiently.
5. Take the approved target database/private-file backup and verify an authorized isolated restore. Assign responsibility for MySQL partial-DDL failure, private-file custody and downtime. DDL is not promised to roll back as one application transaction. A partial failure requires inspection and reviewed recovery, never an automatic retry.
6. Only after target-specific apply approval, substitute `--noinput` for `--plan` for each frozen single target. Do not run a blanket command. Review post-migrate metadata effects; no new staff grants are implied. Verify expected tables/fields/checks/history/permissions and unchanged original data/audits/references.
7. Keep Association registration and information-review policies absent/disabled. Start only through the unchanged approved launcher after the full pending-plan check succeeds, leaving the original fingerprinted deferrals intact. Smoke-test existing workflows and disabled direct routes. Public Resources may show unpublished-topic guidance; no resource publication is inferred from applying schema.
8. Retain commands, UTC/local timestamps, code/schema hashes, identities, backup evidence, outcomes and failures. Stop before any separately unapproved collection, grants, source publication or deployment.

## Disable and rollback

For resource content, use authorized withdrawal/archive; retain snapshots and history. For registration/private reviews, use the documented feature gates and an approved pause/access-continuity procedure. Finish remains available for legitimate revocation even during policy pause. Do not silently change public receipt access/recovery policy.

Do not reverse populated registration/review tables or drop resource metadata as routine rollback. It destroys retained records/metadata and can leave private uploads orphaned. Exact reversals tested on disposable fixtures do not authorize that loss. A code rollback must also consider active sessions, retained references, new schema dependencies and the unchanged startup guard; use a separate compatible checkout and reviewed restore plan rather than resetting this dirty tree.

## Operational decisions still missing

- **Association/client:** qualifications and field purpose; OQ-27 originals/copies/scans, permitted alternatives and physical envelope handling; identity/representative/cross-channel/correction procedures; legitimate member/control-number assignment/manual PRPWD relationship; socioeconomic assessment; membership decision responsibility; named staff access; privacy/retention/custody/disposal/incident procedures; reviewed public source content.
- **Project owner/security review:** actual registration context duration, attempt-window/address/session/reference-retry budgets, file/count/body limits, trusted address/proxy handling and shared-device/pause/recovery procedures. Existing maximums constrain configuration but do not choose approved values. No synthetic fixture value is an operational recommendation or approval.
- **Review/tracking:** IQ-03 status fields/access/recovery/QR/abuse protection; IQ-08 routine basis, evidence/update/unresolved-case procedures; IQ-12 reviewer authority/deadlines/final-case remedies; exact reviewed-calculation binding and safe accepted-evidence integration. A private note cannot stand in for unresolved-evidence blocking.
- **PDAO/external:** intake/transfer authority, checklist/information handling, forwarding procedure and staff assignments under IQ-09/16. No collection, forwarding, government status/ID issuance or membership creation from PDAO intake.
- **Referral/RSVP:** separate ticket verification/state/reference/minimal-data contract and IQ-11 RSVP audience/fields/duplicates/cancellation/capacity/restricted-attendance rules. New event audience fields need a compatible protected-terms binding.

Membership handoff remains unavailable at service and database boundaries. A future bridge must use the existing membership writer at its **top-level** transaction boundary with real authorized identifiers and accepted onsite/assessment facts, exact retry/member deduplication, native audit cardinality and existing source invalidation. Do not surround separate protected writers with a new outer transaction or manufacture PRPWD findings. No engine changes are proposed here.
