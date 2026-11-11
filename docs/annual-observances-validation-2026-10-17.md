# Annual observances groundwork validation

**Historical groundwork record.** The owner subsequently approved dedicated persistence,
photo uploads and publication implementation with disposable testing. See
[current persistence validation](annual-observances-persistence-validation-2026-10-17.md)
for the delivered workflow and remaining operational migration boundary. The source
verification table below remains applicable; the read-only limitations below describe
the earlier increment only.

Date: October 17, 2026. Branch: `feature/events`. Accepted milestone: **70%, unchanged**.

## Delivered scope and authorization

No dedicated annual-observance schema authorization was found. The current request's
safe-groundwork fallback was followed. See the concrete
[schema and service proposal](annual-observances-schema-proposal-2026-10-17.md).
**No models/migrations were added, no operational migration was run, no permission was
granted, no record was seeded or published, and no actual Event was manufactured.**

- Public `/events/`: separate twelve-month annual calendar with publication empty states,
  month links, semantic headings and the retained Upcoming/Past activities and pagination.
- Admin `/events/manage/observances/`: eleven source-checked **reference candidates**, not
  persisted drafts. Existing active/staff/dashboard/Event-view authorization is checked
  in the service and request path. Read-only; all mutation methods rejected. No override
  for technical superusers. GET and HEAD do not create observance/Event/audit records.
- Annual Observances is a child link inside existing Programs & Events; exactly eight
  sidebar groups remain for the full Admin. Existing light/white styling, outline icons,
  teal accents and active-link behavior remain.
- Shared responsive cards show title, explicit annual recurrence, category, description,
  legal basis and individually named official source links. June is health related, not
  PWD-specific; May has no selected candidate. Nothing derives year-specific dates.
- The reference catalogue has no status flag that a request can promote. Public service
  deliberately returns empty months; no CMS/file/session database substitute or fallback.

Creating/editing durable drafts, publication, optimistic persistence, transactional
revision/audit history and their permissions remain **proposed, not implemented**. Existing
actual-event publication/history/stale-edit regression tests are not evidence that those
new observance workflows exist. The proposal specifies their acceptance tests.

Read authority: local AGENTS.md, CURRENT_SYSTEM_SPECIFICATION, Guide for Development,
System Master Specification, October 10 Implementation Impact, Open Decisions, DEC-024–027,
the confirmed membership/PDAO amendment, Public Portal annual-theme notes and current
Events/revised70/durable-backend validation. Historical DEC-013 and EWAF-specific schema
approval were not repurposed as annual-observance approval.

## Official source review

Cross-checked against the [NCDA calendar of disability celebrations](https://ncda.gov.ph/)
and the individual official references below on October 17, 2026. This is the owner's
selected subset, not a claim to list every national observance. May is deliberately
unselected; no inference that May has no observances anywhere. June is an additional
health-related selection and is not relabeled as a PWD-specific observance.

| Month | Selected title and recurrence | Official reference |
| --- | --- | --- |
| January | National Autism Consciousness Week — third week | [Proclamation 711, s. 1996, NCDA](https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-711/) |
| February | National Down Syndrome Consciousness Month — whole month | [Proclamation 157, s. 2002, Senate](https://issuances-library.senate.gov.ph/executive-issuance/proclamation-no-157-s-2002) |
| March | Women with Disabilities Day — last Monday | [Proclamation 744, s. 2004, NCDA](https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-744/) |
| April | World Autism Awareness Day — April 2 | [UN observance and Resolution 62/139 reference](https://www.un.org/en/observances/autism-day/) |
| May | No selected observance | No candidate or Event row |
| June | National Kidney Month — whole month; health related | [Proclamation 184, Senate](https://ldr.senate.gov.ph/executive-issuance/proclamation-no-184); [1993 legal-basis cross-check, National Nutrition Council](https://nnc.gov.ph/luzon-region/keep-your-kidneys-in-good-shape/) |
| July | National Disability Rights Week — July 17–23 | [Proclamation 597, s. 2024, NCDA](https://ncda.gov.ph/declaring-the-period-of-17-to-23-july-of-every-year-as-national-disability-rights-week-proclamation-no-597/) |
| August | White Cane Safety Day — August 1 | [Republic Act 6759, section 3, NCDA](https://ncda.gov.ph/disability-laws/republic-acts/republic-act-6759/) |
| September | Cerebral Palsy Awareness and Protection Week — September 16–22 | [Proclamation 588, s. 2004, NCDA](https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-588/) |
| October | National ADHD Awareness Week — third week | [Proclamation 472, s. 2003, NCDA](https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-472/) |
| November | Deaf Awareness Week — November 10–16 | [Proclamation 829, s. 1991, NCDA](https://ncda.gov.ph/disability-laws/proclamations/proclamation-829/) |
| December | International Day of Persons with Disabilities in the Philippines — December 3 | [Proclamation 1157, s. 2006, section 1, NCDA](https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-1157/) |

Source reconciliation:

- January's legal text calls it Autism Consciousness Week; NCDA's current calendar adds
  National, matching the requested display title. Its initial 1996 date range is not a
  perpetual fixed-date rule. January/October remain descriptive third-week recurrences.
- October's legal heading spells out Attention Deficit/Hyperactivity Disorder (AD/HD).
  The requested short display title is retained with the full proclamation citation.
- July uses the current rights-week title; old NDPR wording occurs only in the legal
  instrument's historical background, not as the current application title.
- November's NCDA heading/current calendar says Deaf Awareness Week; the operative
  proclamation text says Deafness Awareness Week. The description records this variation.
  The final card links directly to NCDA's proclamation, not an annual event advisory.
- December's NCDA page heading contains “December 2”; the reproduced proclamation title,
  section 1 and current calendar specify December 3. December 3 is used.
- `Brainstorm Final.docx` was not found by filename search throughout the local Capstone
  System directory. Its pages 4–5 were **not inspected**. No claim of access to that original.
- Some external PDF fetches were unavailable to the research tool. Final application links
  use readable official HTML references; no runtime network lookup or link-fetch service
  was added. URL validation verifies structure/host, not the future truth of external text.

## Exact file inventory

Six existing files modified:

| File | Change |
| --- | --- |
| `core/templatetags/workspace_navigation.py` | Child link and precise active-state handling within Programs & Events |
| `events/services.py` | Read-only, RBAC-protected reference service and empty public calendar service |
| `events/views.py` | Preview view and public calendar context; actual Event filtering retained |
| `events/urls.py` | Read-only management route |
| `templates/events/manage_list.html` | Annual Observances link within Events |
| `templates/events/public_list.html` | Separate annual calendar, shared stylesheet, logical activity heading levels |

Nine new files:

| File | Purpose |
| --- | --- |
| `events/observances.py` | Immutable reference candidates, recurrence and official-URL validation, minimal card projection |
| `events/test_observances.py` | Sixteen tests for reference integrity, recurrence validation, authorization, privacy, methods, navigation and Event regression |
| `templates/events/observance_calendar.html` | Shared accessible twelve-month card/list partial |
| `templates/events/observances.html` | Private read-only reference preview and availability explanation |
| `static/css/observances.css` | Responsive month cards, focus states and forced-color borders |
| `scripts/observances_browser_qa.py` | Fictional Admin plus disposable live-server browser test |
| `scripts/observances_browser_qa.cjs` | Browser assertions and screenshots |
| `docs/annual-observances-schema-proposal-2026-10-17.md` | Concrete approval proposal, fields, constraints, permissions, transactions and acceptance |
| `docs/annual-observances-validation-2026-10-17.md` | This inventory, source record and validation evidence |

Ignored local evidence: `.local/observances-20261017/baseline.json`, preservation report
and screenshot directory. Baseline captured **526** tracked/staged/untracked nonignored
files. Only the six intended existing files differ; the other **520** retain their bytes.
All pre-existing EWAF/G12–G17/startup changes are preserved. Git index and HEAD unchanged;
no pull/reset/stash/clean/stage/commit/push/merge/deploy performed.

## Test commands and results

The existing `scripts/g12_test_runner.py` was read before execution. It starts a fresh
MySQL 8.4.11 datadir on an unused loopback port, verifies its identity, disables `.env`,
and restricts grants to `g12_empty` and `test_g12_disposable`. The durable runner verifies
the fresh instance before migrations and establishes only its existing test capability.
No application data, credentials, real members or private uploads were read or modified.

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test events.test_observances --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test scripts.observances_browser_qa --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test events.test_observances scripts.observances_browser_qa --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py check --database default
git diff --check
```

| Check | Result | Evidence under temporary `santolan-g12-tests-…/django.log` |
| --- | --- | --- |
| New focused tests | 16 passed; 0 failures/errors, 0.182 s | `rk5k3f59` |
| Full discovered project suite | 919 passed; 0 failures/errors, 328.150 s | `1o_8amsc` |
| Browser calendar | 1 passed; 0 failures/errors, 9.113 s | `5lg65ge6` |
| Final focused + browser after direct November URL refinement | 17 passed; 0 failures/errors, 7.613 s | `y1o7o_9s` |
| Migration consistency | Exit 0, No changes detected | `mz06ligz` |
| Django/database checks | Exit 0, no issues | `9b05b4rf` |
| Whitespace | Exit 0; only line-ending notices | Local command output |

The reported 898 tests remain historical evidence; today's full discovered suite is 919.
No new full-suite count is inferred from old documentation. The full run loaded the
initial official November advisory link; the final focused/browser rerun validates the
replacement direct proclamation URL and refreshes screenshots. No other behavior changed.
Initial sandbox attempts failed before tests because temporary `mysql.ini` creation was
denied; authorized outside-sandbox retries used the same isolated harness. These were
environment launch failures, not failing test cases.

The new tests cover anonymous/nonstaff/inactive/missing-permission access, service-level
RBAC, read-only method rejection even for superusers, public query-parameter isolation,
draft/archive Event privacy, pagination/period behavior, escaping, named source links,
recurrence shapes, invalid month/day/range inputs and misleading/unsafe URLs. No observance
model/permission is installed as a side effect. Existing tests also pass for actual-event
forged publication, stale versions, protected history and publication audit rollback.

Browser checks: 320/390/768/1024/1440 px; twelve months, eleven private candidates and zero
public candidates; keyboard skip link/month-anchor focus; visible focus; largest text/high
contrast; forced colors; JavaScript disabled at 320 px; Upcoming/Past controls; named
official source links; eight sidebar groups; one active child; zero JavaScript errors.
Desktop Admin and mobile public screenshots were visually reviewed. Screenshots are in
`.local/observances-20261017/screenshots/` (standard, large-contrast and forced-colors views).

## Remaining decisions and limitations

Approve the dedicated schema/persistence lifecycle before implementing durable editing,
publication and revision/audit transactions. Assign new permissions explicitly and publish
reviewed drafts explicitly later; none is auto-enabled here. The proposal recommends
withdraw-before-edit for published items, subject to owner approval. Source-checked
reference material does not itself authorize publication.

No year-specific recurrence derivation, live observance persistence, draft saving,
publication or history browser exists yet. No source-URL reachability guarantee. No full
manual screen-reader/assistive-device/UAT or WCAG conformance certification is claimed.
Only the dedicated calendar browser harness was run in addition to the full discovered
unit/integration suite; other opt-in historical browser scripts were not rerun.
Milestone stays 70%; operational migration and deployment remain outside this work.
