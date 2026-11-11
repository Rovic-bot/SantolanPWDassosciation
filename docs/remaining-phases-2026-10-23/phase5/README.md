# Phase 5 checkpoint — validation and handover

2026-10-24, Asia/Manila. **Partial.** The final corrected available regression suite passed: **1,638 tests in 1,302.890s**, including **897 unchanged EWAF tests**, with no failures, errors or skips. Institutional acceptance, blocked journeys, representative assistive-technology/UAT and a faithful historical-schema upgrade rehearsal remain unavailable. The accepted milestone remains 70%.

## Delivered scope and changes

This phase adds the broad ordinary-app test inventory, guarded additive-schema/recovery rehearsal, integrated synthetic browser journey, preservation evidence, full requirement dispositions, migration/activation instructions and proposed staff/UAT guidance. See [exact changes](../changes.md), [acceptance matrix](traceability-and-acceptance.md), [migration readiness](migration-and-activation-readiness.md) and [staff guidance/UAT](staff-guidance-and-uat.md).

Two small corrections emerged from validation: the new private-review policy now rejects a non-string routine-check basis and treats whitespace as absent, and the non-EWAF registration guidance test now expects the explicitly authorized eighth public destination. Test tooling now validates an entire migration plan before any operation; a mixed plan cannot partly reverse a new table before refusing an old migration. No protected assertion, startup guard or institutional policy was changed.

## Actual runs

All database runs used the G12 launcher, fresh isolated MySQL 8.4.11 datadirs/loopback ports, `.env` disabled, disposable grants and separate temporary private media. Logs retain command output, real identities and outcomes. Counts overlap; do not add them or substitute historical counts.

The launcher sets `DJANGO_SETTINGS_MODULE=config.settings`, `PYTHON_DOTENV_DISABLED=1`, empty base database `g12_empty`, test database `test_g12_disposable`, generated test-only credentials and `PDAO_ENFORCEMENT_ENABLED=0`. The test runner synchronizes models (`TEST.MIGRATE=False`) before the explicitly reviewed additive migration tests. Individual tests use synthetic policy overrides; none becomes ordinary configuration. Log last-write UTC timestamps and hashes are retained in `verification.json`; these are evidence-file timestamps, not invented exact test-start times. The code baseline is HEAD `776cac5d1119410717c6a31c044ea85f4d619941` plus the dirty/new file hashes in `../change-manifest.json`.

| Retained log | Outcome |
| --- | --- |
| `full-validated-suite.log` | 1,638 passed, 1,302.890s, exit 0, no failures/errors/skips. Includes all 897 selected unchanged EWAF tests. Fourteen historical migration tests were explicitly excluded before execution. |
| `final-targeted-tests.log` | 61 passed, 17.072s: registration/security/navigation, private reviews, Resources and additive schema/mixed-plan guard. |
| `recovery-and-preservation.log` | 5 passed, 37.629s: native disposable database/private-file restore, exact additive schema, three unchanged EWAF business-row preservation tests. |
| `browser-validated.log` | 1 integrated browser test passed, 16.553s; details below. |
| `schema-drift-check.log` | `makemigrations --check --dry-run --noinput`: No changes detected; exit 0. No migration generated. |
| `full-available-suite.log` | First broad attempt: 1 failure and 7 errors across 1,636 tests in 1,339.974s. Retained and explained below. |
| `browser-tests.log` | First browser attempt: 1 failed in 48.606s; overly exact test label selector corrected. No application behavior changed for this failure. |

The first broad run's assertion still expected seven public links. Two historical program migration tests were accidentally included: the per-operation guard refused their historical operations, but one allowed new review-table reversal had already occurred. That left only this disposable schema without the review table, causing five later errors, including four unchanged EWAF tests. Whole-plan preflight and exact exclusions correct the harness; the failed evidence is retained. No historical migration schema operation, normal-database fallback or protected-code change was used to repair the run.

The final suite discovers 1,652 tests and selects 1,638, with **14 historical migration tests explicitly Not Run**, listed in `final-suite-inventory.json`. Three independent business-row tests sharing migration-test classes are included. Optional `program_intake`/`main_testing` apps remain uninstalled/disabled. This is the available ordinary-app regression suite, not a claim to run every optional/deferred/historical configuration. Earlier inherited fixture helpers may invoke Python data-seeding functions from historical modules; no historical schema migration plan was applied. Model-synchronized schema and synthetic migration history are not a faithful deployed-baseline upgrade.

Commands actually used (the shell redirected output to the corresponding retained logs):

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test core accounts members membership announcements events programs documents assistance ewaf analytics reports audit scripts.remaining_schema_tests --testrunner scripts.remaining_full_test_runner.RemainingFullTestRunner --noinput --verbosity 2 --failfast
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.test_registration_intake members.test_information_review core.tests.test_resources scripts.remaining_schema_tests --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test scripts.remaining_recovery_tests scripts.remaining_schema_tests ewaf.test_evidence_migrations.EvidencePreservationTests.test_evidence_operations_preserve_complete_existing_business_rows ewaf.test_configuration_migrations.ConfigurationPreservationTests.test_all_g12_and_business_rows_preserved_by_g14_workflow ewaf.test_scoring_migrations.ScoringPreservationTests.test_entire_historical_g12_g14_business_rows_preserved --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test scripts.remaining_phases_browser_qa --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run --noinput
```

## Security, privacy and accessibility

Tests exercise permission checks and revocation, direct unauthorized requests, private attachments/forms, CSRF, stale writes, duplicate/replayed submissions, concurrent synthetic updates, audit failure rollback and preserved old records. Finish revocation remains independent of exhausted request budgets, idempotent and unable to reset submission/retrieval budgets. A reference alone grants no private access. Private review findings do not update accepted evidence, dates, scores or outcomes. CMS drafts/private history are not public snapshots.

Private-review concurrency tests cover identical requests for the same Member. Deliberate simultaneous reuse of one request UUID across different Members remains an untested error-response edge case: the unique database constraint prevents a second record, but a collision may surface as an integrity error rather than a recoverable form message. This disabled foundation needs that additional adversarial check before operational activation. Raw database administrators are outside the application-level history guards; database access control remains necessary.

The browser evidence uses fictional records and explicit synthetic policy values only. Chrome 156.0.8078.48 completed **48 responsive checks** across 12 pages at 320/390/768/1440px; keyboard form/reference/review journeys, error recovery, visible focus, receipt/resource enlargement to 200%, print mechanics, reduced-motion preference, public reading controls and an accessibility-tree capture. Fourteen high-contrast text samples on the new published resource detail passed their sampled thresholds. Reading-control tests spy on speak/cancel calls; they do not prove actual spoken output. Print mechanics are not printed-paper review.

Representative screen-reader sessions, full normal/high-contrast audit, 400% zoom/browser/assistive-tool combinations, actual spoken output, participant UAT and blocked positive journeys remain **Not Tested/Blocked**. No WCAG certification or institutional acceptance is claimed. See [synthetic resources screenshot](ui-validated/resources-desktop.png), [mobile 200% screenshot](ui-validated/resources-mobile-200percent.png), [private review screenshot](ui-validated/private-review-synthetic.png) and `ui-validated/checks.json`.

## Preservation, schema and operational boundaries

Final preservation in `verification.json` confirms **267/267 protected files unchanged** against both the current baseline and original Phase 1 manifest; **58/58 pre-existing migrations unchanged**; governing source originals and prior audit reports unchanged; and the original 46,880 progress-record bytes retained. Original/integrated Section 8 is byte-identical: 8,384 bytes, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. Hash preservation is distinct from executable behavior evidence. The 897 unchanged EWAF tests in the successful broad run cover both criterion histories, strict CR, bounds/directions, missing/stale evidence, complete pools, ties, decision/capacity, publication freshness and actual release/PA semantics. No engine assertion was altered.

Read-only Python AST checks passed for all 25 changed/new Python files; the new browser JavaScript passed `node --check`; local links in this continuation's Markdown resolved; changed/new source trailing-whitespace checks and `git diff --check` passed. Git emitted only the existing line-ending normalization warnings. Final file hashes are in `../change-manifest.json`.

No new Phase 5 migration was generated. The exact existing membership 0006 and new members 0006/core 0002 were reversed/reapplied only in disposable synthetic tests. Existing Member/content/history values were checked. Native dump/restore and one synthetic private-file restore succeeded. Neither test proves recovery of real records or upgrade from an unknown historical schema. The unchanged startup guard rejects these three migrations when pending; disabled features do not waive that requirement. Working/production history was not queried, migrations were not applied there, and no deployment/credentials/normal configuration changed.

The eight Admin groups and minimalist interface remain intact. Staff inbox filters stay under Members; private review links are gated under Member details; content stays under Announcements & CMS. Public Resources is appended after the seven existing destinations and reads only reviewed publications. No real source content was published. Existing pending-registration/Finish functionality was reused, not recreated.

## Remaining decisions, risks and handover

Registration, its membership handoff, public tracking/recovery, private review operation, PDAO, referral tickets and RSVP remain disabled or unavailable as documented. Owner technical direction D01–D14 does not settle Association qualifications, OQ-27 document/identity procedures, legitimate control numbers/manual PRPWD, socioeconomic assessment, approval authority, staff assignments or privacy/retention. Actual session/budget/upload/proxy values still require security approval. Tracking IQ-03, routine review IQ-08, review/remedy authority IQ-12, PDAO IQ-09/16 and RSVP IQ-11 remain open.

New private notes do not mark accepted evidence unresolved. They therefore cannot be operationally enabled as a substitute for the missing approved evidence/dispute coupling. Exact reviewed-calculation provenance, safe correction linkage and terminal-case remedies remain incomplete. Referral lifecycle/access/minimal-data/reference rules and event audience binding to protected terms remain unresolved. Handoff must preserve the existing membership writer's top-level transaction contract, not fabricate identifiers or verification facts.

Benefits are easier authorized retrieval, retained private concern history and one maintainable public guidance destination with explicit source review. Remaining risks are misuse if gates are later configured without approvals, stale authored content, privacy exposure through incorrectly approved access/custody, and MySQL partial-DDL failure during future migration. Saved/printed copies cannot be revoked by Finish. No performance/fairness improvement, deployment readiness or higher completion percentage is claimed.

No next phase is started. Further work requires the specific decisions above, an approved safe protected-service integration contract where missing, a faithful synthetic historical-schema rehearsal, target-specific migration/activation authorization and the remaining accessibility/UAT evidence. The progress record retains a separate final Phase 5 checkpoint without changing earlier reports. No normal database changes, production access, commit, push, merge or deployment occurred.
