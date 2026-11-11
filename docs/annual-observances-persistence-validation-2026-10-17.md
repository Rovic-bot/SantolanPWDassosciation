# Annual observances, photo editing and publication validation

**Startup follow-up:** the owner subsequently reported that Start System was blocked.
The [October 17 startup correction](start-system-observances-fix-2026-10-17.md) now permits
the exact reviewed Events migration to remain pending while the rest of the site runs.
This supersedes the startup-blocking statement below. Observance editing still requires
the separately authorized working-database migration; none was applied by the correction.

Date: October 17, 2026. Branch: `feature/events`. Accepted milestone: **70%, unchanged**.

## Authorization and operating status

The owner requested photo uploads/editing in Admin and a grid layout, then replied
“yes i approve” to the explicit dedicated-model/migration implementation proposal.
That approval question covered implementation and disposable-database testing and
expressly reserved migration of the working database for a separate step.

`events/0006_annual_observances.py` is implemented and exercised on disposable MySQL.
**No working database migration, backup, permission assignment, seed or publication has
been performed.** No real members, application credentials or private uploads were used.
Source references are optional form starting points; a GET never creates a row.
The eleven references are not automatically saved or published.

The remaining operational action is a verified backup followed by an approved,
targeted `manage.py migrate events 0006_annual_observances`, after inspecting its plan.
Do not run an unrestricted `migrate`: the unrelated pending EWAF migration must remain
under its existing approval controls. The disposable migration test verifies that
targeting Events does not apply `ewaf/0005_durable_development`.
The existing startup guard is unchanged: **Start System will reject an unapproved
pending Events migration until that separate operational step is completed.** An already
running application returns empty public months and a setup-pending Admin screen when
the new tables are absent. New observance create/edit requests return 503 in that state;
detail/image requests return 404. No substitute persistence is used.

## Delivered behavior

- Public Events has a twelve-month grid: three columns on desktop, two on tablet, one
  on narrow screens. Published cards show optional uncropped photos, meaningful alt text,
  title, category, descriptive annual recurrence, description, legal basis and source link.
  “No published observances for this month” means there is no publicly published card
  in that month, not that the observance does not exist. May has no selected reference.
- Actual association activities retain their Upcoming/Past filters, pagination, detail,
  publication and registration behavior. Annual observances have no Event/Member/Program FK,
  fabricated venue, schedule, attendance or RSVP.
- Admin > existing Programs & Events > Annual Observances supports create/edit drafts,
  optional JPEG/PNG upload/replacement/removal, review, explicit publication, withdrawal,
  archive and restore-to-draft. Published items must be withdrawn before editing.
  Ordinary Admins require explicit new view/add/change/publish permissions; historical
  Event permissions do not grant them. No ninth sidebar group was added.
- Services reload the actor before checking active/staff/dashboard and dedicated
  permissions, lock edited rows, compare expected versions and atomically store aggregate,
  complete revision snapshot and audit record. Stale edits do not overwrite changes.
  Client fields cannot forge status, actor or publication timestamps.
- Revision and audit viewers require separate view permissions. History stores reasons,
  actors, timestamps, content and before/after values. ORM updates/deletes and instance
  overwrites are blocked; protected FKs preserve history. History actors use PROTECT,
  a deliberate strengthening of the original SET_NULL proposal. Direct database-owner
  SQL is not made immutable by application-level guards.
- Images use the existing normalization/validation pipeline (5 MiB, 16 million pixels),
  random dedicated paths and permission-checked routes. Public routes serve only the
  currently published image; historical photos require private revision access. Replaced
  or removed images remain available in historical revisions. A failed write/audit removes
  its newly written image; database content rolls back together.
- Whole-month, fixed day/range, last Monday and third week remain explicit descriptive
  rules. No year-specific date calculation or ambiguous week convention is introduced.
  June remains health related, not PWD-specific. July uses National Disability Rights Week.

Official source review and all eleven direct source URLs remain in the
[groundwork source record](annual-observances-validation-2026-10-17.md#official-source-review).
`Brainstorm Final.docx` was not located; its pages 4–5 were not inspected. The supplied
selection was cross-checked against official NCDA, Senate and UN sources. Source URL
validation allows only reviewed HTTPS hosts and rejects credentials, ports, query strings,
fragments and misleading hostnames; it does not fetch or certify future source content.

## Actual file inventory for this approval increment

Fifteen existing files modified (relative to the captured 535-file follow-up baseline):

| File | Change |
| --- | --- |
| `core/templatetags/workspace_navigation.py` | Dedicated observance permission and active child link |
| `events/models.py` | Register the three dedicated models; existing Event classes unchanged |
| `events/services.py` | Publication projection, service RBAC, transactional edit/publication/history |
| `events/views.py` | Private CRUD/review, current/history image routes and pending-schema behavior |
| `events/urls.py` | Dedicated observance routes |
| `events/test_observances.py` | Adapt sixteen groundwork tests to durable model permissions |
| `scripts/observances_browser_qa.py` | Fictional uploaded poster and persisted browser assertions |
| `scripts/observances_browser_qa.cjs` | Upload/edit/publish/withdraw/history and responsive-grid checks |
| `static/css/observances.css` | Uncropped responsive photo and preview styling |
| `templates/events/manage_list.html` | Dedicated-permission management link |
| `templates/events/observance_calendar.html` | Published photo and private reference-start link |
| `templates/events/observances.html` | Saved records and optional verified-reference grid |
| `templates/events/public_list.html` | Publication-aware introduction and grid context |
| `docs/annual-observances-schema-proposal-2026-10-17.md` | Follow-up approval and implementation link |
| `docs/annual-observances-validation-2026-10-17.md` | Mark earlier groundwork status historical |

Eight new files:

| File | Purpose |
| --- | --- |
| `events/observance_models.py` | AnnualObservance, AnnualObservanceRevision and AnnualObservanceLog |
| `events/observance_forms.py` | Content/photo and explicit publication forms |
| `events/migrations/0006_annual_observances.py` | Additive three-model migration, constraints/index; no RunPython/seeds/grants |
| `events/test_observance_workflow.py` | Twenty-three workflow, concurrency and migration tests |
| `templates/events/observance_edit.html` | Accessible multipart draft editor |
| `templates/events/observance_detail.html` | Card review, publication, paginated revision/audit history |
| `templates/events/observance_unavailable.html` | Setup-pending editor response |
| `docs/annual-observances-persistence-validation-2026-10-17.md` | This approval, inventory and validation record |

The earlier increment additionally introduced `events/observances.py`; its verified
reference content is unchanged in this increment. The earlier source record lists its
complete groundwork inventory.

## Test commands and evidence

All database commands below use the existing isolated harness: fresh MySQL 8.4.11 on
loopback, verified disposable datadir, `.env` disabled and grants limited to `g12_empty`
and `test_g12_disposable`. Test photos and actors are fictional. Browser photos/media
are confined to temporary directories; screenshots are ignored local evidence.

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test events.test_observances events.test_observance_workflow scripts.observances_browser_qa --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py sqlmigrate events 0006_annual_observances
git diff --check
```

| Check | Result | Temporary harness artifact suffix |
| --- | --- | --- |
| Focused workflow + browser | 40 passed, 0 failures/errors; 47.007 s | `8z73ckys` |
| Full discovered suite | 942 passed, 0 failures/errors; 358.884 s | `x2icucm1` |
| Migration consistency | Exit 0; no changes detected | `q1j1b4ha` |
| Migration SQL | Exit 0; only new observance tables, constraints, indexes and FKs | `fy8w_9cd` |
| Django system checks | No issues during focused/full test setup | Above test logs |
| Whitespace | `git diff --check` exit 0; line-ending notices only | Local output |

The final focused run includes sixteen adapted groundwork tests, twenty-three durable
workflow tests and one browser scenario. It covers service/request permissions, no silent
grants, draft/public privacy, immutable revisions, audit rollback including photo cleanup,
stale edits, two concurrent writers on MySQL, upload limits/form validation, official URL
validation, recurrence rendering, CSRF, publication confirmation, historical image access,
missing-storage behavior and migration preservation. It verifies a targeted Events
migration leaves EWAF 0005 unapplied and does not seed observances or alter an actual Event.
The historical 898 count and the earlier groundwork 919 count are retained as historical
evidence; the current full-suite result is 942. The focused tests overlap the full suite
and must not be added to it as a count of distinct unit/integration tests. The browser
scenario is opt-in and was explicitly included in the focused run.

Initial focused iterations exposed test-harness issues: a missing reference-explanation
paragraph, manual streaming-response closure invalidating a Django TestCase connection,
POST data containing None, and a history locator that needed to open the specific revision
details instead of matching both revision and audit summaries. These were corrected.
The first run had 1 failure/9 errors; the next had 1 failure/1 error; the third passed all
39 non-browser tests but its browser selector failed. That third harness also encountered
a Windows cp1252 logging exception while rendering the failure; the final UTF-8-enabled
run completed cleanly. These intermediate results are not reported as passing runs.

Browser checks cover 320/390/768/1024/1440 px, the public 3/2/1-column grid, photo creation,
draft review, publication, withdrawal, replacement, republishing, historical-photo link,
keyboard skip/month focus, large text/high contrast, forced colors, JavaScript disabled,
eight Admin groups and zero JavaScript errors. Desktop public grid, mobile public grid,
mobile editor and mobile review screenshots were visually inspected. They preserve the
light/white Admin, teal highlights, readable labels and uncropped photos. Screenshots
are under `.local/observances-persistence-20261017/screenshots/`.

Preservation audit: the 535-file baseline has exactly the fifteen intended existing-file
changes listed above; the other **520 files retain their bytes**. Eight files were added,
none deleted. Git index and HEAD are unchanged, and the branch remains `feature/events`.
All pre-existing EWAF/G12–G17/startup work is preserved. Evidence is in
`.local/observances-persistence-20261017/baseline.json` and `preservation.json`; generated
SQL is in `migration-sql.txt`. These ignored evidence files are not application content.

## Limits and remaining decisions

- Approval to back up and migrate the working database remains outstanding. Specific
  ordinary Admin role assignments and actual content/photo publication remain explicit
  owner/Admin actions. No automatic publication or silent permission grants.
- No year-derived calendar dates. A future date-expansion feature requires validated
  week/leap-day conventions and boundary-year tests.
- Image history is deliberately retained. Retention policy and crash-orphan cleanup
  are not implemented here; the filesystem cannot participate in a database transaction.
  Normal service exceptions clean up new images, but a process crash or an external
  caller rolling back a later enclosing transaction can leave an unreferenced file.
- Automated keyboard/layout/contrast checks and visual inspection do not certify WCAG
  compliance or replace manual screen-reader and owner acceptance testing.
- No pull, reset, stash, clean, staging, commit, push, merge or deployment. No milestone
  increase; EWAF, PDAO, assistance selection, membership, program terms, normal application
  processing and actual Event workflows remain outside this implementation.
