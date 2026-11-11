# Stage 8 consolidated disposable development validation

2026-10-19. **Accepted milestone remains 70%; owner review is required.**
Operational scoring, ranking, selection, release and publication remain disabled.
No application database was opened or migrated. No migration or production
settings change was made. Development-only promotion is now available solely
inside the verified disposable session; it is not an operational current result.

## Outcome and boundary

The sprint adds the remaining supported source-writer fences, a complete-pool
generation-aware development promotion service, separate four-criterion AHP and
fictional workflow demonstrations, and private development pages using the
existing Admin layout. The five-criterion historical engine and all previous
regression assertions remain unchanged. One existing photo-test fixture prepares
its guarded reference before session registration. The four-criterion proposal is still inactive and
explicitly `BLOCKED_POLICY`.

This completes the bounded implementation and validation described below, not
Association policy approval or automatic Stage 8/80% acceptance. Four-criterion
durable operational configuration, real functional-need assessment policy,
deployment and unrestricted external-writer protection are not claimed.

## Workspace and preservation

- Branch: `feature/events`.
- HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
- Baseline captured before edits: 591 file/hash entries, including existing
  tracked, untracked and staged work. No baseline path was removed.
- Staged index SHA-256:
  `731c74ba7d747938181fbc4140139120a01c4ac5d676ac9607f3ff30ef718338`.
- Staged binary diff SHA-256:
  `64b8c580177e3d43c8c4fa863df77e81193c66a95071b4508f0f25b28e0fded6`.
- All existing test files except that photo fixture, all migrations, eight generation model definitions, numerical
  engines, four-criterion reference, Gate 1 capture/source digests, prior writer
  adapters, Events/annual-observances implementation, templates outside the
  explicitly listed EWAF link, and production configuration retain their hashes.
- DocumentType/DisabilityType method guards changed; their database fields did
  not. Generation services support the new versioned contract while preserving
  old sidecar records. Old foundation bindings still cannot promote.
- The review package contains a baseline-relative patch, exact current sources,
  hashes and unchanged reference dependencies, not an older remote checkout.
  No Git staging, commit, push, merge, reset, stash, clean or pull was performed.

### Exact affected-file inventory

<!-- INVENTORY_START -->
| Status | Path |
|---|---|
| Modified | `assistance/services.py` |
| Modified | `documents/admin.py` |
| Modified | `documents/models.py` |
| Modified | `documents/services.py` |
| Modified | `ewaf/durable_services.py` |
| Modified | `ewaf/evidence_services.py` |
| Modified | `ewaf/generation_services.py` |
| Modified | `ewaf/scoring_services.py` |
| Modified | `ewaf/scoring_views.py` |
| Modified | `ewaf/test_photo_writers.py` |
| Modified | `ewaf/urls.py` |
| Modified | `members/admin.py` |
| Modified | `members/models.py` |
| Modified | `members/services.py` |
| Modified | `members/views.py` |
| Modified | `membership/admin.py` |
| Modified | `membership/services.py` |
| Modified | `membership/views.py` |
| Modified | `programs/photo_views.py` |
| Modified | `programs/terms.py` |
| Modified | `programs/views.py` |
| Modified | `templates/ewaf/scoring_list.html` |
| New | `docs/stage8-consolidated-source-coverage-2026-10-19.md` |
| New | `docs/stage8-consolidated-validation-2026-10-19.md` |
| New | `ewaf/access_invalidation.py` |
| New | `ewaf/assistance_invalidation.py` |
| New | `ewaf/development_views.py` |
| New | `ewaf/diagnostic_invalidation.py` |
| New | `ewaf/four_criterion_development.py` |
| New | `ewaf/generation_inputs.py` |
| New | `ewaf/generation_processing.py` |
| New | `ewaf/generation_protocol.py` |
| New | `ewaf/member_invalidation.py` |
| New | `ewaf/membership_invalidation.py` |
| New | `ewaf/reference_invalidation.py` |
| New | `ewaf/shared_invalidation.py` |
| New | `ewaf/test_access_writers.py` |
| New | `ewaf/test_assistance_writers.py` |
| New | `ewaf/test_development_views.py` |
| New | `ewaf/test_four_development.py` |
| New | `ewaf/test_generation_processing.py` |
| New | `ewaf/test_member_writers.py` |
| New | `ewaf/test_membership_writers.py` |
| New | `ewaf/test_reference_writers.py` |
| New | `scripts/stage8_browser_qa.cjs` |
| New | `scripts/stage8_browser_qa.py` |
| New | `templates/ewaf/development.html` |
| New | `templates/ewaf/development_program.html` |
<!-- INVENTORY_END -->

Local-only review tooling and evidence reside in `.local/stage8-sprint/`:
baseline and before-copies, `inventory.py`, `collect_logs.py`, `build_review.py`,
sanitized logs, screenshots, fictional demonstration JSON, migration graph,
preservation/inventory manifests, patch, ZIP and SHA-256 file. These are not staged.
The baseline environment file/hash is excluded from the review ZIP.

## Source coverage and transaction evidence

The [coverage matrix](stage8-consolidated-source-coverage-2026-10-19.md) identifies
every participating family, scope, native audit, prohibited path and limitation.
New integrations were developed sequentially: membership, Member/document,
Assistance, reference/diagnostics, then conservative private-access audits.
Focused checks preceded the integrated regression runs.

All participating mutations enter before source locks and use the Gate 2A
prefix: Terms, global AuthorityGeneration, all affected Programs in PK order,
all SourceStates, Event when needed, Applications, Members, ordered leaves.
Cross-program Member and receipt scope comes from every retained application,
including closed/incomplete records. There is no caller-supplied scope authority.
Exact expected-token maps reject partial scope, stale generation/revision,
missing authority/state and inconsistent pointer values.

Business changes, existing native audits, SourceMutationBatch, exactly one
SourceInvalidation per affected program and conditional state updates commit
together. Pending membership intake has no program dependency and retains an
audited zero-program batch. Native audit sets and prior history are checked;
missing, duplicate, forged or wrong-scope evidence aborts the transaction.
Failure of a second program CAS undoes the first program update and the receipt.
Failed membership uploads remove only newly saved files. Retained evidence stays.

Real separate-connection MySQL tests cover membership review conflicts, complete
Member fan-out, release races, source writers during calculation, writers waiting
behind promotion and two competing accepted requests. The promotion race matrix
includes Member status, document verification, eligibility, reference Admin,
authority, program publication and cross-program release/void. Separate connection
IDs and blocking assertions are used where order matters; these are not mocks
of database locks. Prior photo, application and linked-event races run again in
EWAF/full regression. No global deadlock-freedom or production load claim is made.

## Complete-pool development protocol

1. A private registered session and fresh authorized actor are required. Missing
   bootstrap state fails closed. No request parameter or feature flag can create
   this capability, and ordinary requests do not query generation tables through
   the new adapters.
2. Under the shared fence, capture the entire retained application manifest,
   eligibility/evidence/configuration/authority dependencies and exact fictional
   test contract. Incomplete in-scope applicants block calculation; applicants
   after cutoff remain accounted for. The existing 128-applicant supported limit
   rejects the entire oversized pool instead of silently truncating it.
3. Accept immutable request and generation binding together. The binding records
   expected source/authority/revision/pointer, unchanged Gate 1 snapshot/digests,
   evaluation timezone and finite valid-until boundary.
4. Persist an attempt, release locks for numerical work, then reacquire the full
   fence and recapture sources. Require exact accepted dependencies, permissions,
   generations, complete results and criterion traces. Persist the immutable
   graph, completion, RunSourceBinding, DevelopmentPromotion audit and pointer
   revision CAS in one transaction; validate again before returning.
5. A stale concurrent request cannot promote. Failed graph/audit/CAS/final-time
   validation rolls back the entire graph/pointer; an authorized separate failure
   outcome records the failed attempt. Same-content current retries are
   idempotent. Interrupted attempts require explicit authorized recovery.
6. Replacement acceptance explicitly invalidates the former development pointer.
   Old requests, runs, bindings, traces and digests remain immutable. Failed
   replacement processing cannot silently restore the predecessor. Stale
   authority pointers can be explicitly replaced using a fresh current token.
7. Every protected current use checks source/authority, complete graph, current
   dependencies and expiry. Observed expiry clears the pointer with an immutable
   invalidation before returning the error, including completed retries/context
   reads. Rolling the clock backward does not resurrect it. Historical inspection
   reports historical integrity, not current usability.

Expiry is no later than the next evaluation-day midnight, shortened by future
program/event timestamp boundaries. Time can advance immediately after the last
check; the protocol promises validation at the protected use boundary, not an
indefinite lease. External SQL/ORM or filesystem tampering is outside the atomic
writer contract. Changed-and-restored **participating** sources are rejected by
monotonic generations even when their values match the original snapshot.

Legacy durable processing/current inspection explicitly refuses requests bound
to the new protocol, including when session registration is suspended. Historical
inspection remains available. Selection, release and publication do not consume
this pointer, and their previous restrictions are unchanged.

## Four-criterion implementation and fictional demonstration

`g18-four-development-1` implements six pairwise judgments, reciprocal matrix
construction and normalized-column row-average AHP with a 50-digit Decimal
context. Default output must replay the existing validated reference exactly;
rounded target weights are not assigned in code. The matrix (SI, ES, PA, ND) is:

| | SI | ES | PA | ND |
|---|---:|---:|---:|---:|
| SI | 1 | 2 | 3 | 5 |
| ES | 1/2 | 1 | 2 | 4 |
| PA | 1/3 | 1/2 | 1 | 3 |
| ND | 1/5 | 1/4 | 1/3 | 1 |

| Output | Decimal text |
|---|---|
| SI | 0.47085905179088958208889183867613548372823610097122 |
| ES | 0.28401252184686179509302891528948474591270104643702 |
| PA | 0.17148293179354439061082719408862635782394194818699 |
| ND | 0.073645494568704232207252051945753412535120904404772 |
| lambda estimate | 4.0513654728589442612068089407860696967972113290515 |
| CI | 0.017121824286314753735602980262023232265737109683833 |
| RI | 0.90 |
| CR | 0.01902424920701639303955886695780359140637456631537 |

These are finite-context computed Decimal outputs, proposed configuration values
pending explicit confirmation. PR contributes no score in this separate module;
it remains a program-specific eligibility requirement. Approval/effective date
and authorized program list remain unset. No approximately May 2026 date is used.

The fixed fictional example retains three applicants: DEMO-A and DEMO-B eligible;
DEMO-C either confirmed ineligible under a test-only functional-need rule or still
awaiting review. Pending review blocks all scores without removing DEMO-C. The
example's arbitrary 0..10 benefit scales are visibly fictional, not proposed SI,
ES, PA or ND measurement policy. Scores are approximately 63.0417 and 49.4038;
selecting DEMO-B illustrates an independent human choice, writes no beneficiary
decision, and leaves actually-assisted false. No business rank, tie-break or need
classification is assigned. Full exact values/traces are in the evidence JSON.

The exported end-to-end evidence also executes the existing five-criterion
fictional contract: accept, calculate, validate complete graph, promote, inspect,
mutate a source, reject current use, and replay the unchanged historical run.
The pointer is cleared and historical completeness remains true. The browser
creates two actual development calculation versions and shows their predecessor
history. Four-criterion example scores are **not** inserted into five-criterion
historical tables or represented as an approved persisted configuration.

## Admin development interface and privacy

Two private pages reuse the existing layout under EWAF & Selection: guided
pairwise comparisons/readiness/fictional explanations, and harness-created
program calculations/history. A conditional link appears only in a registered
session with existing permissions. No permission definitions, sidebar modules,
CSS baseline or public page is changed. Outside registration, development routes
return 404 before querying the development tables. Fresh permissions are checked;
pages are not cached and use existing authentication and CSRF handling.

The pages distinguish eligibility, numerical comparison, hypothetical human
selection and actual assistance; they explain functional need, missing/disputed
evidence, consent and accessible alternatives without inventing assessment rules.
Inputs edit pairwise judgments and the fictional example only; scores/weights/
ranks are not manually editable. Program calculation forms submit expected
generation/context tokens and a reason. No new operational selection endpoint
or real-member input to the fixed four-criterion example exists.

Browser validation used Chrome/Playwright against the disposable live server:
two pages, widths 320/390/768/1440, labels for visible controls, keyboard checkbox
and history expansion, no horizontal page overflow, pending-inventory blocking,
fictional selection, two real versioned calculations, no score/rank edit fields
and no page errors. Desktop/mobile/history screenshots were visually inspected.
This is focused accessibility evidence, not WCAG certification, screen-reader
testing, contrast certification or user acceptance by PWD participants.

## Executed tests and corrections

Every Django command used the existing isolated runner, which initializes a fresh
loopback MySQL 8.4.11 datadir, disables `.env`, grants only disposable databases,
checks identity/isolation and destroys the test database/server. Durable runner
verified READ-COMMITTED and InnoDB. Only fictional fixture data/files were used.
No `--keepdb`, SQLite substitution or application-database command was used.

Command prefix (PowerShell):

```text
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py
```

All test commands append `--testrunner scripts.durable_test_runner.DurableTestRunner --noinput`.

| Run group | Arguments after prefix |
|---|---|
| Combined focused | `test ewaf.test_membership_writers ewaf.test_member_writers ewaf.test_assistance_writers ewaf.test_reference_writers ewaf.test_access_writers ewaf.test_generation_processing ewaf.test_four_development ewaf.test_development_views` |
| Corrected photo/reference/UI | `test ewaf.test_development_views ewaf.test_photo_writers ewaf.test_reference_writers` |
| UI failure-path probe | `test ewaf.test_development_views` |
| EWAF regression | `test ewaf` |
| Domain regression | `test programs events members membership documents assistance accounts` |
| Full project | `test` |
| Browser | `test scripts.stage8_browser_qa` |
| Django/database | `check --database default` |
| Migration drift | `makemigrations --check --dry-run` |

<!-- RESULTS_START -->
| Executed run | Tests | Seconds | Failures | Errors | Skips | Result |
|---|---:|---:|---:|---:|---:|---|
| membership-initial | 12 | 7.408 | 0 | 1 | 0 | FAILED |
| membership-corrected-regression | 54 | 8.535 | 0 | 0 | 0 | OK |
| members-initial-regression | 90 | 17.115 | 0 | 14 | 0 | FAILED |
| members-second | 14 | 2.337 | 0 | 14 | 0 | FAILED |
| members-assistance-corrected | 26 | 36.781 | 0 | 0 | 0 | OK |
| reference-shared-regressions | 148 | 79.251 | 0 | 0 | 0 | OK |
| promotion-foundation | 61 | 97.167 | 0 | 0 | 0 | OK |
| four-ui-promotion | 43 | 105.409 | 0 | 0 | 0 | OK |
| access-browser-initial | 7 | 55.096 | 1 | 0 | 0 | FAILED |
| hardening-browser-corrected | 44 | 150.156 | 0 | 0 | 0 | OK |
| focused-combined | 112 | 239.645 | 0 | 0 | 0 | OK |
| ewaf-initial | 804 | 932.356 | 0 | 1 | 0 | FAILED |
| domain-regressions | 463 | 294.326 | 0 | 0 | 0 | OK |
| full-initial | 1397 | 1328.540 | 0 | 1 | 0 | FAILED |
| browser-before-display-fix | 1 | 26.141 | 0 | 0 | 0 | OK |
| ui-replacement-initial | 8 | 30.189 | 1 | 0 | 0 | FAILED |
| photo-reference-ui-corrected | 70 | 80.058 | 0 | 0 | 0 | OK |
| ewaf | 804 | 887.849 | 0 | 0 | 0 | OK |
| full | 1397 | 1235.569 | 0 | 0 | 0 | OK |
| browser-final | 1 | 22.638 | 0 | 0 | 0 | OK |

The full run executed **1,397 passing tests**, including all 1,285 pre-existing tests and 112 new tests. The separate browser check passed one additional test. Repeated suite counts overlap and are not summed as unique coverage.
<!-- RESULTS_END -->

Initial failures are retained, not omitted: membership's worker propagated an
expected ValidationError rather than returning it (one test error); a new Member
fixture first used a nonexistent field (14 errors), then lacked the mandatory
issued reference (14 errors). Fixtures were corrected to use the existing
application fixture, preserving reference rules. Browser's exact label selector
missed Django's rendered colon (one failure); the selector was corrected. Existing
business/security assertions were not weakened. Broad regression then caught an
older photo-test fixture creating DocumentType after session registration. The
reference is now prepared before registration; all old assertions and rollback
expectations are AST-compared unchanged. No guard was relaxed. Review also found
that a failed replacement response could reuse its pre-POST current-result label;
the error path now conservatively clears that label. Its first added assertion
failed because the injected numerical failure also interrupted predecessor replay
before acceptance; injection was moved to graph persistence to exercise the
intended post-acceptance rollback. Corrected reruns and final
results are tabulated above. There were no automatic retry loops hiding failures.
Timings are Django-reported test execution times, not total disposable-instance
startup time or performance benchmarks. Independent regression runs used separate
instances concurrently. The initial broad runs had already loaded the pre-fix
photo fixture; their retained tracebacks may display a subsequently updated source
line. Final broad reruns loaded the corrected source from startup.

Django/database checks reported no issues; migration drift reported no changes.
Working-tree and staged whitespace checks pass; added files are checked for
trailing whitespace. Migration leaves are recomputed offline from local migration
dependencies and compared to the captured baseline. All historical migration
bytes remain unchanged. The application migration recorder was not queried.

## Remaining blockers and conditions for 80% acceptance

1. Owner and independent reviewer must accept the complete Stage 8 scope and
   evidence; this report does not advance the milestone.
2. Association confirmation is still required for the revised configuration,
   scoring definitions/measurements/normalization directions and bounds, PA
   measurement/lookback/scope, classifications/boundaries/ties, missing/disputed
   evidence handling, approving role, approval/effective dates and program scope.
   PR removal alone does not approve these rules.
3. Program-specific functional-need evidence, authorized assessment/consent and
   accessible alternatives remain subject to approved policy. No disability-label
   shortcut or silent exclusion was introduced.
4. The four-criterion workflow is a separately versioned, blocked-policy fictional
   demonstrator. Persisting it as an approved production calculation/configuration
   requires a reviewed compatible storage/workflow design and separate schema
   authorization if needed; no five-criterion schema reinterpretation is allowed.
5. Production-scale lock/load/deadlock recovery, external import/SQL integrations,
   filesystem integrity/maintenance and broader accessibility/user acceptance
   remain outside this bounded disposable proof. Raw unguarded writers invalidate
   its atomicity assumptions. See the explicit coverage limitations.
6. Source-edit form generation-token UX is not a production rollout; registered
   sessions use internal/test contracts and fail closed where tokens are absent.
   Deployment, application-database migration (including existing migration 0006),
   operational activation and any real-member use need separate authorization.

## Review package

`.local/stage8-sprint/stage8-consolidated-review-2026-10-19.zip` contains exact
source deltas, new tests/browser harness, unchanged reference dependencies,
sanitized initial/final logs, fictional demonstration JSON, three screenshots,
offline migration leaves, preservation evidence, SHA256SUMS and a payload manifest.
The adjacent `review-package.sha256` contains the ZIP checksum; the build verifies
each archived payload against the manifest. Credentials, environment files/hashes,
application databases, MySQL datadirs/config, real records and private uploads are
excluded. Stop after this sprint for independent review. **Milestone: 70%.**
