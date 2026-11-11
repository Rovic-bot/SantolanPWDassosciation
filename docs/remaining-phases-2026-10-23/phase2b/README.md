# Phase 2B operational completion checkpoint

2026-10-23. **Partial.** The existing registration foundation and Finish correction are retained. This checkpoint adds staff inbox filters and an exact additive migration lifecycle rehearsal. Institutional operating rules, working-database authorization and activation remain outstanding. Accepted milestone: **70%**, unchanged.

## Delivered and reused

Members → Membership Reviews now permits filtering pending registrations by their existing processing state and submission channel. Exact AMR reference retrieval takes precedence over filters so a printout can locate its retained intake. Invalid filters return no records with an accessible error. Filtering/retrieval remain read-only and use the existing gated inbox, staff permissions, paginator, styles and detail routes. No new status, identifier, document permission or Member writer was introduced.

Files changed in this checkpoint:

- `membership/registration_views.py`: existing inbox filters and bounded query validation only; Finish remains unchanged.
- `templates/membership/registration/inbox.html`: labeled filters, result status, and pagination retaining search/filter values.
- `membership/test_registration_completion.py`: two inbox compatibility tests and one migration/history/metadata/startup-guard lifecycle test.
- `scripts/remaining_phases_test_runner.py`: fresh G12 instance/private-media requirement; permits only fingerprinted, reviewed additive migrations during explicit tests.
- `scripts/remaining_phases_evidence.py`, this report/logs/baseline/verification and the existing progress record: retained evidence and checkpoint.

No new migration or dependency. Membership 0006 and all earlier migrations remain byte-identical. No settings, sidebar, Public navigation, protected EWAF code or startup guard changed.

## Migration and startup evidence

The test removes only the empty new registration tables from a model-synchronized disposable baseline, establishes **synthetic baseline migration-history rows**, and runs the exact forward target, reverse-to-parent target and forward target again. The actual migration executor/history recorder, `post_migrate` content types/permissions and unchanged startup guard are exercised. It verifies a retained synthetic legacy membership row is unchanged, five new content types appear, and no new user grants are assigned. The pending plan must be exactly membership 0006 in either direction. The runner refuses other migration fingerprints.

This is not a historical upgrade from an actual deployed schema: baseline tables are synchronized from current models, including intentionally deferred models. Historical migrations were not executed. A faithful synthetic pre-upgrade schema with deferred tables absent, working history inspection, backup/restore and target-specific authorization remain prerequisites. No working database was read or changed. Reversal is tested only with empty new tables; reversing populated intake would destroy retained records and is not an operational rollback policy.

Membership 0006 is not an approved startup deferral. Its disabled public policy cannot satisfy the unchanged guard. The existing [startup recovery procedure](../../phase2b-finish-security-2026-10-23/startup-recovery-procedure.md) remains governing, with this narrower rehearsal evidence added. Conditional recovery is still an exact reviewed target after target-specific authorization, never blanket migration, fake history, a launcher bypass or a new deferral by inference.

## Validation

Actual run commands, counts, isolation identities and protected hashes are retained in `verification.json` and the two logs in this directory. Focused tests: **60 passed in 19.674s**. Selected workflow/EWAF regression: **429 passed in 178.957s**, including **102 unchanged EWAF tests**; no failures/errors/skips. Both commands exited 0. Counts overlap and must not be added. Both use fresh G12 MySQL instances, `.env` disabled, isolated grants and separate temporary private media. No fallback to normal data.

All 267 protected files and pre-existing migration files match the captured current baseline. Original/integrated Section 8 remains byte-identical: 8,384 bytes; SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. Preservation alone is not behavior evidence; the selected unchanged EWAF tests supply separate executable evidence.

The new template uses native labeled controls, existing responsive layout and a status message. Browser/assistive-technology evidence will be recorded separately in Phase 5; this checkpoint makes no WCAG or live-user claim. Public intake remains disabled in ordinary settings, and private forms/attachments retain existing checks. Search does not grant access by possession of a reference.

## Blocked and next independent work

Association/client approval remains required for qualifications/field purpose, OQ-27 document alternatives and physical/original/copy handling, identity/representative/cross-channel verification, legitimate control-number assignment/manual PRPWD relationship, socioeconomic assessment and approval authority, named staff assignments and privacy/retention/custody. Exact session/budget/upload/proxy parameters and operational activation are not supplied. PDAO authority remains separate and absent.

Membership handoff remains refused, including the database NULL-link constraint. A safe future bridge must call the existing membership writer at its top-level transaction boundary, never fabricate identifiers/PRPWD evidence, preserve native audit cardinality and invalidate dependent evidence through authorized services. Changed registration evidence already invalidates its onsite findings in the retained foundation; there is no automatic EWAF calculation.

The practical improvement is easier staff retrieval and more migration evidence. Remaining risks are institutional misuse if gates are later configured without approval, shared-device custody after information has already been delivered, and partial MySQL DDL failure during a separately authorized future migration. No unsupported fairness/performance benefit is claimed.

Phase 3 may proceed only with independent, private supporting components. Public tracking access/recovery/fields (IQ-03), review authority/terminal remedies (IQ-12), routine-review policy and any protected-writer dependency remain blocked. The owner's latest authorization permits that independent work after this checkpoint; it does not activate Phase 2B or settle these decisions.
