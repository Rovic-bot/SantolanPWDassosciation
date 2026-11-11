# G07-B — Public Programs availability and lifecycle clarity

Owner-defined baseline: **70%, unchanged**. Branch: `feature/events`.
Starting commit: `23d036559cffee19614383a39fb56ad12d52f4ce`; clean working tree
confirmed before implementation. This increment is local and awaits owner review.
No staging, commit, push or Render deployment is authorized.

## Authority and scope

Reviewed `../CURRENT_SYSTEM_SPECIFICATION.md`, `../Guide for Development.md`,
`../00 - Project Overview/Open Decisions.md`, the public portal source extraction,
`../05 - Development/October 10 Implementation Impact.md`, and the G07 validation
record and implementation. The approved public workflow supports Available,
Upcoming (view), and Past browsing. This change presents the existing registration
policy; it does not implement pending policy, EWAF, eligibility or evidence rules.

Previously the list defaulted to programs with future closing dates and labelled
every non-open, non-cancelled row “Applications closed,” including future opening
dates and incomplete authorization. Detail pages had the same closed fallback.

The default is now **All programs**, with server-side filters for Available now,
Upcoming, Past application periods, and Cancelled / unavailable. Every previously
publicly visible program remains browsable. Draft, archived and future-publication
records remain hidden; no publication criteria are relaxed.

Public lifecycle labels use this precedence:

1. Cancelled status: **Cancelled program**, regardless of application dates.
2. Closing time reached: **Application period ended**.
3. Opening time not yet reached: **Upcoming application period**, with its
   scheduled opening time and guidance to check for updates.
4. Existing `registration_available` policy satisfied: **Applications open**.
5. Otherwise: **Applications unavailable**, explaining incomplete application
   arrangements and directing visitors to check back or contact the Help Desk.

Upcoming means a scheduled period, not a promise that authorization or readiness
will be completed. An incomplete program remains upcoming before opening and
ended after closing; during its window it is unavailable. Cancellation always
overrides those date labels. No new approval or eligibility rules are inferred.

`?period=current` retains its original future-closing-date semantics and displays
an active “Current application periods” filter when visited. `?period=past` retains
closing-time-at-or-before-now semantics, including cancelled rows. A cancelled
program whose application period ended therefore appears in both Past and
Cancelled / unavailable. Existing detail URLs are unchanged. Unknown period
values fall back to All programs. Pagination retains the selected period.

## Implementation

- `programs/models.py`: the G07 availability predicate is shared between
  `accepting_applications()` and a lifecycle SQL annotation. Optional `at` arguments
  on public/availability querysets allow one timestamp per request. The original
  `Program.registration_available` property is unchanged, including the exact
  inclusive opening, exclusive closing and Python-compatible whitespace rules.
- `programs/views.py`: only public list/detail handlers change. Filter in SQL,
  paginate ten rows, and use the same instant for publication, lifecycle, filters
  and the detail Apply link. Available/upcoming/past filters use relevant date
  ordering with primary-key tie breakers; other filters preserve model ordering.
- `templates/programs/public_list.html` and `public_detail.html`: accurate text,
  application dates, semantic `time` elements, category-specific empty states and
  active filter links. Existing public styling, navigation and detail guidance
  are reused; there is no CSS change or redesign.
- `templates/programs/availability_label.html` and `availability_message.html`:
  shared labels/explanations for consistent list/detail presentation.
- `programs/test_public_availability.py`: 18 synthetic backend tests.
- `scripts/program_availability_browser_qa.py` and `.cjs`: two explicit browser
  tests using synthetic live-server fixtures.
- This validation record.

The homepage and its 13 G07 tests are unchanged. Its `exists()` query is preserved.
The actual verification/application service guards remain unchanged and recheck
policy on use. The detail Apply link uses the shared G07 predicate at the request
timestamp; it does not grant access. Private evidence, member matching, throttles,
Admin UI, EWAF computations, navigation and the 70% baseline are untouched.

## Validation environment and commands

Before database-backed tests, confirmed no inherited database target or Django
settings variables. Each run initialized a fresh native MySQL 8.4.11 data directory
in Windows temp, bound only to loopback on a new port. The harness checked actual
`@@datadir` against that fresh directory before creating synthetic credentials.
Dotenv loading was disabled, DEBUG was false, and Django used only
`test_g07b_disposable`. An empty `review_unused` schema on that same fresh instance
was used for database checks. The test runner applies existing migrations only
to its disposable test schema; no application database migrations were run.

No development `.env`, production credentials, existing `.local` database files,
real member records, Aiven, Supabase or hosted Render databases were accessed.
MySQL binaries were reused without connecting to any existing server.

Commands ran with the harness's isolated synthetic environment:

```text
manage.py check --database default
manage.py makemigrations --check --dry-run
manage.py test programs core.tests.test_home_program_availability --noinput --verbosity 1
manage.py test --noinput --verbosity 1
manage.py test scripts.program_availability_browser_qa scripts.public_navigation_browser_qa --noinput --verbosity 1
python -m pip check
manage.py check --deploy --settings=config.settings_production
git diff --check
git diff --cached --name-only
```

Focused backend tests cover exact opening/closing microseconds, publication
boundaries, all five lifecycle states, both empty/whitespace-only instruction
fields, padded meaningful instructions, missing authorization, hidden records,
legacy links, mixed collections, stable pagination, empty states, safe invalid
parameters, accessible text/dates, detail Apply parity, and direct verification
guard rejection. Query assertions check one count and one limited program query;
clock assertions check one lifecycle evaluation instant per public request.

- Focused backend suite: **90 passed**, 17.955 seconds, including all 13 G07
  homepage tests and the 18 new G07-B backend tests.
- Complete Django regression suite: **425 passed**, 84.088 seconds (407 existing
  plus 18 new tests); no failures or skips. Focused counts are included here,
  not additive.
- Browser suite: **3 passed**, 23.209 seconds: two new G07-B tests and the existing
  public navigation test. Chrome checked all five lifecycle states, filters,
  legacy bookmarks, pagination, empty states, Apply-link visibility, all seven
  public navigation destinations, keyboard use, no-script browsing, 200% text and
  high contrast. Widths: 320, 390, 768, 1024 and 1440 pixels; no horizontal overflow
  or JavaScript exceptions detected. Mobile/desktop listing and upcoming-detail
  screenshots were also visually inspected. Synthetic screenshots are ignored
  under `.local/qa-g07b/`; no screenshots or database files enter the change set.
- Django checks, including the disposable database check: no issues.
- `makemigrations --check --dry-run`: **No changes detected**.
- Dependency check: no broken requirements.
- Synthetic production-settings deployment check: no errors; existing
  `security.W005` / `security.W021` HSTS subdomain/preload warnings remain.
  This check used synthetic configuration and did not contact a hosted database.
- `git diff --check`: passed. Tracked and untracked paths were reviewed; exactly
  the ten files listed above changed. Staged index remains empty. No secret,
  credential, private data, database, migration, Admin UI or unrelated file is
  included. AST comparison confirms the Program model/property and all view
  functions outside public list/detail are unchanged.
- Django destroyed its disposable test databases and each isolated MySQL process
  stopped. Synthetic server artifacts remain in Windows temp, outside the repo.

## Limits and release

No unresolved policy decision blocks these presentation changes. Existing open
decisions remain open; this increment does not authorize future workflow changes.
Availability remains a request-time snapshot, not a reservation or guarantee of
acceptance. SQL/property parity must be maintained if registration policy changes.
The database validation targets native MySQL, not alternate database engines.
Browser checks are focused automated checks, not comprehensive assistive-technology
testing or owner acceptance. Hosted acceptance is intentionally not performed.

No schema changes, migrations or dependencies are required. Owner review is the
next step before staging/committing/pushing to `feature/events`. Render remains a
separately approved manual deployment milestone. Suggested commit message:
`Clarify public program availability and application periods`.
