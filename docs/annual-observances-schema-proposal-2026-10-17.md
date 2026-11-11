# Annual observances: schema proposal and approval record

**Follow-up approval:** the owner replied “yes i approve” to implementing the dedicated
models/migration, photo editing and publication workflow with disposable-database testing.
Applying the migration to the working database was expressly reserved for a separate step
in that approval question and remains pending. The original proposal below is retained
as historical context; current implementation and evidence are in
[persistence validation](annual-observances-persistence-validation-2026-10-17.md).
The implemented revision/audit actor FKs use PROTECT instead of the originally proposed
SET_NULL, preserving immutable attribution when an account deletion is attempted.

Date: October 17, 2026. Branch: `feature/events`. Accepted milestone: **70%, unchanged**.

## Original authorization finding (before follow-up approval)

The current request explicitly permits schema-independent groundwork when dedicated
Events-schema approval is absent. No approval covering these annual-observance tables
was found in the current specification, Open Decisions, Decisions, domain notes or
repository validation. Historical DEC-013 authorized the original actual-event workflow;
it does not expressly authorize this new annual-observance persistence. The October 16
durable-schema authorization is explicitly limited to EWAF. Neither is extended here.

**No model registration, migration file, database change, permission grant, seed or
publication is included in this increment.** Existing migrations are exercised only by
the existing disposable MySQL test harness. There is no alternate JSON/CMS/session
storage for observances and no use of `Event`/`EventLog` as surrogate storage.

The reviewable groundwork is a private source catalogue and responsive shared calendar,
an authorized read-only Events preview, and a public calendar that returns empty months
until explicit publication exists. The eleven reference candidates are not saved drafts.

## Proposed additive migration

After explicit approval, generate a new migration under `events/migrations/`, depending
on the then-current Events leaf and swappable user model. Review generated SQL and
exercise forward migration, constraints and preservation on fresh disposable MySQL first.
Do not edit historical migrations. Operational migration requires separate authorization
and a verified backup. No data migration, backfill or default permission assignment.

Proposed `AnnualObservance` (a separate content aggregate, no FK to Event/Program/Member):

| Field | Proposed definition |
| --- | --- |
| `id` | UUID primary key, immutable |
| `title` | CharField(200), required, plain text |
| `month` | PositiveSmallIntegerField, 1–12 |
| `category` | `disability` or `health`; displayed text identifies health-related content as not PWD-specific |
| `recurrence_kind` | `whole_month`, `fixed_day`, `fixed_range`, `last_monday`, `third_week` |
| `recurrence_rule` | CharField(250), required descriptive rule; server-generated canonical wording from structured fields to avoid contradictory text |
| `day_start`, `day_end` | Nullable small integers; fixed day uses only start; fixed range uses both, ordered within the same month; all descriptive kinds have both null |
| `legal_basis` | CharField(250), required citation, plain text |
| `source_url` | URLField(1000), required direct HTTPS official source, shared validator |
| `description` | TextField(2000), required plain text, escaped on output |
| `image` | Optional FileField(250); validated JPEG/PNG input normalized through the existing image pipeline, stored under a random dedicated observance path |
| `image_alt` | CharField(250), required when a photo is attached; editable image description for screen readers |
| `status` | `draft` by default; `published`, `archived` |
| `version` | PositiveIntegerField; starts at 1 after initial save, incremented on every accepted mutation |
| `published_at`, `published_by` | Nullable timestamp and user FK; set only by explicit publication, clear on withdrawal; past values survive in revisions |
| `published_by_label` | Captured actor label on publication, retained if the account is later removed; clear on withdrawal, preserve in history |
| `created_at`, `updated_at` | Server timestamps |
| `created_by`, `updated_by` | User FKs with SET_NULL; permanent actor labels retained in history |

No actual datetimes, location, RSVP, capacity, registration, attendance or application
fields. A source month does not create an association program/activity. Month/title is
not unique: future authorized content may contain multiple observances per month.

Proposed `AnnualObservanceRevision`:

- UUID PK; `observance` FK with PROTECT; unique `(observance, version)`.
- Complete typed snapshot of all content, recurrence and publication fields above.
- `version`, `action`, required `reason` (up to 2,000 characters), server `occurred_at`,
  actor FK with SET_NULL and captured `actor_label`.
- Immutable after creation, view permission only; no normal Admin add/change/delete UI.
  Never discard a revision when withdrawing, archiving or restoring a draft.

Proposed `AnnualObservanceLog`:

- UUID PK; protected observance and unique protected revision reference; action, version,
  required reason, actor FK plus captured label, timestamp, optional request address.
- Allowlisted before/after content differences, including source and recurrence changes.
  No member identifiers, credentials or private evidence payloads.
- One required audit row per revision; both written atomically with the aggregate.
  A protected read-only history view requires its separate permission. Existing
  `audit.SecurityEvent` remains authentication-specific; `EventLog` remains for real events.
- Application/service protections and read-only Admin do not imply DBA-proof immutability.

Database constraints: valid status/category/recurrence values, month 1–12, version >= 1,
publication timestamp/actor requirements (allow actor deletion only with captured label),
valid null/day shape per recurrence, day range 1–31 and ordered fixed ranges. Model/form
validation additionally checks calendar-valid month/day combinations and the URL policy.
Index `(status, month)`; unique revision version and one audit per revision. No cascading
deletion of history. Default permissions exclude delete throughout.

## Proposed permission and service contract

New dedicated permissions: `events.view_annualobservance`, `add_annualobservance`,
`change_annualobservance`, `publish_annualobservance`, `view_annualobservancerevision`,
`view_annualobservancelog`. Migration creates permission definitions only. Assignments
require explicit administrator action; existing Event publishers receive no new rights.
The present read-only preview uses existing `events.view_event` plus dashboard access;
that does not authorize future editing/publication.

Every future mutation must independently enforce authenticated, active, staff,
`accounts.access_dashboard` and the relevant dedicated permissions at service level.
Views enforce the same checks; hide inaccessible controls as a usability aid only.
Restrict changes to allowlisted fields; caller-supplied actors, versions-to-store,
publication timestamps and state cannot override server ownership.

Proposed lifecycle:

1. Create: view + add; always private draft; canonical recurrence, validated URL/content;
   actor, initial version, revision and log saved in one transaction.
2. Edit draft: view + change; lock row with `select_for_update` inside `atomic`, compare
   submitted expected version, validate, increment version, append snapshot and audit.
3. Publish draft: view + publish, explicit confirmation and reason; lock/check version,
   rerun full validation, record actor/time, append complete revision/audit atomically.
4. Withdraw published content: view + publish and reason; atomically become private draft,
   increment version and retain publication history. Editing published rows directly is
   rejected: the Admin must withdraw, edit, preview and explicitly republish.
5. Archive: view + publish and reason; remove from public projection, preserve all history.
   Restore archive to private draft through the same permission/version/audit boundary.
6. Any stale edit/publication is rejected without writes. Audit or revision failure rolls
   back aggregate changes and version increments. Concurrent mutations serialize on the
   aggregate; no object deletion, silent overwrite or auto-publication endpoint.

Public query must select published rows with a nonfuture publication timestamp and
project only month/category/title/recurrence/legal basis/source/description plus a
publication-checked image endpoint and image alternative text. Never expose
drafts, archives, actors, versions, audit notes, addresses or private history. Only the
published query may feed the public calendar. The reference catalogue must never become
a public fallback on missing tables, empty results or errors. Requests cannot enable it.

An optional, separately authorized import operation can copy the eleven verified reference
candidates into **drafts**, with explicit actor and per-item history/audit. No May row. It
must be repeat-safe and must never overwrite Admin edits or publish anything. No such
import command or data migration exists now.

## Owner clarification: editable photos and a grid

The owner clarified that Admin must be able to upload a photo for an observance, edit
its content and display the cards in a grid. This establishes the requested behavior;
the earlier explicit schema-approval requirement still gates persistence implementation.

Proposed interface:

- Events → Annual Observances → create/edit a draft, upload/replace/remove one photo,
  enter its accessible description, edit the title/body/source/recurrence, preview and
  explicitly publish. Present the verified catalogue as optional starting content when
  creating a draft; choosing it must not publish or manufacture an actual event.
- Public twelve-month calendar: three columns on desktop, two on tablet, one on narrow
  mobile screens. Each published observance card shows its photo above its title,
  recurrence, description and official source. Preserve the full photo aspect ratio
  so text in a poster is not cropped; essential information also appears as readable text.
- A missing optional photo has a clean text card, not a fictitious stock photo. A month
  without published content has an honest empty state. May remains unselected unless
  an authorized Admin later creates valid content. Actual Upcoming/Past activities stay
  separate and functional.

Photo storage and history:

- Reuse `announcements.images.prepare_image` and the existing Events upload-size/pixel
  limits without changing actual Event behavior. Validate decoded content, reject invalid
  and unsupported files, normalize accepted input and require alternative text. Do not
  trust filename/MIME alone or expose unrestricted media URLs.
- A private preview route checks the observance-view permission. The public image route
  checks the current published status on every request, including after withdrawal.
  Historical photos require the separate revision-history permission and never become
  public through a guessed storage path or old revision ID.
- Each immutable revision stores the photo reference and alternative text. Replacing or
  removing the current photo must retain files referenced by historical revisions. Only
  a newly written, unreferenced upload may be cleaned up after transaction failure; do not
  copy the actual Event replacement behavior if it deletes history-referenced images.
- Add tests for upload limits/invalid bytes, missing alternative text, private and withdrawn
  image access, replacement/removal history, stale photo edits, audit rollback/file cleanup,
  and responsive photo-card rendering with keyboard/screen-reader semantics.

Approval requested next: authorize these dedicated Events models and an additive migration,
plus the Admin photo/edit/publish workflow and public grid, with migration testing confined
to fresh disposable MySQL. Applying the migration to the working application database is
a separate step requiring explicit approval and backup; no broad `migrate` invocation may
apply the pending EWAF migration as a side effect.

## Recurrence, publication and acceptance decisions

- No year-specific dates are derived, including last-Monday dates. January and October
  remain “third week”; do not infer a Sunday/Monday start or first-complete-week convention.
  Future date expansion needs authoritative conventions and boundary/leap-year tests.
- The user-selected names and dates are source-checked; legal-title variations and source
  errors are recorded in the validation note. June stays health related; May stays empty.
- Required next decision: approve the additive models/migration and bounded persistence
  implementation above. Permission assignments and actual initial publication are separate
  actions. Editing a published item is proposed to require withdrawal; approve this lifecycle
  with the schema, or specify retained-public-version editing before implementation.
- `Brainstorm Final.docx` was not found in `C:/Users/rovic/Documents/Capstone System`.
  Pages 4–5 were not inspected. The user's explicit dataset and official sources support
  the reference groundwork; do not claim verification of that missing document.
- No OQ-05 RSVP/audience decision, membership/PDAO enforcement, EWAF policy, eligibility,
  ranking, selection, release or other application workflow changes are authorized here.

After approval, acceptance must add permission-matrix tests, forged fields, CSRF, draft/
archive privacy, publication validation, immutable revisions, stale edit and publish tests,
audit-failure rollback, actual MySQL concurrency, explicit draft import idempotency and
migration preservation. Current groundwork tests cannot establish those unimplemented
persistence guarantees. Existing Event publishing/history/stale-edit tests remain regression
coverage for actual activities only.
