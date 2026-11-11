# G06-B1A — Manual PDAO Approval Recording

Date: 2026-10-12 (Philippine time).
Branch: `feature/events`.
Verified starting HEAD: `27ba496330c8a6dc1d7eb270b8bc02213d389a16`.
The working tree was clean before implementation. The owner-defined development
baseline remains **70%**.

## Confirmed policy and increment boundary

Every assistance program requires manual PDAO approval. An authorized Association
Admin/Secretary records it; PDAO does not use the system. Signed/stamped letters
are held physically at the Association office. No digital upload/storage, PDAO
account, mandatory second-officer confirmation, Approved Budget or restored
Budget editing is included.

Previously approved programs with a missing letter may continue while replacement
approval is obtained. This requires an explicit legacy Association attestation;
existing publication/internal policy authorization is never treated as evidence
of PDAO approval. Unknown legacy dates and signatories remain unknown.
Legacy recording requires a retained publication timestamp no later than the
recording time. Never-published programs must use official approval recording;
this remains available while they are drafts.

Major revisions require renewed approval, full processing suspension and existing
application reassessment. Those are confirmed requirements for later increments;
**this increment implements recording only**, with no new publication/application
gate, suspension, reassessment, eligibility rule or beneficiary decision.

## Files changed

1. `programs/models.py`: add `PDAOApprovalRecord` and append-only queryset guards.
2. `programs/approval_forms.py`: explicit recording fields and manual confirmation.
3. `programs/approval_services.py`: permission checks, serialized append and audit.
4. `programs/approval_views.py`: protected, noncached history and recording page.
5. `programs/urls.py`: named `programs:pdao_history` route.
6. `templates/programs/manage_detail.html`: permission-controlled history link.
7. `templates/programs/pdao_history.html`: paginated history and recording form.
8. `programs/migrations/0004_pdaoapprovalrecord.py`: additive table migration.
9. `programs/test_pdao_approval.py`: focused synthetic regression coverage.
10. `docs/g06-b1a-pdao-recording-validation-2026-10-12.md`: decision and validation.

## Records, permissions and preservation

`PDAOApprovalRecord` contains the program, a positive per-program recording
sequence, program version at recording, record type, approval date, signatory,
explicit manual confirmation, recording reason, actor FK/label, timestamp and a
required unique link to its `ProgramLog` audit entry. The actor label preserves
the recorded name even if the account is renamed. Protected foreign keys prevent
deletion of the associated program, actor and linked audit entry.

- **Official approval record — physical letter held:** approval date and nonblank
  signatory are required, with confirmation that the physical signed/stamped
  letter at the office was checked.
- **Legacy Association attestation — physical letter missing:** explicit manual
  attestation and a reason are required. Date/signatory may remain blank when
  unknown; known metadata can be retained. The UI distinguishes this from an
  official letter record and states that replacement approval is being obtained.
- A future approval date is rejected because this records approval already
  obtained. No metadata is estimated or copied from publication timestamps.
- Prior entries cannot be edited/deleted through model save/delete, queryset
  update/delete or bulk write APIs. There are no edit/delete routes or permissions.
  Corrections append a new numbered entry with a reason; previous entries remain.
- The sequence is **not** an approved-terms version. `program_version_at_recording`
  is context only; it does not claim approval of the current terms. B1A has no
  approved-terms snapshot or effective-approval pointer for enforcement to consume.

History requires active staff status and `accounts.access_dashboard`,
`programs.view_program` and `programs.view_pdaoapprovalrecord`. Recording also
requires `programs.record_pdaoapprovalrecord`. This works for an explicitly
authorized non-superuser Secretary; existing publication permission alone does
not grant recording. No existing user/group permissions are changed automatically.
No independent second officer is required.

The recording service locks the program row inside an atomic transaction. It
checks both the latest approval sequence and the program version submitted by
the form. Competing submissions from the same history version serialize; only
one succeeds and the other must reload. A unique `(program, version)` constraint
provides additional protection. Failed audit or record insertion rolls back both.
Model validation also checks the stored audit row's program, actor and
`pdao_recorded` action against the approval entry. Service validation errors are
returned as form-wide errors, including errors on fields not exposed by the form.
Audit changes contain the entry sequence/type, while signatory and context remain
on the separately permission-protected history page.

Recording never saves the Program row, bumps `Program.version`, authorizes its
selection/photo policy, alters dates/budget/terms, or updates applications,
eligibility, releases or results. Existing verification grants stay valid. The
G06-B0 form exclusion and every G07/G07-B availability rule remain unchanged.

The page uses existing Admin layout, form/error rendering, labels, CSRF protection
and pagination (20 entries). Unknown metadata and empty history are explicit.
Text is escaped; recording timestamps use the existing Philippine timezone.
There is no upload field; forged multipart uploads are rejected without storage.
History is not exposed on public pages and responses are marked noncacheable.

## Additive migration

`0004_pdaoapprovalrecord` depends on programs `0003` and the configured user model.
Its only operation is `CreateModel`: one new table with foreign keys, a unique
program/sequence constraint, positive sequence and manual-confirmation checks,
and official-record metadata/type constraints. Django creates the new view and
record permission definitions during migration setup; it assigns no roles.

There are no Program alterations, data migrations, backfills, inferred approvals,
budget changes, document columns or uploads. Existing application/release tables
are untouched. Migration execution was limited to disposable test schemas. A
separate reviewed deployment must apply it before enabling this code in a real
environment. Reversing it after recording real entries would discard the new
history; preserve those entries and use a separately reviewed recovery procedure.

## Initial implementation validation (before targeted correction)

The shell was checked for inherited `DB_*`, `SUPABASE_*`, `AWS_*` and
`DJANGO_SETTINGS_MODULE` variables before setup; none were present. The existing
isolated-test harness was adapted in memory without changing its file. MySQL
8.4.11 ran on loopback at an unused port, with a fresh Windows-temp data directory
verified using `SELECT @@datadir` before Django database commands. Credentials
were generated only for that temporary server. `.env` loading was disabled using
`PYTHON_DOTENV_DISABLED=1`; no development or production credentials were read.

The scratch connection schema was `review_unused`; tests used the distinct
`test_g06b1a_disposable` database. Every migration and fixture operation occurred
on this fresh local instance, never on an existing `.local` or hosted database.
The migration preservation test temporarily moved only the disposable schema
between programs `0003` and `0004`, retained a synthetic historical program and
budget, verified that `0004` contains only `CreateModel`, and confirmed that no
approval record was inferred.

Final commands used the virtual-environment Python and this isolated environment:

```text
manage.py check --database default
manage.py makemigrations --check --dry-run
manage.py test programs core.tests.test_home_program_availability --noinput --verbosity 1
manage.py test --noinput --verbosity 1
```

Results:

- **120 focused tests passed**, 26.889 seconds, including all existing program,
  G06-B0 budget-preservation, G07/G07-B and 23 new PDAO tests.
- **455 full regression tests passed**, 112.703 seconds: 432 existing plus 23 new;
  no failures or skips. Focused tests are included in the full count.
- Django system/database checks: no issues.
- Migration drift: **No changes detected** after generating `0004`.
- `git diff --check` and equivalent checks for every untracked file: passed.
- AST comparison against HEAD: every pre-existing model, queryset and function
  in `programs/models.py` is unchanged. Original forms, services, workflows and
  tests are untouched.
- Full tracked/untracked file review: only the ten intended files above, no
  credentials, secrets, real member data, database files or generated test
  artifacts included; index empty. Branch and HEAD remain unchanged.
- Both test schemas were destroyed and the isolated MySQL process stopped.
  Synthetic logs/data remain in Windows temp outside the repository.

The first focused run exposed one new-test fixture error (four status subcases):
the shared factory already supplied `policy_authorized_at`, so passing it again
duplicated the keyword. The test now changes that synthetic field after creation.
The final successful runs above include that correction and extended checks for
published-result and verification-grant preservation.

The 23 new test methods cover explicit Secretary permissions and missing-permission
denials; anonymous/inactive/nonstaff access; private view-only history; required
fields, whitespace, future dates and manual confirmation; unknown/known legacy
metadata; sequential official replacement without overwriting history; forged
actor/program/version/budget/audit fields; stale program/history versions;
instance/queryset/bulk immutability and protected foreign keys; audit and insert
rollback; unchanged program/internal policy across all statuses; unchanged
application, eligibility, release and published-result records; valid verification
grants and no new application gate; upload rejection; CSRF/method guards;
pagination/escaped text/labels; concurrent recording; and migration preservation.

## Targeted independent-review correction

The branch and HEAD were reverified at
`feature/events` / `27ba496330c8a6dc1d7eb270b8bc02213d389a16`.
The ten existing uncommitted G06-B1A files were retained. This correction changes
only `programs/approval_services.py`, `programs/models.py`,
`programs/test_pdao_approval.py` and this report; the migration, form fields and
Admin templates are unchanged.

The service now rejects legacy attestations if the locked Program row has no
`published_at` or that timestamp is still in the future. The existing publication
service retains this timestamp on withdrawal, cancellation and archive. A
previously published program can therefore be attested without requiring it to
be currently public. No historical cutoff date or age threshold is imposed.
The timestamp is a necessary condition only: manual attestation, permissions,
reason and stale-version checks remain mandatory. Publication never inserts an
approval record or supplies missing PDAO metadata. Official approval can still
be recorded for a never-published draft without publishing it or authorizing its
internal selection/photo policy.

Model-level audit validation is appropriate because a valid foreign-key ID alone
does not establish that an audit belongs to the same program/actor/action. The
existing service's `full_clean()` now verifies these relationships against the
stored audit row before inserting the record. A mismatch rolls back the audit
transaction. Validation errors are normalized for the recording form so that an
error on the noneditable audit field does not itself cause a server error.
No existing audit row or approval record is modified by these checks.

Seven additional regression tests cover:

1. Rejection for never-published drafts and archives, with unchanged program data
   and no approval/audit insertion.
2. Forged publication status/timestamp POST fields cannot bypass the service guard.
3. A future publication timestamp is not past publication; the current instant
   satisfies the timestamp prerequisite without removing manual attestation.
4. Real publication-service transitions to published, withdrawn draft, cancelled
   and archived states retain eligibility to record an explicit legacy attestation;
   publication alone creates no approval, and missing confirmation still fails.
5. Official approval succeeds for a never-published draft without changing it.
6. Model validation accepts a matching audit and rejects wrong program, actor or
   action while preserving the previously stored approval record.
7. An incorrect audit created during recording is rolled back, produces a usable
   form error, and does not consume an approval sequence number.

Final correction validation used a new verified disposable local MySQL instance
with the same isolated settings/commands described above, synthetic credentials,
and `.env` loading disabled:

- **127 focused tests passed**, 31.503 seconds, including 30 PDAO tests.
- **462 full regression tests passed**, 111.292 seconds (455 before this correction
  plus seven new tests), with no failures or skips. The focused count is included
  in the full count.
- Django system/database checks passed with no issues.
- Migration-drift check: **No changes detected**. The existing additive `0004`
  remains unchanged; no additional migration is created or needed.
- Tracked and untracked whitespace checks passed. Static review confirmed every
  pre-B1A model and function remains unchanged, including the Program model and
  availability queryset. No unrelated files, credentials or private data were added.
- Django destroyed the disposable test schema after each suite; the isolated
  MySQL process stopped. No existing application database was accessed.
- Branch/HEAD remain unchanged, all work remains unstaged, and no commit, push
  or deployment was performed. The owner-defined **70%** baseline is unchanged.

## Limitations and owner review

The software records an authorized officer's assertion; it cannot independently
authenticate a physical letter. Append-only application controls do not prevent
a privileged operator from changing data with raw SQL. Existing institutional
backup, database-access and audit protections remain necessary.

No approved-term binding, approval activation, revocation, suspension/resumption
or reassessment is implemented. Later enforcement must explicitly distinguish
official records from legacy attestations and define its transition and term
version linkage; it must not treat the newest B1A entry as automatic authorization.
Historical records and human final decisions must remain preserved.

Visual browser/assistive-technology QA and hosted acceptance are not claimed;
rendered Admin HTML, access controls, escaping, labels and pagination are tested.
This increment does not establish completion of the full PDAO workflow or change
the 70% baseline. No production/private data access, deployment, staging, commit
or push is authorized or performed.

After owner review, publication and deployment remain separate approvals.
For future rollout: review the migration, back up the database, apply the additive
migration only under that approval, and assign the new permissions to the
authorized Association personnel. No production command was run in this task.

Recommendation: **GO for owner review of G06-B1A recording only.** No blocking
implementation issue was found. This is not approval to deploy or a claim that
the complete PDAO enforcement/reapproval workflow is implemented.

Suggested commit message: `Add versioned manual PDAO approval recording`.
