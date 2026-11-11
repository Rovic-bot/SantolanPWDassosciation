# Admin overview: ten-chart inventory — October 29, 2026

This authorized update supersedes the eight-bar/column presentation in the
[previous overview definitions](../dashboard-overview-2026-10-29/definitions.md).
The six summary metrics and their definitions remain unchanged. The existing
dashboard gate, per-module permissions, half-open date filtering, unavailable/error
states, private cache policy, and sidebar routes remain intact.

There is **no installed Chart.js asset or package in this repository**. These
charts use local SVG/HTML, generated from safe aggregate JSON and accessible HTML
tables. No Chart.js version is claimed, no library/plugin/CDN was added, and no
unsupported Chart.js API is used. The heatmap is a semantic HTML table.

## Common scopes and access

`/dashboard/` requires authenticated active staff with
`accounts.access_dashboard`; `analytics.services.overview` independently enforces
that gate. Queries execute only after the associated module permission check.
Existing module permissions have global record scope, not per-officer assignment.

Activity defaults to six calendar months through today. Custom dates allow at
most 731 inclusive days. Datetime filters use local midnight through midnight
after the end date, with the configured application timezone (Asia/Manila here).
The exact dates and timezone are shown with every activity chart. Current charts
show the refresh date; they do not pretend to be historical snapshots.

Permission groups below:

- **M:** `members.view_member`.
- **A:** `programs.view_program` and `programs.view_programapplication`.
- **E:** A plus `assistance.view_assistancecase`.
- **R:** E plus `assistance.view_assistancerelease`.
- **P:** `programs.view_program`.
- **D:** `assistance.view_referralticket`.
- **V:** `events.view_event`.

## Chart inventory

| Chart | Actual source, count and population | Date / exclusions | Access |
| --- | --- | --- | --- |
| Horizontal bar — Members by disability type | DISTINCT Member IDs within each recorded classification, across current nonarchived official Members (active and inactive). M2M classifications take precedence; legacy FK is fallback only when M2M is empty. Missing classification is separate. | Current snapshot; pending membership intake and archived Members excluded. Categories may overlap; no percentages forced to total 100%. | M |
| Column — Monthly assistance releases | `AssistanceRelease.objects.successful()`; distinct release IDs, plus DISTINCT recipient Member IDs from precisely the same qualifying releases. | Actual `released_on` DateField in selected dates, monthly bins. Voided releases excluded. Applications/selections without receipts never counted. No currency/value total. | R |
| Line — Program applications over time | DISTINCT `ProgramApplication` IDs grouped by submission month. Straight segments between monthly counts; no smoothed curve or inferred intermediate observations. | `submitted_at` in selected interval. All stored application states included; membership registrations, Desk tickets and RSVP excluded. | A |
| Pie — Programs by current status | One `Program.status` per program: Draft, Published, Cancelled, Archived. Total, counts and percentages displayed. These are the existing mutually exclusive lifecycle/publication codes, not a new composite lifecycle. | Current snapshot of all Program records. Application opening/closing schedules are not mixed into the pie. No invented Completed state. Active-program headline continues using existing `accepting_applications()`. | P |
| Donut — Community Assistance Desk status | One current `ReferralTicket.status` per ticket: Received, In review, Needs information, Referred, Closed. Total in the center; counts/percentages in legend/table. | `received_at` in selected interval. Feature-disabled source is Unavailable; no activation. Replies/closure/referral do not establish delivery. | D |
| Stacked horizontal — Eligibility outcomes by program | DISTINCT applications in the submission cohort, grouped by program and their one AssistanceCase eligibility code: Pending, Eligible, Needs Information, Ineligible, No review recorded, or Unrecognized outcome. | Same selected `submitted_at` cohort as the line. Current recorded findings only, not re-evaluation. No overlapping Submitted/Selected/Delivered stages added to stacks. Program names require existing program-view permission. | E |
| Area — Cumulative new memberships | Running sum of monthly Member joining counts. Each Member counted once, including records since archived. `joined_at` is stored when approved intake creates the official Member. | Selected `joined_at` period; cumulative total resets at range start. Monthly observations, not reconstructed historical active membership. No prior members carried into cumulative baseline. | M |
| Scatter — Applications versus recorded slots | One dot per Program, X = configured `slots`, Y = DISTINCT applications submitted within that program's full `[registration_opens_at, registration_closes_at)` window. Table identifies each numbered dot/program and its window. | Programs whose closing timestamp is in selected dates **and <= refresh time**. Unknown slots excluded and counted separately, never converted to zero. All stored publication states retained. Capacity means recorded configured slots, not slots remaining after selection. No success inference. | A |
| Histogram — Member age distribution | Current nonarchived official Members, grouped into equal-width ten-year age bins (0–9, 10–19, …). MySQL `TIMESTAMPDIFF(YEAR, birthdate, as_of)` computes completed years server-side; only bin counts are selected. | As of refresh date in application timezone. Missing and future birth dates counted separately and excluded. No arbitrary maximum age or medical/eligibility grouping. Database DateField validation rules out impossible calendar dates. Names, DOBs and individual ages never enter payloads. | M |
| Heatmap — Scheduled events by month and weekday | DISTINCT Event IDs in a month/year × Monday–Sunday matrix. One occurrence at its local start date, regardless of duration. Values and numeric color-scale ranges shown. | Selected `starts_at` dates. Draft/published/cancelled/archived scheduled records included and labeled; AnnualObservance references excluded. No RSVP, attendance or completion inference. | V |

The scatter intentionally uses a **closed-program cohort with full-window
submissions**, while the line/headline use a **submission-date cohort**. Their
totals need not match; both scopes are stated directly beside their charts.
Monthly activity endpoints may be partial months at the selected boundaries.

## Partitions, empty states and privacy

Pie and donut use a single stored state per record, so slices are complete and
nonoverlapping. Displayed percentages use largest-remainder rounding to 0.1% so
they total exactly 100% for nonempty populations. Empty populations have no fake
slices and no division by zero. Unknown stored codes become an aggregate
“Unrecognized state”; raw code values are not disclosed.

Successful empty queries show zero and an explicit no-matching-data message.
Unauthorized sources show Not permitted with no payload/count; disabled/missing
sources show Unavailable; other database errors show Could not load. A chart
rendering failure leaves its table available and is never converted into zero.

The browser receives only aggregated classification, program, status, date-bin,
age-bin, count, capacity and percentage data. Program names and program windows
are available only with program-view permissions. No individual member/applicant
IDs, birth dates, individual ages, income, clinical notes, scores, ticket text,
emails or attachment URLs are sent. Django escapes HTML and uses `json_script`;
the SVG renderer assigns labels with `textContent`, not innerHTML.

## Rendering and accessibility behavior

All ten visualizations have headings, programmatic names, scope, short summary,
visible values or labels, and a matching native View data table. Pie/donut slice
numbers match their labeled count/percentage legends. Stacks label program totals
and nonzero outcome counts; scatter dots map to numbered table rows. Labels wrap
and no classification/program is dropped to fit a fixed-height card.

The layout has at most two chart columns, with the long-label stacks and heatmap
using the full row. It becomes one column on narrower screens. SVG text is redrawn
at the current font size when the sidebar, viewport or text preference changes.
At enlarged text sizes, bounded keyboard-scrollable chart/table regions preserve
readable labels without page-level horizontal scrolling. Charts have no animation,
hover-only data, draggable controls or external rendering service. Current high
contrast and forced-colors preferences retain labels and boundaries.

Native tables are open by default when JavaScript is unavailable. Successful
rendering collapses the redundant data disclosure once; resizing does not override
the user's open/closed choice. No data is hidden behind tabs or a carousel.

No chart is unavailable because of a missing schema/source in the current local
installation. Individual charts can correctly be empty for a selected cohort
(especially the closed-program scatter), or restricted by permissions. A one-month
line/area has a single observation, shown as a point rather than invented history.

## Scope preservation

This adds/changes only read-only aggregations and dashboard presentation/tests.
The previously removed management-card wall remains absent. Existing shell,
sidebar routes, module actions, EWAF criteria/weights/calculation/ranking,
registration/verification/eligibility rules, beneficiary decisions, releases,
publication controls, permissions, credentials, flags and schema are unchanged.
No feature activation, migrations, dependencies, commit, push or deployment.
The accepted milestone is unchanged.
