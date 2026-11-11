# Phase 2B Finish security correction and startup diagnosis

2026-10-23. **Task A security correction: Completed. Task B diagnosis/procedure: Completed; working startup recovery not performed. Phase 2B remains Partial.** The accepted milestone remains **70%**. No new registration collection, membership handoff, PDAO processing, Phase 3, working migration, production configuration, credential change or Git publication was performed.

Authority is the owner's narrowly scoped Finish-security correction, isolated testing and startup-diagnosis instruction. It does not approve institutional policy or any working-database operation. Existing D01–D14 technical direction and outstanding institutional/security parameters remain distinct.

## Root cause and corrected behavior

The previous Finish endpoint called `_public_attempt` before revoking its context. Exhausted address/session budgets denied the request before revocation. It also used the ordinary public policy/context check, which rejected already-revoked, expired or changed-policy contexts instead of permitting a safe idempotent closure.

Finish is now a **POST-only, explicitly CSRF-protected access-reduction action**. It obtains the context identifier only from the current server-side session, never from a posted reference/context. The service locks the context and verifies its HMAC session binding, online channel and lack of a staff actor before doing anything, including an already-revoked retry. A correct identifier alone cannot revoke or retrieve another session's information.

The first successful call atomically records revocation and the retained close audit; later calls preserve the original timestamp and do not add another audit. An expired context or changed/disabled collection policy does not prevent its owner from closing it. A request with no session context returns the generic closed message without creating a submission context or invoking revocation. This narrow closure/no-op availability is not public registration activation.

After success the session's context pointer is removed. Finish does not create or rotate the browser session, reset/consume request counters, issue another context, erase the pending application or expose form data. Normal apply/receipt gates and limits remain unchanged; repeated Finish cannot replenish them. Revoked contexts remain denied by the unchanged submission/receipt checks. Attachments and administrative completed forms retain their separate authenticated access requirements. Authorized staff access to retained records is not revoked by an applicant finishing their browser interaction.

## Exact changed files

| File | Change |
|---|---|
| [`membership/registration_views.py`](../../membership/registration_views.py) | Changes only Finish: removes ordinary policy/budget dependency, makes CSRF explicit, uses only the current session context, and treats repeated closure as a no-op without creating/rotating a session. |
| [`membership/registration_services.py`](../../membership/registration_services.py) | Changes only `revoke_context`: ownership checks independent of collection policy/expiry, row-locked idempotent revocation and exactly-once close audit. Existing receipt/submission/permission services remain unchanged. |
| [`membership/test_registration_finish.py`](../../membership/test_registration_finish.py) | Adds 14 request/service security cases, one concurrent revocation case and three tests of the actual unchanged startup guard. Uses synthetic fixtures and verified isolation. No existing assertion is edited. |
| [Progress and decisions](../added-targets-phase1-2026-10-23/progress-and-decisions.md) | Prepends this completed correction/checkpoint; all earlier bytes remain intact. |
| This documentation directory | Adds baseline hashes, retained test logs, this report, startup procedure and reproducible evidence verification. Earlier Phase 1/2A/2B/readiness evidence and approval register remain unchanged. |

No model, form, URL, template, stylesheet, JavaScript, existing test, dependency, migration, setting or startup-guard file changed. The eight-module Admin and existing Public navigation remain intact.

## Actual tests and isolation

| Run | Actual result |
|---|---|
| [Focused Finish and existing intake](targeted-tests.log) | **57 passed in 4.019 seconds**, zero failures/errors/skips. Includes 18 new security/startup tests and 39 existing intake tests. |
| [Selected workflow and EWAF regression](regression-tests.log) | **426 passed in 200.227 seconds**, zero failures/errors/skips. Includes the same 18 new tests, existing intake/membership/member, Phase 2A lookup, private storage, account/permission, program workflows and **102 existing EWAF tests**. |

The counts overlap; do not add the focused run to the 426. These are newly executed results, not the earlier 410-test implementation count. Both commands used the unchanged launcher/runner and ended exit 0:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.test_registration_finish membership.test_registration_intake --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 2

.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.tests membership.test_reference_retrieval membership.test_onsite_profile membership.test_confirmed_requirements membership.test_registration_intake membership.test_registration_finish members.tests documents.test_storage accounts.tests.test_accounts accounts.tests.test_authority_generation programs.tests programs.test_revised_workflow programs.test_workflow_alignment ewaf.test_computation_reference ewaf.test_four_criterion_reference ewaf.test_ahp_validation ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_four_kernel ewaf.test_operational ewaf.test_delivery ewaf.test_membership_writers ewaf.test_access_writers --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 2
```

Before setup, G12 verified a fresh temporary loopback MySQL datadir/port, disabled `.env` loading and restricted synthetic database grants. The runner reverified instance identity, `test_g12_disposable`, InnoDB, READ-COMMITTED isolation and separate temporary private media. There was no normal-database fallback. Baseline test tables were synchronized from models; **zero migration files were applied or reversed**. No migration test was selected.

Both runs used MySQL 8.4.11. Final instance: temporary `santolan-g12-tests-nqo1fxtp`, port **65435**, server UUID `3d4e7846-cef2-11f1-b105-581122e63603`; private media `phase2b-private-media-s7jfk17q` inside that directory. The test database was destroyed, temporary test media cleaned and the launcher shut down its own server. Restricted synthetic diagnostic artifacts remain under the logged Temp locations. [Verification evidence](verification.json) retains exact identities, commands, log hashes, test identifiers and outcomes.

New tests cover separate exhausted address/session budgets without resetting either; repeated HTTP/service requests; preserved revocation timestamp; CSRF and POST-only behavior; paused/removed/changed policies; expired contexts; generic no-context closure; posted-identifier tampering; foreign/malformed identifiers before and after revocation; tampered server-session pointers; refusal to revoke staff-assisted contexts; shared-browser reuse; receipt/form/file denial; audit rollback/retry; unsubmitted context closure; and concurrent exactly-once revocation. The guard tests cover membership 0006 rejection, disabled-feature rejection and unchanged existing deferrals.

Python syntax, document links, Git whitespace and preservation checks also passed. Not run: full repository suite, browser/screen-reader/UAT, load testing, working/production database inspection or actual startup, migration application/history/post-migrate rehearsal, backup/restore or membership handoff. No UI change was made and old screenshots were not reused as new validation.

## Startup diagnosis and recommended resolution

The owner's reported pending `membership.0006_association_pending_intake` is outside `runlocal`'s explicitly fingerprinted deferral list, so the unchanged guard stops before opening the website. Disabled registration flags do not alter the migration plan. This task did not query working migration history or attempt startup.

The recommended recovery is **reviewed application of only membership 0006 after exact dependency/history, metadata and backup/restore rehearsal, followed by separate owner authorization for the identified database**. Its file SHA-256 remains `fc897f9ee2f2f1b2433cccc7bf7f6bd531c199363f0cfa5fe2bdcfb9583b224d`. See the [exact startup recovery proposal](startup-recovery-procedure.md) for gated preflight, target-plan checks, conditional commands, validation and partial-DDL recovery requirements.

No migration was generated, applied, reversed, edited or faked. No allowlist/guard modification or alternate-launcher bypass was made. A new deferral policy would require separate authorization and schema-absent route/session analysis; it is not the recommended change for this task. Schema readiness still does not activate collection or settle institutional policy.

## Preservation and remaining limitations

All **267 protected files** and **58 migration files** (57 prior boundary files plus registration 0006, including migration-package files) match the captured baselines. The startup guard and source specifications remain unchanged. Original/integrated EWAF Section 8 is still byte-identical, **8,384 bytes**, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. The protected-file diff is empty; [verification.json](verification.json) records the exact application changes and hashes.

The 102 executed unchanged EWAF tests exercise criterion/formula versions, AHP/CR checks, normalization/scoring, missing/stale inputs, complete pools, ties, decisions/publication/releases and membership/private-access source writers. This is selected regression evidence, not a full-suite or institutional acceptance claim. No calculation is added to registration or Finish.

Remaining limitations:

- Revocation requires the existing browser session, valid CSRF and functioning database/audit storage. An audit failure rolls back and returns an error; it does not falsely display success. The application cannot retract a response/file already delivered, a printed copy or a saved download. Browser/device custody remains an operational responsibility.
- Finish grants no recovery capability. Lost sessions cannot select an arbitrary reference for closure or retrieval. Shared-device testing used Django HTTP clients and database concurrency, not a new real-browser cache/device test; approved browser/device/UAT coverage remains outstanding.
- Exact operational timeouts, budgets, upload limits, proxy handling and pause/receipt-access policy remain unapproved. Closure now works during a public pause, but the public gate still stops new acceptance and receipt output together; no separate receipt-continuity feature was implemented.
- The earlier readiness finding about exhausted-budget Finish is resolved by this correction. Other readiness items remain: normal migration history/post-migrate/startup rehearsal, accepted onsite/assessment evidence, safe membership handoff and copied-legacy permission integration. Old reports retain their dates and original findings.

## Remaining Phase 2B approvals and stop

Association/client approval is still required for field purpose, qualifications, original/copy/scan/alternative handling under OQ-27, identity/representative/cross-channel/correction procedures, legitimate control-number/manual PRPWD relationship, required socioeconomic assessment and membership decision responsibilities, named staff assignments, privacy/retention/custody/incident handling and assisted instructions. PDAO authority and transfer handling remain separately deferred.

Project-owner review is still needed for exact security configuration, any remaining integration/schema changes, migration recovery/rehearsal and separately scoped working access/application, grants, operational enablement or production deployment. This security correction supplies none of those approvals. Membership handoff remains refused by its service and NULL-link database constraint. Public registration remains unconfigured/disabled; PDAO and Phase 3 remain unavailable.

**Stop after this report. No registration activation, working migration, Phase 3, commit, push, merge or deployment is authorized automatically.**
