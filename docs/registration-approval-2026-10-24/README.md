# Pending Association registration approval — 2026-10-24

Technical implementation is delivered in the current development checkout. Operational Phase 2B remains **Partial**: real institutional procedures, assignments and activation are not approved by this code change. Accepted milestone remains **70%**. This is the owner's specifically requested registration-to-Member extension, not a new Phase 3 development cycle.

## Staff workflow and running fictional demonstration

Open **Members → Membership Reviews → Pending Association registrations**. Search the existing AMR reference, begin review, and record the current five-item onsite observations. **Prepare membership approval** then displays the retained applicant fields and collects the legitimately assigned control number, identity/representative acceptance basis, five-item acceptance basis, responsible socioeconomic assessor/date/record, and duplicate-review findings. This creates one linked pending legacy membership review, not a Member. Staff record actual manual PRPWD verification and then choose **Approve membership** in the membership decision form on the pending-registration detail page. Approval uses the existing membership writer and creates one official Member. Rejection creates none. The detail and inbox display the real decision and link to the official Member where permitted.

The form preserves the five confirmed Association requirements; it defines no new document substitute, government-ID prerequisite, assessment scale, identity procedure or approval authority. Physical envelope findings do not require an envelope upload. Current legacy upload requirements must be explicitly reconciled and fingerprinted in the handoff contract. Pending attachments remain private and retained; they are not automatically copied into approved evidence. Staff supply only the configured legacy uploads when preparing review.

The separate **fictional-only demonstration** is running at http://127.0.0.1:8002/membership/register/ ; staff inbox: http://127.0.0.1:8002/membership/registrations/ . Use the existing `demo_staff` demonstration login. Credentials remain in the ignored local demonstration folder and are not included in this report. The prior port-8001 demonstration and port-8000 ordinary site were not stopped or modified. The new demonstration has its own fresh loopback MySQL instance, private media, session/CSRF cookies and visible fictional-data banner. Its configured procedures and staff grants are test fixtures, not Association authorization. The manual-registry example URL is deliberately fictional; no government request, approval or ID issuance occurs.

## Implemented controls

- No direct Member creation from pending intake. `handoff_registration` enters `submit_application` at top level; the existing writer owns the authority/terms fence and transaction. Link, legacy profile/documents, native event and immutable acceptance action commit together. Existing `record_verification` and `decide_application` perform the later steps. Enlisted tests prove one native audit per operation and zero affected program scope.
- AMR reference, original and corrected revisions, original attachments and histories remain intact. Applicant fields are pinned to the current revision; a tampered POST cannot replace them. Corrections before handoff invalidate onsite readiness. Linked records cannot use pending correction/onsite actions to rewrite the accepted submission.
- The original request key provides one-time linkage. Identical repeated preparation returns the same legacy record with no extra files/event. Changed evidence or acceptance replay is rejected. The handoff token cannot be replayed through the unlinked legacy encoding route. A concurrent/stale approval cannot create another Member.
- Existing Member and pending-review control-number collisions block handoff. Staff record human duplicate review; matching names/contact information never merges people. Different identifiers for the same person still require actual human identity review.
- Every linked verification/decision service rechecks current registration and legacy permissions, accepted revision, procedure fingerprint and link. Legacy detail/list/download and member-document/review routes enforce the additional registration access boundary. Existing unrelated official Member access continues under its existing permissions. Program evidence reuse remains governed by existing program services.
- Real manual verification is still mandatory for approval. No service manufactures a successful registry result. Accepted onsite findings are retained separately from EWAF evidence and scores. Public references remain identifiers, not private access credentials.
- CSRF, private uploads/delivery, native audit rollback, freshness/version checks and append-only registration history remain enforced. A public intake pause or request-budget change does not strand an accepted staff review; a changed acceptance/authority procedure blocks further decisions until separately reconciled.

## Files changed by this task

The complete machine-readable list and original hashes are in `before.json` and `preservation.json`. Pre-existing unrelated dirty/untracked work is preserved.

| Files | Purpose |
|---|---|
| `membership/registration_handoff.py` (new) | Policy-bound preparation form, immutable-field projection, deterministic retry proof, duplicate checks, atomic link/provenance helpers, linked access and decision guards. |
| `membership/services.py` | Optional pending-registration input to the existing native submit writer; link inside its transaction; linked checks/audits on existing verification and decision operations. |
| `membership/registration_models.py`, `membership/migrations/0007_registration_membership_handoff.py` (new migration) | Permit an explicitly linked `membership_review` state; retain unique link and constrain state/link consistency. |
| `membership/registration_services.py` | Delegate handoff to the existing writer; allow only the new named audit actions with fresh permission checks. |
| `membership/registration_views.py`, `membership/urls.py` | Authenticated preparation page; verification and decision forms in the pending detail; actual membership status in inbox. |
| `membership/views.py`, `members/views.py`, `documents/views.py`, `documents/services.py` | Guard alternate linked legacy detail/search/document/review access, including direct service calls. |
| `templates/membership/registration/detail.html`, `inbox.html`; new `handoff.html`, `decision.html` | Existing minimalist components and navigation; visible accepted basis, manual review, decision, Member link and accurate status. |
| New `membership/test_registration_handoff.py`, `test_registration_handoff_migration.py` | Synthetic lifecycle/security/retry/audit/concurrency/enlisted-writer and exact migration tests. |
| `membership/test_registration_completion.py`, `test_registration_migration.py`, `scripts/remaining_schema_tests.py` | Rehearse older extension migrations at their actual pre-0007 schema, then restore the child. Original preservation/permission assertions retained; startup additionally proves 0007 is blocking. No historical migration file changed. |
| New `scripts/registration_handoff_test_runner.py`, `registration_approval_browser.py`, `registration_approval_browser.cjs` | Narrow hash-pinned migration allowance in the existing disposable runner; browser approval/responsive evidence. |
| This report, JSON/log/UI evidence and existing progress record | Scope, results, limitations and resume instructions. Ignored `.local/registration-approval-demo-20261024/` holds isolated launch/runtime files. |

## Schema and startup readiness

`membership.0007_registration_membership_handoff` depends only on `membership.0006_association_pending_intake`. SHA-256: `8d400ddcc416c0081518dd45a5cbc2097e7b36103d391260174347c0e4c2ddb8`.

It removes the deliberately NULL-only `reg_handoff_unavailable` constraint; replaces the permitted-state CHECK with the additional `membership_review` state; adds a CHECK requiring a link exactly in that state; and changes field choices. No historical row, old reference, Member, EWAF model or evidence record is backfilled. The existing one-to-one link remains unique. Immutable `RegistrationAction` holds the accepted current revision, responsible actor, basis, procedure snapshot and request digest; no new approval role is introduced.

The reverse precondition runs **before reverse DDL** and refuses if any handoff link exists. Do not delete Members, links or audit history to force reversal. Once used, disable the feature and retain the schema/provenance; recovery needs a separately reviewed plan. MySQL DDL is not generally transactional: backup and verify exact plan/constraints before any authorized operational application.

**No working-database migration was executed.** Prior evidence identifies local development `santolan_pwd` on 127.0.0.1:3307 as already having membership/0006, members/0006 and core/0002. This task did not reconnect to that database or recheck its current history. Reconfirm the exact target before asking for/applying an upgrade. The unchanged startup guard will block an ordinary restart while 0007 is pending; it has not been added to any deferral list or bypassed.

Target-specific sequence, requiring separate authorization:

1. Confirm database/schema/server UUID/datadir and private-media location without exposing credentials; ensure this is the intended working-development target.
2. Take and verify a current database/private-media backup and disposable restoration. Retained older backups are not a new backup of current data.
3. Inspect `showmigrations membership` and `migrate membership 0007_registration_membership_handoff --plan` using that exact reviewed environment. Expected forward plan is only 0007 if 0006 is applied. Stop on any extra dependency or mismatch.
4. After target-specific migration approval, apply only that target migration. Verify migration record, state/link CHECKs, unchanged old references/records and normal startup guard. Do not apply optional/deferred migrations.
5. Schema application alone enables no real collection or membership powers. Review the common registration contract, required handoff procedure references/fingerprint and actual staff assignments separately, then accept the authorized end-to-end workflow before activation.

Disposable evidence: the exact new migration reversed/forwarded on synthetic pending data; linked reversal refused before DDL; older 0006 and the other extension lifecycles were tested in proper dependency order; `makemigrations --check --dry-run` reported no changes. The demonstration separately restored only the recorded schema/history metadata, then applied the four exact reviewed extension files. No real-data dump or historical migration execution was used. See `demo-isolation.json`, `demo-http.json` and actual test logs.

## Actual validation and limits

All database tests used the fresh-instance `scripts/g12_test_runner.py`, with `.env` disabled, separate random loopback MySQL/datadir, restricted synthetic database grants and separate private media. Tests used the exact-migration runner `scripts.registration_handoff_test_runner.RegistrationHandoffTestRunner`; the initial handoff-only run used the previous remaining-phases runner without executing migrations.

| Run / retained log | Actual outcome |
|---|---|
| `handoff-initial.log` | 18 tests, 15 errors: the new audit action names were absent from the registration allowlist. Fixed by adding the specific capability-checked actions; original failed evidence retained. |
| `handoff-recheck.log` | 19 tests passed in 7.127s, including transactional/concurrent/enlisted handoff and new migration lifecycle. |
| `regression.log` | 201 tests in 63.751s; 3 assertion failures and 2 errors. Older guidance wording mismatches; an unavailable `documents.tests` label; and a pre-child migration fixture. Corrected the label to the actual `documents.test_storage`, and adapted schema fixtures without changing engine assertions. |
| `regression-final.log` | 266 tests in 106.253s; no errors; 5 assertion failures across three test methods remain, all from two pre-existing public guidance wording expectations (including inherited remote-storage subtests). New handoff, original membership/program/document behavior, native writer, browser, and exact migration checks passed. |
| `ewaf-final.log` | **188 tests passed in 219.445s** on the final current code: approval/browser plus unchanged formula/configuration/evidence/decision/publication/release checks. Per-log digests, isolation identity and outcomes are recorded in `validation.json`. |

The unresolved assertions expect `How to become a member.` and `Membership applications are not accepted online.`. Those templates/test expectations were already present at task start and were not changed to obtain passes. The public page now distinguishes enabled online intake from closed intake. These older expectations require a separately reviewed wording/test reconciliation; this report does **not** call the whole regression suite passing.

The final EWAF run selected `ewaf.tests`, `test_configuration`, `test_weighted_scoring`, `test_scoring_inputs`, `test_evidence`, `test_decisions`, `test_operational`, `assistance.tests`, `announcements.test_results`, the new handoff/migration tests and the new browser test. Earlier workflow runs additionally exercised `ewaf.test_membership_writers`. Counts overlap across runs and are not additive unique-pass counts.

Browser evidence in `ui/` demonstrates pending form → preparation → manual verification → approval → official Member. Twelve page/viewport checks cover 320/390/768/1440px, duplicate IDs and horizontal overflow; keyboard focus and anonymous denial were checked. No JavaScript errors were reported. This is not a complete screen-reader, contrast, assistive-technology or WCAG audit; representative PWD/officer UAT remains pending. Historical/deployed-data migrations and production performance were not tested in this task.

## Preservation, remaining gates and risks

`feature/events` at `776cac5d1119410717c6a31c044ea85f4d619941` remains the checkout; no commit/push/merge/deploy. **All 267 protected paths match the Phase 1 baseline.** Original and integrated EWAF Section 8 match byte-for-byte: 8,384 bytes, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. No pre-existing migration changed. Preservation hashes are evidence of unchanged files, separate from the executed behavior tests. Existing eight Admin groups, public navigation, member identifiers, manual verification and shared styling are preserved.

Real use still requires Association decisions on qualifications, identity/representatives, five-item acceptance/original-copy handling, legitimate control-number source and first-time-applicant PRPWD compatibility, assessment responsibilities, decision authority, staff assignments, privacy/retention and operating security values. New mandatory handoff references are `identity_procedure_reference`, `requirements_procedure_reference`, `assessment_procedure_reference`, `identifier_procedure_reference`, `decision_authority_reference` and the reviewed `membership_requirements_fingerprint`, in addition to the existing onsite/common contracts. `handoff_enabled` must be explicitly reviewed for the target. No ordinary settings or real staff grants changed.

Older minimal submissions and incomplete fields required by the legacy writer cannot be silently converted. Resolve them through authorized correction/reconciliation first. After linking, profile/acceptance correction, changed institutional-procedure reconciliation and reopening a final decision remain unavailable unless a separate compatible procedure is approved. Policy changes deliberately stop dependent decisions; public pauses alone do not. Name-based similarity and unique numbers do not conclusively establish person identity. Filesystem cleanup remains subject to the existing storage failure limitations.

Benefit: authorized staff can complete a retained registration in one review location, preserving its reference, original information and audit trail, with no duplicate Member from retry/concurrent approval. No throughput or fairness improvement is claimed. Risks: misuse of configured authority references or staff attestations cannot be eliminated by code; migration/activation and real acceptance require accountable review.

PDAO collection/forwarding, government ID issuance, public tracking/recovery, new accounts/notifications and Phase 3 evidence integration remain excluded. The operational-closure checklist remains authoritative for those unresolved items. This task addresses the technical OC-06 handoff dependency; it does not close OC-01–05 or institutional/UAT acceptance.
