# Dashboard overview: data definitions

Authorized October 29, 2026 scope: replace the dashboard presentation and add
read-only analytics. The accepted 70% milestone is unchanged. No domain workflow,
permission, feature flag, setting, schema, migration, or existing route is changed.

## Access and refresh

`core:dashboard` remains `/dashboard/`. The existing `dashboard_required` gate
requires authenticated, active staff with `accounts.access_dashboard`. GET/HEAD
only, with the existing private/no-cache response policy. `analytics.services.overview`
also enforces this gate when called directly. Each source checks its module
permissions before running any query. There are no aggregate API endpoints,
exports, caches, or separate table requests to bypass the gate.

The permissions reuse `reports.services.PERMISSIONS` and
`assistance.services.VIEW_PERMISSIONS`, plus the existing event and Desk view
permissions. Existing module access is global rather than row-assigned; these
aggregates use the same scope. No permission is widened.

The page shows the request's refresh time, not a real-time update claim. Counts
are separate SELECTs under the configured database isolation; concurrent writes
can make adjacent counts briefly differ. No locks or business writes are added.

Existing detailed report/export access audits remain in `reports.views` and
`reports.services.record_access`. The previous dashboard had no access-audit
write. This aggregate-only dashboard does not invoke a report export, read private
attachments, or introduce an audit exemption on those underlying routes.

## Dates

- Application default timezone: `settings.TIME_ZONE` (Asia/Manila in this installation).
- Default: first day of the month five months before today through today (six
  calendar months including the current partial month).
- Presets: last 30 inclusive days, last six calendar months, this year through today.
- Custom: two valid dates, start <= end, at most 731 inclusive days, years 1900–2100.
  Future dates are accepted for event scheduling; they do not imply delivered activity.
- Datetimes use timezone-aware `[start midnight, day-after-end midnight)` bounds.
  Delivery's DateField uses the equivalent date interval. Monthly boundary gaps
  are zero only for successful queries against retained records. No previous-period
  growth percentages or reconstructed active-member histories are provided.
- Python constructs month boundaries; conditional SQL counts do not require
  installed MySQL named-timezone tables. At most 25 partial/full month buckets.
- Snapshots ignore activity dates explicitly. Invalid filters return HTTP 400 and
  run no analytics. Sources with missing required timestamps are counted separately
  as undated and excluded from period attribution; no date is guessed. Current
  schema makes all five relevant activity dates non-null.

## Supported measures

| Measure / unit | Source and definition | Date / kind | Required module permission(s) |
| --- | --- | --- | --- |
| Official members / distinct Member IDs | `Member`, `archived_at IS NULL`; active and inactive official records. Pending MembershipApplication records are excluded. | Current snapshot | `members.view_member` |
| Membership growth / distinct Member IDs | All retained Member rows, including subsequently archived members. `joined_at` is stored when approval creates the Member. Counts joins, not historical active membership. | `Member.joined_at`; period activity | `members.view_member` |
| Disability classifications / members per classification | Same current member population. M2M `disability_types` takes precedence; the legacy `disability_type` FK is used only when M2M is empty, matching `PersonalRecord.disability_ids`. DISTINCT per classification; recorded retired classifications are retained. Missing structured classification is separate. No free-text inference. | Current snapshot; categories overlap | `members.view_member` |
| Confirmed assistance releases / release IDs | Existing `AssistanceRelease.objects.successful()` (`voided_at IS NULL`). This model records confirmed delivery; it has no pending/failed delivery rows. No selections, applications, or Desk tickets substitute for receipts. | `released_on`; period activity | `programs.view_program`, `programs.view_programapplication`, `assistance.view_assistancecase`, `assistance.view_assistancerelease` |
| Distinct recipients / Member IDs | DISTINCT `AssistanceRelease.application.member_id` over exactly the same qualifying releases and dates. Multiple releases to one member remain one recipient. | `released_on`; period activity | Same release permissions |
| Program applications / distinct application references | `ProgramApplication`, including all stored states. Does not count membership intake, Desk requests, or EventParticipation/RSVP. Existing event-linked ProgramApplication contexts remain program applications under the current model. | `submitted_at`; submission cohort, current stored outcomes | `programs.view_program`, `programs.view_programapplication` |
| Eligibility findings / cohort application IDs | LEFT join to each application's one AssistanceCase, grouped by eligibility code. Pending, Eligible, Needs Information, Ineligible, and No eligibility review recorded. This is the stored review, not a fresh eligibility evaluation. Not added to application-state totals. | Same `submitted_at` cohort; current stored findings | Application permissions plus `assistance.view_assistancecase` |
| Active programs / distinct Program IDs | Existing `Program.objects.accepting_applications(at=request_time)` query, including publication/window/policy/event/PDAO checks as currently configured. No flag changed. | Current snapshot | `programs.view_program` |
| Program publication states / distinct Program IDs | All Program records grouped by existing Draft, Published, Cancelled, Archived states. Publication alone does not mean accepting applications; a past closing date does not invent completion. | Current snapshot | `programs.view_program` |
| Scheduled events / distinct Event IDs | Actual scheduled Event records grouped monthly by start date. All recorded publication states included, with current state counts in the summary. Does not claim that draft/cancelled/past events occurred or completed. AnnualObservance reference entries excluded. | `starts_at`; period schedule | `events.view_event` |
| Community Assistance Desk / distinct ReferralTicket IDs | Existing ticket model, grouped by Received, In review, Needs information, Referred, Closed. Closure/referred/email is not assistance delivery. Feature-disabled state displays Unavailable without querying tickets. | `received_at`; submission cohort, current stored states | `assistance.view_referralticket` |

Status charts include every observed state, including needs-information and
unreviewed cases. Unknown codes are counted under “Unrecognized state,” never
rendered as raw database text. Known zero-status categories are omitted from both
chart and table; monthly zero buckets remain visible. Counts start at zero with
whole-number scale labels. No financial totals, capacity-derived receipts,
attendance estimates, scores, rankings, or inferred clinical categories are shown.

## Rendering and failure handling

The repository has no installed Chart.js or other chart library. Charts use
server-rendered HTML/CSS bars and monthly columns, preserving the existing Django,
Bootstrap and font assets. Monthly charts reflow to horizontal bars on narrow or
enlarged layouts and for ranges longer than 12 month buckets. No dependency,
remote chart service, JSON record payload, or client analytics library is added.

Each of the eight charts has a programmatic name, scope, visible values, short
section summary, and a native keyboard-operable View data disclosure containing
the equivalent HTML table. The six requested sections always remain on the page,
including truthful restricted/unavailable states. JavaScript only restores filter
focus to the short completion/error notice. Tables and filter submission work
without it. CSS responds directly to existing contrast, text-size and motion
preferences; charts have no animations.

Successful empty queries display zero and “No matching recorded activity.” Missing
dates are explicitly marked “No dated data” for those records. Permission denial
displays “Not permitted,” disabled/missing sources “Unavailable,” and other database
errors “Could not load.” Errors never become zero and SQL/error details are not
rendered. Model names, personal records, attachments, emails, incomes, medical
text, application IDs and scores do not enter the dashboard projection. Recorded
classification names are escaped by Django; chart dimensions are generated numbers.

## Removed dashboard presentation; preserved functionality

Removed the Membership reviews/Photo Verification, Content Management,
Eligibility and assistance/Eligibility states, Member records, Community
announcements/events, Assistance programs, Accounts and roles, Membership
configuration, and Account activity shortcut cards and their button lists.
Also removed the dashboard's account-access/public-website/community-services
side column and onsite-registration header action so the page is an overview.

All existing sidebar groups, navigation behavior, native Admin destinations,
module routes, forms, actions, records, and underlying read/export audits remain.
No new drill-down link was added with misleading date semantics; the scoped data
tables are the dashboard's analytical detail view.
