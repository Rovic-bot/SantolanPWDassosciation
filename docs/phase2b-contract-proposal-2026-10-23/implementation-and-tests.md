# Ordered Phase 2B implementation and validation plan

2026-10-23. **Plan only. No step below has been executed as application development.** The [approval register](approval-register.md) determines which subset can be authorized. Work remains inside Phase 2 of the existing five-phase plan; Phases 3–5 and institutional acceptance remain separate checkpoints.

## 1. Dependency and implementation order

| Order | Proposed work after explicit authorization | Required decision/evidence and stop condition |
|---|---|---|
| 1 | Recheck actual branch/HEAD/worktree and governing decisions. Capture new protected/source/test hashes. Select the approved category/action subset. Preserve all Phase 2A and unrelated changes. | D13; no reset to a documented checkpoint. No assumption that a later checkout matches this proposal. |
| 2 | Finalize approved form/checklist/privacy versions, field schema, state/permission matrix, references, limits and retention dependencies. Specify unavailable routes/actions for every missing dependency. | D01–D11 as applicable. No fixture values may become ordinary settings or implicit policy. |
| 3 | Prove the membership bridge design using isolated synthetic test scaffolding: top-level service entry, unchanged protected locks/writers, in-service intake guard/link/audit, native audit count, retry and file ownership. | D04/D12 and explicit test scope. If protected changes are needed, stop handoff and retain independent intake work as partial. Do not relax engine assertions. |
| 4 | Implement only approved additive membership records/constraints and category capabilities. Generate only reviewed additive migration files if specifically authorized. | D12/D13. No existing model/migration/source-writer change is inferred. No migration application unless separately authorized for a named disposable environment. |
| 5 | Implement public pending submission service, request contexts, private attachment handling, retry/collision rules and same-context receipt/completed-form output behind server-side default-off gates. | D01/02/05/06/07/10/11 and category authority. Atomic acceptance, audited failure and cleanup must work before any usable route. No public tracker or attachment download. |
| 6 | Add Members category lists/search/detail, reusing Phase 2A patterns. Add permission-scoped document/render actions, append-only corrections and onsite findings. Retain legacy UUID and program retrieval unchanged. | D03/D05/D09/D12. No new sidebar group; no duplicated registration case in Applications & Verification. |
| 7 | Add the approved Association handoff, manual-review linkage and decision guard through existing services. Existing unlinked onsite workflow stays unchanged. | D02/03/04/09/D12; compatible actual requirement configuration must be established. Missing physical/file mapping or approved identity path blocks this feature. |
| 8 | Only if independently approved, implement Association-side PDAO review and manual forwarding facts. Retain separate collection/review/forwarding gates. | D08/D09 plus applicable data/security decisions. No automated transmission/ID issuance, government approval, membership creation or program substitution. |
| 9 | Run targeted failure/concurrency/privacy tests, existing regressions and accessible synthetic browser journeys. Review protected diff and scope. | Verified disposable isolation first; actual commands/versions/fixtures/time/results retained. No normal database fallback. |
| 10 | Update development/Obsidian status and staff instructions, report Pass/Fail/Blocked/Not Tested, demonstrate only permitted synthetic flows, and stop for owner review. | Do not imply production activation, UAT completion, WCAG certification or acceptance beyond the existing 70%. |

## 2. Proposed additive migration plan

This turn creates **zero migration files** and executes **zero migrations**. Inspect actual leaf nodes again at implementation time. Current inspected membership leaf is `0005_onsite_profile_capture`; documents leaf is `0004_onsite_profile_capture`. Do not renumber, rewrite or edit either.

Recommended first additive migration in `membership` (candidate successor name only) creates the five proposed records, with the swappable user dependency and existing membership leaf. `RegistrationAttachment` owns its private file and requirement key, so **no new documents-model migration is presently required**. Use the existing storage/validator components by reference. There is no new dependency on EWAF, optional `program_intake`, program applications or deferred schemas.

Suggested creation order: submission context and intake; revision; attachment; action; then forward/circular references and constraints to accepted revisions/findings if needed. Django may split this into more than one new additive file after review; record the exact graph before authorization to apply it. The schema proposal uses `PROTECT` for retained record links and nullable staff FKs with retained actor labels consistent with existing history. It must not backfill, reinterpret or relink historical membership records.

Proposed technical field bounds for D12 review: external reference ASCII max 40; category max 16; state max 32; action code max 48; digest hex length 64; UUID request/context identifiers; positive integer revision/version; timezone-aware timestamps. Submitted-field types/lengths and private reasons/filenames follow the approved D01 schema and existing safe bounds, not unconstrained JSON or arbitrary-size text. Public values never set actor/version/state/authority fields. File/attempt/time limits are D06/D11 decisions, not this schema's defaults.

Add unique reference/request/context ownership constraints, one-to-one legacy membership link, category/state validity and Association-only legacy linkage checks. Add indexes only for the defined list/exact-lookup operations. Model validation and transactional services must enforce related-row invariants that MySQL CHECK constraints cannot. No unsupported partial/conditional unique constraint is assumed. Permission creation must not auto-assign broad grants to existing staff.

Upgrade/backward-compatibility validation needs separately authorized disposable migration execution. A model-synchronized test schema can exercise application behavior but **cannot prove migration correctness**. Never run a blanket migration command, change startup migration guards, enable deferred schemas, or fall back to normal settings to get a screen working.

## 3. Proposed gates and disable strategy

Names below are descriptive proposals, not settings created this turn:

| Independent gate | Dependencies | Disable behavior |
|---|---|---|
| Association public pending submission | Approved form/documents/privacy, references/idempotency/context output, limits/storage and scoped authority | No new public acceptance; direct GET/POST cannot bypass. Existing authorized staff can still review retained cases when separately permitted. |
| PDAO public pending submission | All common requirements plus current office/form and collection authority | PDAO intake unavailable; Association route cannot accept a tampered PDAO category. |
| Submission-context form output | D06 approved security parameters and accepted context ownership | Generic refusal, no reference-only fallback. Pausing new submissions need not revoke existing valid output contexts unless the separate security gate is closed; document exact policy. |
| Staff new-category retrieval/review | Category authority/permissions and schema available | Direct list/detail/document/export routes fail closed. Existing Phase 2A lookup of legacy records remains unaffected. |
| Association handoff/linked decision | Accepted current onsite findings, identifier/configuration compatibility and D12 proof | New linked-case decision cannot use a legacy route to bypass the gate; ordinary unlinked onsite decisions remain unchanged. |
| PDAO forwarding facts | Approved reviewer/recipient/transfer procedure and actual facts | No forwarding mutation, even if PDAO intake/review is allowed. |

No “all new features” switch or legacy `MembershipSettings.registration_open` flag should imply these approvals. Runtime checks require the relevant approved configuration/version and capabilities; missing dependencies keep the action unavailable. Gates do not override existing ordinary-mode operating restrictions.

Disable first by stopping new acceptance/mutations while retaining appropriately authorized read access, audits and pending work. Retained records must not disappear or be relabeled as completed. Revoke output contexts when security requires it, with approved generic assistance text. Keep old URLs/references and historical private files intact.

Database rollback after real records exist is **not** “reverse the migration and delete the tables.” Prefer disabling the extension and retaining additive records until a separately reviewed recovery/disposal plan is authorized. Record storage orphans, linked file copies and backups in that plan. An older application version might lack the linked-intake guard: never roll back to an unguarded approval path with linked cases present. Require guarded compatibility or freeze those actions before any separately authorized rollback. No backup/restore or rollback command runs in this contract review.

## 4. Isolation before future tests

Reuse `scripts/g12_test_runner.py`, the durable isolated runner and Phase 2A's `scripts/reference_retrieval_test_runner.py` patterns. Review them at the actual implementation revision before use. The ordinary launcher, `manage.py check --database default`, normal migration commands and working configuration must not be used for this task.

1. Disable `.env` loading and explicitly select the isolated settings/runner. Record code revision plus uncommitted-file hashes, Python/Django/MySQL versions, exact command and UTC timestamps.
2. Create a fresh loopback MySQL instance with verified temporary datadir, unique port/server identity and distinct disposable `DB_TEST_NAME`; verify it is empty and different from working data **before setup writes**. Use only restricted test credentials from the launcher; do not alter existing credentials.
3. Use a separate verified temporary private-media directory and synthetic people/documents/permissions. Check that every storage backend and external-call stub points to isolated resources. Mock external PDAO/registry links without contacting live services or inventing government status.
4. If migration execution is not specifically authorized, use the no-migration runner and block application/reversal. Required synthetic reference labels are fixtures, not newly approved policies. If approved upgrade tests are requested, run only the reviewed migration plan against a separately verified disposable instance; label those results separately.
5. Abort on missing identity checks, unavailable MySQL/media path or any normal-database fallback. Save sanitized commands/results and cleanup outcome. Do not start a normal project server to fill a gap in disposable browser tests.

An enrolled source-writer compatibility test must use an already authorized disposable operating contract; tests must not enable deferred production behavior. Existing non-enrolled and enrolled service behavior both remain protected. Test failure is evidence for deferral, not permission to bypass the writer.

## 5. Targeted tests and acceptance trace

IDs T01–T20 are **planned cases, not executed tests**. Each eventual report must distinguish Association and PDAO outcomes, blocked categories and unrelated portions of broader acceptance criteria.

| Test | Synthetic case and required outcome | Source trace |
|---|---|---|
| **T01** | Each approved online form creates only its category's pending intake/revision/reference/audit; rejected validation creates no successful receipt/Member. Tampered trusted fields/category and unknown form fields fail. | BF-01/02; BR-A01–03; AC-B01 |
| **T02** | Required/optional slots and exact Birth OR Marriage alternatives work; photo sizes/guidance stay category-specific; physical envelope has no file requirement. PDAO residency alternatives never replace Association Voter's Certificate. | BF-01/02; OQ-27; AC-B01/04 |
| **T03** | Correct authenticated category reference finds the intended form; legacy UUID normalization/status lookup and program references continue to work; invalid/partial input cannot broaden query. | BF-03; BR-A04; AC-B02 |
| **T04** | Anonymous, inactive, nonstaff, wrong-category, missing-view, revoked and direct identifier-tampered requests cannot retrieve form/history/export/documents. Test copied legacy rows through their old UUID/list/document routes too: both applicable permission scopes remain required. Generic absent/inaccessible outcomes do not reveal existence. | BR-A04/18; AC-B02 |
| **T05** | Document permission is separate; revocation checked on each request; untrusted extension/MIME/header/path, oversized/empty/multiple files and invalid portraits rejected. No unrestricted media URL or unsafe active preview. | §12.6; AC-B02/13 |
| **T06** | Same bound request/payload, double click, network retry after commit and concurrent duplicate POST return the one accepted intake/reference. Changed payload or another session cannot overwrite/recover it. Different legitimate applicants sharing contact/name remain distinct. | IQ-10; AC-B01/03 |
| **T07** | Forced UUID collision retries within approved bounds or fails cleanly; no program counter or historical reference changes. Duplicate request versus reference collision branches behave separately. | IQ-10; OQ-17/21; AC-B01/14 |
| **T08** | Same-context form output contains only the original submitted revision; wrong/expired/revoked session, guessed reference, cross-context request and stale context fail. No private attachments, later findings, public tracker or URL bearer secret. | BF-03; BR-A04/18; IQ-10; AC-B01/02 |
| **T09** | Online-plus-print after approved identity review records presentation against the same intake; blank printed/walk-in capture follows approved duplicate checks and evidence requirements. No silent merge or auto-close. | BR-A01/05; AC-B03 |
| **T10** | Missing/unclear onsite findings or unapproved alternative block handoff; correction appends a revision, preserves files/history, invalidates affected readiness and rejects stale staff writes. | OQ-27; AC-B03/04/06 |
| **T11** | Handoff fails without legitimate identifier/valid legacy form/permissions; successful handoff links exactly one pending membership application and creates no Member. Retry and concurrent handoff cannot duplicate link/member. | BR-A02; IQ-10; AC-B04 |
| **T12** | Existing decision endpoints cannot approve a linked case without current onsite guard, actual manual PRPWD and required evidence; view-only staff cannot decide. Approved existing service creates one Member; unlinked legacy forms/decisions remain compatible. | BR-A02/04; AC-B04/14 |
| **T13** | Top-level writer calls in ordinary and enrolled isolated modes preserve lock order/native audits; failed audit/link/file/save rolls back appropriate operation. A failed later review leaves truthful pending state. No nested-transaction workaround, direct Member write or forged source token. | §8 protected boundary; AC-B04/14 |
| **T14** | PDAO collection/review/forwarding gates checked independently; only authorized factual forwarding succeeds, with real synthetic transfer evidence. Renewal is unavailable unless scoped. No ID issuance/government decision/membership/program/release/PA side effect. | BF-02; BR-A02/11; IQ-09/16; AC-B04/06 |
| **T15** | Readiness is not approval/appointment; only actual assigned appointment information could display. Public tracking/routes remain unavailable; receipt/full form cannot retrieve later states by reference alone. | BR-A18; IQ-03; registration portion AC-B06 |
| **T16** | State/audit failure, storage write/cleanup failure, permission revocation race and concurrent stale actions fail safely. Download audit failure blocks delivery. Retried cleanup affects only verified orphan files, not linked legacy evidence. | §12.6; AC-B01/02/04 |
| **T17** | Retention/disabled-feature configuration rejects unset dependencies. Unauthorized terminal/reopen/withdrawal/duplicate-closure actions fail; no automatic deletion or public recovery appears. | OQ-16/27; IQ-03/12; AC-B04/14 |
| **T18** | Keyboard/error recovery, screen-reader labels/status, visible focus, measured contrast, 200% text and zoom/reflow/mobile, upload/print/save, controllable reading aloud and assisted/text-reference alternatives. Record actual tools/versions and untested combinations. | BF-11; BR-A17; AC-B13 |
| **T19** | Re-run current Phase 2A retrieval/private-storage/account/membership/member/program regressions plus appropriate new cases. Existing forms/reference/history snapshots unchanged by searches; no new public leakage or altered eight-group navigation. | BR-A04/05/18; AC-B02/03/14 |
| **T20** | Existing EWAF reference/operating regressions preserve criterion versions, strict CR, bounds/directions, missing/stale inputs, complete pool, exact ties/no business rank, decisions/capacity, publication freshness and actual-release/PA/history behavior. Identical accepted inputs/configuration yield baseline behavior. No auto calculation from intake/correction. | Section 8; AC-B14 |

Future commands must select actual test modules present at the implementation revision. The full exact **earlier** 352-test command is retained in the [Phase 2A report](../phase2a-reference-retrieval-2026-10-23/README.md); do not paste a new label onto its result or assume its explicit selection covers new files. Add targeted `TestCase`/`TransactionTestCase` tests and browser cases for the approved scope without editing existing assertions to accept changed EWAF behavior. Broader regression is warranted after implementation, with exclusions reported.

AC-B01–04 are not all satisfied if PDAO or handoff is blocked. AC-B06 here covers internal registration semantics only; protected public tracking belongs to Phase 3. AC-B13 here covers new intake/retrieval journeys only, not calendar/resources/review features. AC-B14 requires newly executed regression evidence after code changes; document hashes alone do not pass it. AC-B05/07–12 and remaining BF features stay assigned to their original later phases or explicit deferrals in the Phase 1 traceability plan.

## 6. Current-turn validation and exit

This contract turn ran source/code reads, Git status/diff inspection, hash and exact Section 8 comparisons, documentation-link/decision/test-ID checks and `git diff --check`. It ran **no Django application tests, database checks, migration generation/application, browser flow or production command**. The [verification record](verification.json) contains the actual results and the minor baseline-capture diagnostic error; no test success is inferred from that diagnostic.

Exit is a concrete proposal plus open approvals, not enabled intake. Retain the baseline/protected manifest, prior test evidence and single progress record. Obtain owner decisions on D01–D13 or an explicitly limited subset, keep D14 deferrals visible, then stop. No automatic next phase, accepted milestone change, commit, push, merge or deployment.
