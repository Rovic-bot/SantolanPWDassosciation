# Phase 2B — Association registration foundation

2026-10-23. **Status: Partial.** The independently implementable Association foundation is implemented and synthetically tested. **No new public/staff intake feature is activated in ordinary settings.** Institutional collection/evidence/retention/assignment decisions and exact security parameters remain open; required socioeconomic assessment and membership handoff are blocked. PDAO and all later-phase features remain unavailable. Owner technical approval of D01–D14 is recorded separately from institutional approval in the [approval register](../phase2b-contract-proposal-2026-10-23/approval-register.md).

The accepted milestone remains **70%**. Historical G-stages and the five-phase plan are unchanged. No working/production database, existing credential, deployment configuration, commit, push or merge was changed.

## Implemented Association-only features

- A gated pending form with name, birthdate, residence, optional contact and notice/accuracy acknowledgement. It presents the original five Association requirements, mandatory onsite instructions and reviewed privacy text before acceptance. No post-approval number, government-ID prerequisite, Household Monthly Income or new program-matching fields are introduced.
- Five separate pending-intake records: submission context, intake, original/correction revision, private attachment and action history. No official Member, existing membership application, program application, government ID, assistance release or EWAF calculation is created on submission.
- Immutable `AMR-<UUIDv4>` references, unique request/context ownership, accepted-payload/attachment fingerprints and row locking. Identical same-context retries return the same intake; changed payloads conflict. Reference collisions use an explicit configured bounded retry budget. Different real requests are not automatically merged based on name/contact.
- Original-form receipt and print/save output bound to the submitting browser session, with explicit Finish/revocation. No reference-only access, public attachment access, later status/reasons, public recovery, PIN/OTP or member account. Submitted receipt remains the original revision after staff corrections.
- **Members → Membership Reviews → Pending Association registrations** with exact AMR reference search, type/channel/date/state, canonical private detail and history. Existing Phase 2A UUID retrieval and program reference search remain intact. A separate authorized completed-form print screen excludes private review notes/history.
- Staff encoding for blank printed/walk-in forms, gated matching of a presented online printout to its retained record, possible duplicate prompts for authorized human review, retained revisions and attachments, stale-version checks and transactional review/audit changes.
- Review states `received`, `under_review`, `needs_information`, `ready_for_onsite`, `onsite_review`. Readiness and onsite observations require their own approved procedure gate. Sighted is not authentic/current/registry-verified or approved. Corrections require a separate approved correction procedure and return the case to review without overwriting prior findings.
- Separate form/document/action permissions, repeated fresh authorization before audit writes/delivery, CSRF, escaped/bounded form fields, private file validators/storage, no-store attachment responses and rollback cleanup. Ordinary configuration supplies no invented security values.
- Shared minimalist templates, keyboard/error semantics, responsive forms/receipts and existing controllable reading/display components. No sidebar redesign, physical kiosk, new Public destination or additional login role.

## Disabled and blocked features

Public form acceptance/receipts and the new staff inbox/actions remain unavailable without a complete reviewed configuration and actual staff assignments. Onsite and correction procedures have independent gates. Source code and screenshots do not establish institutional acceptance or operational availability.

**Membership handoff is intentionally not implemented:** Association control-number meaning/allocation, OQ-27 accepted evidence/original-copy handling, the manual PRPWD relationship and required socioeconomic assessment need a valid approved path. The service refuses handoff; a database CHECK requires the future membership-application link to remain NULL. Do not copy a pending record manually into the legacy approval path to bypass this dependency. Existing authorized onsite membership services were preserved and regression-tested, including their top-level transaction/source-writer contract.

PDAO collection/review/forwarding/renewal and issuance remain absent; the new category CHECK permits Association records only. Public tracking/recovery/corrections, QR, member accounts, notifications, new socioeconomic measures, terminal reopening/closure remedies, routine review intervals/sampling, altered public result identifiers/ranks and all Phase 3 work remain excluded. No setting can activate PDAO or handoff in this delivery.

See [configuration and operations](configuration-and-operations.md) for every unset dependency, staff capability, disable behavior and approved-versus-fictional distinction.

## Exact application files

| File | Change |
|---|---|
| `membership/models.py` | Imports/registers only the five additive models; existing model fields remain unchanged. |
| `membership/registration_models.py` | New pending context/intake/revision/attachment/action models, immutable-history service guards, unique ownership and restrictive category/handoff constraints. |
| `membership/registration_policy.py` | Validates a separately reviewed settings mapping; all public/staff/onsite/correction gates default unavailable. No operational numeric defaults. |
| `membership/registration_forms.py` | Minimum pending form, optional approved upload slots, review form and approved-method onsite observation form. |
| `membership/registration_services.py` | Atomic acceptance/retries, private file cleanup, staff checks, retained corrections/actions, explicit handoff refusal and scoped receipt access. |
| `membership/registration_views.py` | Gated public session interaction, Members inbox/detail/printed/walk-in/review/onsite/form-print routes and private attachment delivery. |
| `membership/urls.py` | Namespaced extension routes; existing routes retained. No public reference tracker, recovery, PDAO or handoff endpoint. |
| `membership/views.py` | Adds availability flags to existing guidance/list context only in this phase. Its pre-existing Phase 2A UUID-search code is retained. |
| `templates/membership/list.html` | Conditional authorized link to the new inbox; Phase 2A search retained. |
| `templates/membership/guidelines.html` | Conditional pending-intake link/wording only when enabled; ordinary guidance stays onsite-only. |
| `membership/migrations/0006_association_pending_intake.py` | Single reviewed additive migration creating five tables and their new-table constraints/indexes/relationships. |
| `static/css/registration.css` | Scoped wrapping, receipt/form width and print treatment. Existing shared styles remain unchanged. |
| `static/js/registration.js` | User-initiated browser print control only. |

New templates under `templates/membership/registration/`:

- `apply.html`: pending form/checklist/notice/onsite/session instructions.
- `fields.html`: shared labels, errors and accessible error summary.
- `receipt.html`: original submitted-form receipt and Finish action.
- `submitted_data.html`: explicit minimum-field projection.
- `unavailable.html`: generic disabled action/onsite guidance.
- `finished.html`: confirmation that session access is closed while pending data is retained.
- `inbox.html`: exact reference search and pending-record list.
- `detail.html`: private review/history/retained revisions and permitted evidence links.
- `staff_form.html`: printed/walk-in encoding and assisted correction forms.
- `onsite.html`: approved-method observations, separate from PRPWD/assessment/approval.
- `completed_form.html`: authenticated print/save view without private reviewer notes.

New tests/tools: `membership/test_registration_intake.py`, `membership/test_registration_migration.py`, `scripts/registration_intake_test_runner.py`, `scripts/registration_intake_browser_qa.py`, `scripts/registration_intake_browser_qa.cjs`. Existing assertions/tests and Phase 2A helpers remain unchanged. Documentation/evidence lives in this directory; only the existing approval register and single progress record receive prepended updates. Original content is preserved verbatim.

## Schema and disposable validation

[Exact schema review](schema-review.md) records the contract/dependency comparison. Migration dependencies are `membership.0005_onsite_profile_capture` and the swappable user model. There is no new EWAF/documents/program migration, schema backfill, existing-row rewrite, dependency upgrade or production setting. Offline autodetection reports no model/migration difference and explicitly blocks database connections.

The test runner reused the existing G12 fresh-instance launcher. It verified loopback host, new temporary datadir, separate test database, instance identity, `.env` disabled, restricted synthetic credentials, READ-COMMITTED isolation and InnoDB. Separate temporary private media held synthetic uploads. Isolation failure has no normal-database fallback.

Final run: MySQL **8.4.11**, database `test_g12_disposable`, port **55057**, server UUID `4444d2b3-cee9-11f1-abb7-581122e63603`, datadir `C:/Users/rovic/AppData/Local/Temp/santolan-g12-tests-udw69kin/data/`. Media path, timestamps, versions, commands and hashes are in [validation.json](validation.json). The final test database was destroyed and the launcher shut down its own server. No working/production service was started or changed.

**No blanket or historical migration execution occurred.** Baseline test tables were synchronized from existing installed models. The dedicated migration test removed only the five empty extension tables using the new migration's reverse operations, then applied that exact new migration to the disposable baseline. It preserved a synthetic legacy membership row and tested the Association-only and no-handoff constraints. This happened once in each of the targeted-migration, intermediate regression and final regression runs: **three applications and three reversals of the one new migration across three disposable instances**, none against working data. No prior migration was altered/applied/reversed.

This validates the additive migration against a model-derived baseline, **not every historical migration/upgrade path**. Existing eligibility labels needed by old tests were supplied by the existing synthetic fixture helper; they are not new policy. The startup migration guard remains unchanged and may report the unapplied migration on the working installation; do not bypass it or apply migrations automatically.

## Actual test results

**Final selected suite: 410 tests passed in 240.773 seconds; zero failures/errors/skips.** Included: 39 new pending-intake tests, one new additive-migration test, one new Chrome integration test, the 13 existing Phase 2A retrieval tests, and **102 existing EWAF tests**. The EWAF count comprises the earlier 84 focused formula/operating cases plus 12 membership-writer and 6 private-access-writer cases. All counts overlap with the overall 410; do not add earlier runs to it.

The final command was:

```powershell
$env:PLAYWRIGHT_MODULE = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$env:CHROME_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.tests membership.test_reference_retrieval membership.test_onsite_profile membership.test_confirmed_requirements membership.test_registration_intake membership.test_registration_migration members.tests documents.test_storage accounts.tests.test_accounts accounts.tests.test_authority_generation programs.tests programs.test_revised_workflow programs.test_workflow_alignment ewaf.test_computation_reference ewaf.test_four_criterion_reference ewaf.test_ahp_validation ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_four_kernel ewaf.test_operational ewaf.test_delivery ewaf.test_membership_writers ewaf.test_access_writers scripts.registration_intake_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 2
```

Full output: [final regression log](regression-tests-final.log).

| Earlier attempt | Actual outcome, retained separately |
|---|---|
| First targeted sandbox attempt | Failed writing the fresh MySQL configuration under Temp before test/database setup; zero tests. |
| Authorized targeted run | 35 tests passed in 1.796 seconds. |
| First targeted+migration sandbox attempt | Same sandbox Temp-write denial before tests. |
| Authorized targeted+migration run | 37 tests passed in 34.142 seconds, including the exact new migration. |
| Initial browser run | 1 test passed in 13.417 seconds; 32 viewport checks. |
| Intermediate selected regression | 408 tests passed in 228.546 seconds. |
| Final-review hardening check | 3 concurrency tests passed in 1.335 seconds, including revocation during an in-flight review. New extension code rechecks permission before audit/delivery. |
| Final selected regression | 410 passed as above, including hardening and conditional guidance tests. |

There were no observed application-test failures to conceal or engine changes to obtain passing results. The two sandbox failures and all intermediate logs remain retained. Python syntax, JavaScript syntax, offline model/migration consistency and Git whitespace checks passed.

Not run: the full repository suite; historical migration suites (`membership.test_profile_migrations`, `members.test_catalog_migration` and EWAF migration-history suites); live-data/production tests; backup/restore; complete new-record-to-official-Member journey; actual institutional PDAO procedures; representative screen-reader sessions; measured contrast audit; performance/load benchmarks; institutional UAT. Existing Phase 2A browser artifacts were not overwritten or presented as new results; the new browser harness captures new evidence in this directory.

## Security, privacy, duplicates and accessibility

Fresh synthetic tests exercised same-context identical retries, changed-payload rejection, reference collisions/exhaustion, concurrent acceptance, stale/concurrent review, mid-request permission revocation, separate document rights, malformed/unknown/repeated/oversized uploads, CSRF, absent/expired/revoked sessions, audit/storage failure and private-file cleanup failure. Failure prevents acceptance or delivery as applicable. Private receipt output excludes later corrections and staff reasons; authorized staff printing also excludes private notes. Direct unauthorized identifiers/documents and reference-only receipt attempts fail.

Only request replays are automatically deduplicated. Different requests for a possible same person remain human-review cases; similarity is not identity proof. The stronger guarantee here is **zero new Member creation**, plus unique request/context/reference records. Full same-person reconciliation and membership handoff remain institutional dependencies, not delivered guarantees.

Chrome **156.0.8078.47** passed **32 layout checks** across eight new screens at 320/390/768/1440 pixels, keyboard submission/reference retrieval, form-error semantics, authorized file delivery, submitted-revision preservation, print-button/print-CSS behavior, shared-device Finish and forbidden-route checks. A receipt at 390 pixels with 200% root text size had no document-level horizontal overflow. No unexpected console/page errors occurred; the expected HTTP 400 validation response is separately recorded. Existing tables may scroll within their focusable region. No WCAG certification is claimed; existing reading controls were reused, not fully assistive-technology certified.

Synthetic UI evidence: [public form](ui/public-form-desktop.png), [receipt](ui/receipt-desktop.png), [enlarged mobile receipt](ui/receipt-mobile-200percent.png), [staff inbox](ui/staff-inbox-desktop.png), [review history](ui/staff-review-history.png), [browser checks](ui/checks.json). The permission-filtered screenshot shows only groups available to that synthetic staff user; the eight-group sidebar implementation is unchanged.

## EWAF preservation and requirement disposition

All **267 protected files** and **57 existing migration files** match the captured baseline. Original/integrated Section 8 remains byte-identical, **8,384 bytes**, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. Governing source hashes remain unchanged. [Preservation evidence](preservation.json) records exact changed/new files and prior-evidence checks; the original Phase 2A worktree changes were not reset or discarded.

The 102 executed existing EWAF tests preserve their assertions and cover criterion/formula versions, strict CR, bounds/missing/stale inputs, complete pool, exact ties, configuration/decision/publication/release controls, membership source-writer ordering/audits and private-access invalidation. Document hashes alone are not behavioral proof, and targeted tests are not full EWAF acceptance. No EWAF model, migration, algorithm, parameter, source service, operating gate, rank or PA rule changed.

| Requirement | Actual disposition |
|---|---|
| BF-01; BR-A01–03; Association part of AC-B01 | Association pending form, reference, retained record, receipt/inbox and failure/retry behavior implemented and tested synthetically; ordinary activation blocked. |
| BF-02; PDAO parts of AC-B01/04 | **Blocked/deferred.** No PDAO intake, government processing or forwarding activation. |
| BF-03; BR-A04; AC-B02 | Association new-reference staff retrieval/private form/document boundaries tested; legacy Phase 2A tests pass. PDAO portion remains blocked; QR omitted. |
| BR-A05; AC-B03 | Printed/walk-in pending encoding and online-print reuse tested at service level; full authorized identity reconciliation remains gated. New browser journey exercises online/review/correction, not every paper/walk-in combination. |
| BR-A02; AC-B04 | Pending is never Member; DB/service handoff prohibition and existing legacy approval regressions pass. New intake → required assessment → official Member journey remains **blocked**, not complete. |
| Registration part of AC-B06 | Internal truthful received/review/information/readiness/observation states; no fabricated appointment. Public tracking remains Phase 3. |
| BF-11; BR-A17; AC-B13 | Targeted keyboard/responsive/error/print checks pass; broader accessibility/assisted-route/UAT acceptance remains **Not Tested/Blocked** as listed. |
| Section 8; BR-A11/18; AC-B14 | Protected-file/source checks and 102 current EWAF regressions pass; full repository/post-all-phases regression and institutional acceptance remain outstanding. |

## Benefits, risks and next checkpoint

The foundation retains submissions once per accepted request, provides controlled reference retrieval, and separates pending intake from membership approval. It offers a reviewable basis for later activation without changing approved EWAF behavior. No measured throughput, fairness or institutional acceptance improvement is claimed.

Known limitations/risks: real document collection still needs privacy/security authorization; saved copies cannot be retracted; no malware scanner was added; cleanup failure needs restricted manual follow-up; exact-match duplicate prompts cannot establish identity; context expiry/configuration changes can end applicant output access; retention/disposal and staff-account removal need approved handling for protected links; working startup will see the unapplied migration. The current public gate disables both new acceptance and receipt output, so operational pause/revocation behavior must be reviewed before any activation.

Remaining institutional approvals are D01 field purpose/acknowledgement, D02/OQ-27 document handling/alternatives, D03 identity/correction/onsite procedures, D04 control-number/manual-PRPWD/assessment path, D09 named staff assignments, D10 privacy/retention/incident/disposal, and D06/D11 exact security/operating parameters. D08 PDAO authority and D14 later remedies remain deferred. D05/D07 technical direction and Association-only D12/D13 scope were approved; they do not settle the missing institutional facts.

Before Phase 3: obtain explicit new-scope authorization and IQ-03's allowed tracking fields, independent access controls, QR/recovery/correction contract; settle applicable review/freshness and terminal-remedy policies (IQ-08/12) and service dependencies. Do not infer that the current session-bound submitted-form receipt is a public tracker or that an application reference is a credential.

The [single progress record](../added-targets-phase1-2026-10-23/progress-and-decisions.md) is updated for safe resumption. **Stop after this report. No Phase 3, activation, working migration, commit/push/merge or deployment is authorized automatically.**
