# G06-B1B.1 — Approved-term binding and enforcement preparation

Date: 2026-10-12, Philippine time. Owner-defined milestone: **70%, unchanged**.
Branch: `feature/events`. Verified starting HEAD:
`3db9b3f78fdcb5315e292ec05942511bd80dc213`. The working tree was clean before this
increment. Nothing has been staged, committed, pushed or deployed.

## Scope and authority

This increment implements the owner's G06-B1B.1 decisions. The October 10
`CURRENT_SYSTEM_SPECIFICATION.md`, development guide, open decisions, implementation
impact, membership/PDAO amendment and existing G06-B0/B1A/G07 validation remain
context; target documentation does not authorize extra business rules.

PDAO approval remains external and physical. Authorized Association officers record
and explicitly reconcile it. No PDAO account, digital letter, Approved Budget,
budget editing, second-officer requirement, automatic approval, EWAF activation,
beneficiary selection, suspension or reassessment is added.

`PDAO_ENFORCEMENT_ENABLED` defaults to false. Publication/intake approval gating is
prepared and tested with synthetic settings overrides only. The interim protected
editing freeze **does apply independently of this flag**, as the owner requested.
Genuine legacy programs can continue their existing application/processing behavior
while reconciliation is pending. Existing missing internal policy/configuration
continues to block intake; this increment does not invent replacement terms.

## Changed files

Existing files:

1. `config/settings.py` — default-off enforcement setting.
2. `programs/models.py` — new history/control models and availability projection.
3. `programs/services.py` — locked intake/publication checks and protected no-op preservation.
4. `programs/forms.py` — protected program/requirement validation and form-save guards.
5. `programs/approval_services.py` — B1A recording participates in common lock order.
6. `programs/urls.py` — protected readiness, terms-review and immutable revision URLs.
7. `members/models.py` — disability-definition mutation protection.
8. `documents/models.py` — referenced document-type definition protection.
9. `events/forms.py` — protected event/link validation and form-save protection.
10. `events/services.py` — event/link and lifecycle serialization.
11. `templates/programs/manage_detail.html` — permission-controlled terms-review link.
12. `templates/programs/manage_list.html` — permission-controlled readiness link.
13. `programs/tests.py` — directly affected freeze/draft/budget-preservation expectations.
14. `programs/test_revised_workflow.py` — reject live policy rewrite while preserving reference search.
15. `programs/test_pdao_approval.py` — restore all migration leaves after the existing 0004 test.
16. `assistance/tests.py` — protected-slot rejection precedes the retained reservation guard.

New files:

17. `programs/terms.py` — canonical snapshots, digest, mutex and reference/edit guards.
18. `programs/approval_policy.py` — shared binding projection and locked authorization checks.
19. `programs/binding_services.py` — explicit audited capture, binding and read-only preflight.
20. `programs/binding_forms.py` — explicit confirmation, reasons and stale counters.
21. `programs/binding_views.py` — private paginated review/readiness and immutable history.
22. `programs/management/commands/pdao_cutover_preflight.py` — read-only readiness command.
23. `programs/migrations/0005_approved_terms.py` — additive schema only.
24. `programs/test_approved_terms.py` — 36 synthetic backend tests.
25. `templates/programs/approval_readiness.html` — paginated officer readiness report.
26. `templates/programs/terms_review.html` — current/immutable terms, explicit actions and histories.
27. `scripts/approved_terms_browser_qa.py` — disposable-server browser fixture.
28. `scripts/approved_terms_browser_qa.cjs` — focused headless Chrome checks.
29. This validation document.

## Schema and preservation

Migration `0005_approved_terms` creates four tables:

- `ProgramTermsRevision`: program, independent positive per-program revision number,
  schema version, JSON snapshot, SHA-256 digest, officer/retained label, time, reason
  and mandatory unique audit link. Unique `(program, number)` and positive-number
  constraints. Model/queryset writes cannot overwrite/delete/bulk-replace history.
- `ProgramApprovalBinding`: one program, one terms revision and one existing B1A
  approval record, officer/retained label, time, reason, explicit confirmation and
  mandatory unique audit link. Confirmation is also a database constraint. Its type
  derives from the immutable referenced approval record; legacy is never converted.
- `ProgramApprovalControl`: one row per explicitly reviewed program; governed
  current-revision/digest pointer, active-binding pointer and independent optimistic
  concurrency counter. Only the audited services expose pointer changes.
- `ProgramTermsLock`: a lazily created technical mutex; no approval or program data.

Operations are four `CreateModel`, one `AddField` on the newly created binding
table, and three `AddConstraint`. No `RunPython`, `RunSQL`, removal or alteration of
existing business fields. Migration 0004 is unchanged. No data backfill, fabricated
approval, publication inference or enforcement activation occurs during migration.
Existing budget, program version, applications, snapshots, documents, eligibility,
results and releases are not rewritten. Recording/capture/binding do not save the
Program row. A no-op save of a protected program also retains its version, avoiding
unnecessary historical eligibility/result invalidation.

The preservation test migrates a synthetic database from 0004 to 0005 and compares
the complete Program and PDAO history rows, then checks that revision/binding/control
tables remain empty. The original 0004 test retains its preservation assertions;
its cleanup now restores the current leaf migrations instead of leaving 0005 absent.

## Canonical protected terms: schema 1

Top-level keys: `schema`, `program_id`, `program`, `requirements`,
`disability_qualifications`, `event`.

Program fields: `name`, `description`, `assistance_type`,
`registration_opens_at`, `registration_closes_at`, `starts_at`, `ends_at`, `slots`,
`amount`, `benefit`, `requirements`, `ewaf_applicable`, `selection_method`,
`photo_instructions`, `resubmission_closes_at`.

- Include description, eligibility/requirement text, benefits and assistance type
  to retain their approved meaning, not merely numeric slots or dates.
- Every structured requirement, including inactive ones, is ordered by
  `(position, primary key)`. Capture identity, label, kind, instructions,
  required/active flags, order, and referenced document-type identity, name and
  description. These are definitions, not uploaded applicant documents.
- Disability references are ordered by primary key and capture identity, name and
  `is_active`, because deactivation changes qualification behavior.
- An optional linked event captures its identity, title, description, location,
  start/end, historical registration dates and capacity. Linking, unlinking and
  reassignment therefore cannot silently change approved terms. Lifecycle status
  and publication timestamps stay separate from immutable event terms.
- Aware timestamps use UTC ISO 8601 with six fractional digits. Money uses fixed
  two-place decimal strings. Nulls, booleans and integers retain their JSON types.
  Snapshot JSON uses sorted object keys, compact separators and UTF-8 without
  ASCII escaping for SHA-256. Equivalent object key order yields the same digest.
- Budget and Approved Budget are absent. Program/version counters, internal policy
  authorization metadata, member records, applicant evidence and uploaded files
  are absent. Officer identity belongs to the protected audit/history metadata.
- Schema field allowlists and digest validation reject unexpected program fields.
  Current review dates are rendered in Asia/Manila; immutable stored timestamps
  remain canonical UTC. Historical revisions have a protected read-only URL.

## Binding, permissions and lock order

Officers require active staff/dashboard access plus view permissions for Program,
B1A PDAO records, terms revisions and approval bindings. Recording/binding also
requires `programs.bind_programapprovalbinding`. B1A approval recording retains its
separate existing permission. No officer permissions are granted automatically.

Capture requires explicit review, reason, expected Program/control versions and
the digest of the displayed current terms. Unapproved, never-published drafts may
have preliminary captures followed by ordinary initial configuration and a fresh
capture; this never authorizes publication. Previously published or already-bound
programs cannot capture changed revisions through this increment.

Binding requires explicit coverage confirmation and reason, current Program/control
versions, a current terms revision, a same-program B1A record, and the expected
approval-history counter. B1A metadata/audit validation is repeated. Cross-program,
forged, stale and nonmatching snapshot requests fail. An older specifically selected
approval may be used; the latest history entry is only a concurrency check, never
authorization. Adding any new B1A entry leaves the active binding unchanged.

Official evidence can bind a never-published draft. Legacy needs genuine retained
prior publication plus the B1A explicit manual attestation and a first reconciliation
revision; it cannot bind a later changed revision. Prior publication is only a
prerequisite, never proof of PDAO approval. Unknown legacy metadata remains unknown.
Replacing a binding with newly recorded evidence for the **same immutable terms**
is explicit and audited; both bindings remain. The same approval cannot be reused
for different terms. No revised-approved-term workflow is supplied.

Transactions acquire the installation-wide technical mutex first, then the Program
row (or Event/reference row for those operations), then existing application/member
locks as needed. B1A recording, capture, binding, supported term/reference edits,
event publication, program publication, verification and final submission share
this order. The mutex also protects dependencies that are not linked yet, avoiding
the attach-versus-approve race. Audit failure rolls back the entire transaction.

Five two-connection MySQL concurrency tests exercise bind/bind, record/edit,
bind/publish, capture/edit and bind/submit. Existing recording and submission
concurrency tests remain. This is correctness evidence, not a load benchmark.
The coarse mutex serializes work across programs and may need a carefully reviewed
more granular design if traffic grows.

## Mutation-path review and interim freeze

| Existing path | Protection in this increment |
| --- | --- |
| Program Create/Edit POST and `save_program()` | Protected field/M2M differences fail for previously published, cancelled, explicitly approved or bound programs, even without applications. Draft initial configuration remains available. |
| Direct `ProgramForm` validation/save/M2M save | Rechecks the freeze, including a form validated before approval recording. Normal request writes use the audited locked service. |
| Requirement Add/Edit POST, `RequirementForm`, `save_requirement()` | Protect all structured fields and referenced document type; retain existing submitted-requirement restrictions. |
| Disability classification Admin/form/model/queryset | Protect name/active state and deletion when referenced by a protected program; cover update, bulk update and forged existing-primary-key save. |
| Document type Admin/form/model/queryset | Protect referenced name/description and deletion; cover bulk/update paths. |
| Event Create/Edit/form/service | Prevent adding, removing, replacing a protected link or changing linked identity/description/location/schedules/capacity. Configure the initial link before approval/publication. |
| Event/program lifecycle actions | Serialized; legitimate withdrawal/cancellation remains possible. Event visibility affects intake without rewriting approval terms. |

The application does not expose Program/requirement/binding/control editing through
generic Django model administration. Reference types do use that administration and
therefore have model-level and queryset guards. Unrelated member-profile corrections
remain available; no member data is frozen or added to the approval snapshot.

These are application/service/form guards, not database triggers or protection
against a privileged raw SQL administrator. Low-level ORM/SQL maintenance must not
bypass them. Synthetic tests deliberately simulate out-of-band drift: locked intake
and preflight recompute the digest and refuse it. Public SQL labels use the guarded
stored control/digest projection, so unsupported raw database edits can leave a label
stale until detected. Any future mutation endpoint must join this locking/guard design.

## Prepared authorization and public behavior

When the flag is false, missing bindings do not block existing publication/intake.
When enabled in tests, a valid explicit same-program binding, current terms revision
and matching digest are required. New first publication requires official evidence;
explicitly reconciled genuine legacy programs may continue with legacy evidence.
Internal selection/photo authorization remains independent. Publication retains its
existing validation and officer policy confirmation; intake retains publication,
date, identity, eligibility and linked-event checks.

Verification and final submission recheck authorization while locked and recompute
current terms. Verification grants include the binding identity/control counter only
in enabled mode. Replacement bindings invalidate prior grants without changing
Program.version. New enabled-mode application snapshots retain the authorizing
binding/counter; old application snapshots remain unchanged.

G07's one-query `accepting_applications().exists()` remains a database existence
query. G07-B Open/Upcoming/Ended/Cancelled/Unavailable categories, exact inclusive
opening/exclusive closing boundaries, public URLs and current/past bookmarks are
retained. A linked event that is draft, archived, cancelled or future-unpublished
already blocked backend intake; property/queryset labels now agree with that rule.
No new event RSVP or scheduling policy is introduced. Public errors use generic
unavailability and disclose no signatory, internal approval history or reason.

The intake gate is not a post-deadline processing gate. No suspension, reassessment,
result withdrawal, release correction or historical attendance policy is implemented.
Future G06-B2/B3 must separately cover:

- `programs.workflow.review_photo`, `correct_application` and evidence invalidation;
- `programs.services.change_application` and reasoned closure;
- `assistance.services.review_eligibility`, `decide_assistance`, `record_release`,
  `void_release`, and current-review/reference dependencies;
- `announcements.results.prepare_results`, result publication/currentness and
  associated announcement lifecycle paths;
- `events.services.save_attendance` (including historical corrections),
  `change_registration` and linked selected/completed application checks;
- membership/document corrections that affect assessment evidence, plus any future
  restored EWAF processing entry points (currently retired/disabled).

Those paths retain their current permissions, locks, audits and human decisions.
No terms revision is allowed here that would require their suspension machinery.

## Read-only readiness and future cutover

The private readiness list uses SQL binding projection and pagination (20 rows),
shows recorded explicit bindings versus missing review, and states that full current
terms still need preflight validation. Current terms, PDAO entries, revision history
and binding history are protected; histories are paginated. Viewing does not create
control rows, revisions, approval records or bindings.

`manage.py pdao_cutover_preflight` is read-only. It includes **every published
program**, even when intake has ended or publication is scheduled in the future;
an ended intake period cannot prove that processing is finished. It checks explicit
binding validity and streams canonical digest comparisons, failing with a nonzero
exit for missing/invalid bindings or drift. It never changes settings. Nonpublished
programs remain visible in readiness and must satisfy the publication gate before
future republication. Historical attendance corrections remain outside this gate.

Future owner-approved operational procedure, **not executed here**:

1. Independently review this increment and its additive migration; authorize any
   actual release/migration separately. Keep enforcement disabled.
2. Assign the new review/binding permissions only to authorized officers.
3. Have officers review each operating program and its exact terms, physically
   check the letter or attest genuine previous approval with a missing letter,
   record/review the evidence and explicitly bind it. Resolve discrepancies without
   silently editing protected terms or fabricating approval metadata.
4. Resolve programs needing the future revision workflow; their terms cannot be
   changed by this preparation increment.
5. During an owner-approved controlled cutover window, quiesce mutations, rerun
   preflight immediately, review its output, and obtain explicit activation approval.
   A prior preflight result is not a durable activation token.
6. Only a separately authorized operator procedure may change the environment flag
   and perform deployment/smoke checks. No startup/migration auto-cutover exists.

## Validation evidence

All database-backed checks use a newly initialized, loopback-only MySQL 8.4.11
instance with a new Windows temporary datadir, random synthetic credentials,
`PYTHON_DOTENV_DISABLED=1`, filtered inherited DB/storage/PDAO settings and a distinct
`test_g06b1b1_disposable` database. The harness verifies `@@datadir` before use.
The application check schema is also newly created and empty. Test databases are
destroyed and each temporary server is stopped. No development `.env`, existing
application database, hosted credentials, Aiven/Supabase or Render data is used.

Final validation:

| Check | Result |
| --- | --- |
| `check --database default` | Passed; no issues |
| `makemigrations --check --dry-run` | Passed; models match migration files, including new 0005 |
| Focused: `programs events members documents core.tests.test_home_program_availability` | **289 passed** |
| Complete `manage.py test --noinput --verbosity 1` | **498 passed**, including the 36 new backend tests |
| Explicit `scripts.approved_terms_browser_qa` | **1 passed** |
| Python syntax and tracked/untracked whitespace checks | Passed |
| Changed-file credential/private/generated-artifact review | No credential-pattern matches or unexpected private/generated paths; no files staged |

Final backend-run logs are in the temporary `santolan-g06b1b1-tests-m7aokzyg`
directory; focused browser logs are in `santolan-g06b1b1-tests-cs5zk9do`. These are
local synthetic artifacts outside the repository, not committed evidence files.
The complete run finished across a resumed session and reported unusually long
wall-clock elapsed time; it must not be used as a runtime performance benchmark.

Git review: 16 tracked files changed (259 insertions, 20 deletions), plus 13 new
files including this report. The original migration 0004, G07 homepage view/template
and tests, and G07-B public lifecycle tests are unchanged. There are no staged files.

Earlier diagnostic runs found obsolete tests permitting published-term edits and a
0004 migration test that failed to restore later tables. A subsequent full run found
one obsolete expected slot-error message. Preserving the version on an unchanged
protected save also required changing the stale-grant test to use a genuine
withdrawal/restoration. Those directly affected assertions were updated, retaining
preservation, reservation and stale-grant checks. The final passing run supersedes
these diagnostic failures.

The 36 new backend tests cover canonical/digest history, audit rollback, independent
versioning, scoped/manual/permission binding, draft official and explicit legacy
behavior, forged requests/CSRF, protected fields and indirect definitions/events,
enabled/disabled authorization, SQL/property boundary parity, stale grants,
synthetic migration preservation, historical eligibility/results/releases and five
concurrency races. Existing G07/G07-B and B1A tests remain in the full suite.

Focused browser QA passed one headless-Chrome test of private readiness, current
review and immutable history at widths 320/390/768/1440, keyboard confirmation,
accessible labels, Philippine dates, no file/budget controls and no JavaScript
errors. Its screenshot used a temporary directory; no real records were loaded.
This was focused DOM/layout QA, not a screen-reader certification or production QA.

## Remaining limits and owner review

- Enforcement remains disabled. No actual program is reconciled in this task.
- Physical truth of legacy approval and coverage must be confirmed by the officer;
  software cannot infer it from timestamps or absence of a letter.
- Published/approved programs with incomplete instructions cannot be repaired by
  rewriting protected terms here. They need the separately authorized future
  revision workflow; preserving that freeze is intentional.
- Production cutover needs fresh operational reconciliation/preflight and owner
  approval. Neither a passing synthetic suite nor migration completion authorizes it.
- Major-revision treatment of selected/rejected/completed/released/closed applications,
  cohort versus individual resumption, published results during suspension,
  historical attendance corrections/exceptions, withdrawn/rejected proposals and
  deadline extensions remain G06-B2/B3 decisions.
- Global serialization and public projection limitations are stated above. No load
  test, production inspection or hosted migration has been performed.

Recommendation: **GO for owner and independent code review of G06-B1B.1** with
enforcement disabled. **NO-GO for production enforcement/cutover** until the separate
operational prerequisites are met. No staging, commit, push or deployment is authorized
by this report.
