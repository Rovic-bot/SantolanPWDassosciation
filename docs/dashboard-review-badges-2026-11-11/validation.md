# Hosted dashboard and review badges — November 11, 2026

The owner requested repairing the deployed age chart, removing the entire “More metrics & reporting details” section, and adding membership/program application counts to the navigation and individual cards.

The age query previously used MySQL-only `TIMESTAMPDIFF(YEAR, ...)`, which fails on the hosted PostgreSQL database. It now calculates completed birthdays with portable Django date extraction and conditional expressions. Ten-year bands, local-day boundaries, archived-member exclusion and invalid-date handling remain intact. February 29 birthdays advance on March 1 in non-leap years, matching the earlier calculation. Only aggregate counts leave the database.

The additional-metrics disclosure and all its contents are removed. Primary metrics, charts, filters and accessible chart data remain available.

## Badge definitions

- Association: online registrations without an Approved or Rejected membership decision, matching the outstanding-review inbox. Onsite intake is excluded.
- PDAO: online registrations in Received, including older online records without an intake-channel key. Needs information, Ready and Forwarded records and onsite intake are excluded. PDAO creates no Association membership.
- Membership reviews: the sum of Association and PDAO queues the signed-in staff member can view. Separate counts appear on both review cards.
- Programs: applications in Pending Photo Verification, Photo Verified or Eligibility Review, including the existing no-photo submission route. Each portfolio card shows its own count; navigation shows the total across programs. Later eligibility/selection outcomes and requests awaiting applicant information are excluded.

Counts are outstanding-review indicators, not per-user unread tracking. Opening a page does not clear them or change a decision. The existing review transitions determine when counts decrease. Zero badges are hidden. Counts render on the server and refresh every 15 seconds while the page is visible, including after workspace navigation and program-card replacement. Transient errors retain the last count; lost authorization clears the badges and stops polling.

The endpoint is authenticated, staff-only, permission-scoped, GET/HEAD-only and non-cacheable. It returns only totals and requested program IDs, with a maximum of 20 card IDs. Association policy availability is respected. No migration, new approval rule, business-record mutation, email or public disclosure is introduced.

## Verification

- 37 focused tests passed on disposable native MySQL; the same 37 passed on a separate disposable PostgreSQL cluster with external sockets blocked. Both runners verified database identity and used synthetic data.
- Coverage includes birthday/leap-day/century/local-time boundaries, empty and invalid dates, dashboard aggregate/privacy/rendering checks, queue states and channels, permissions and revocation, read-only requests, invalid/bounded program IDs, counts after decisions, navigation and filtered/paginated program cards.
- An additional PostgreSQL rendering check passed after placing the program badge alongside the program title.
- Offline Chrome checks passed for real rendered templates and assets: age SVG, removed disclosure, dark/light themes at 1440 and 390 pixels, zero/new counts, temporary errors, revoked access, workspace page replacement and replaced program cards. No page JavaScript errors or horizontal overflow were found. The response fixtures are synthetic; these are not screenshots of private production records.
- Django database/configuration checks, migration-drift check, JavaScript syntax and `git diff --check` passed.

The broader first run also included three pre-existing portfolio-capacity expectations that fail against the unchanged deployed implementation: unlimited capacity text, non-EWAF demand and portfolio capacity totals. A separate isolated baseline run loaded the original `HEAD:programs/portfolio.py` and reproduced all three failures. Those business rules were not changed to satisfy stale tests. The full historical suite was not a release gate.

Live browser automation was stopped because its URL safety check could not reliably identify the current browser URL. Hosted verification uses Render status/logs and authenticated HTTP requests instead.

## Synthetic screenshots

- [Age chart](age-chart.png)
- [Membership cards on mobile](membership-dark-390.png)
- [Program card and navigation](programs-dark-1440.png)

## Release boundary

Only this task's source, tests and documentation are copied to the existing isolated deployment checkout, on `deployment/free-render-supabase` in `Rovic-bot/SantolanPWDassosciation`. The original local branch/index and unrelated unfinished changes remain intact. The original deployment's database, storage and configuration are retained.

## Hosted verification

Render deployment `dep-dbq76f0ae00c73fq6ie0` reached **live** at **2026-11-11 13:54:26 UTC**, running commit `d52bdff46648e575e8a3d7f1459a084f4cf6ab09`, at <https://santolan-pwd-system.onrender.com/>.

Authenticated hosted HTTP checks passed for the dashboard, membership review cards, program portfolio and count endpoint. The age chart's labels and values exactly matched a fresh aggregate query against hosted PostgreSQL. The removed disclosure was absent; navigation/card badge markup was present; returned totals and per-program counts matched the permission-scoped review queues. The new JavaScript and stylesheet contents matched the release files. The health endpoint returned success, and anonymous requests to the dashboard and counters redirected to sign-in.

Verification created one short-lived Django staff session and removed it in a `finally` block, confirming deletion. No real application was submitted or reviewed, no business record was changed and no email was sent. The follow-up documentation commit records this evidence without replacing the live functional commit.
