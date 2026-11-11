# Authentication, RBAC, and public portal validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


## Original Milestone Evidence

Date: 2026-09-19 (Asia/Manila). Milestone: 10% → 20%.

## Scope and implementation

The user requested continued development after the completed foundation. The next ten-percent milestone covers administrator authentication, configurable roles/permissions, and public pages. Applicable development guide sections: 13–14, 50–53, 61–66. No member accounts, membership processing, publication workflow, or EWAF behavior was added.

- Dedicated `/accounts/login/`, POST-only logout, password-change screens, and permission-protected `/dashboard/`.
- Retained Django's existing `auth.User`; `accounts.Administrator` is a proxy that defines `accounts.access_dashboard` without replacing user records. Django Groups represent configurable roles, Permissions represent capabilities, and existing many-to-many tables represent UserRole/RolePermission relationships. No business role names or policies are seeded.
- Active staff status and `accounts.access_dashboard` are both required for the dashboard; superusers receive Django's standard permission bypass. Missing permission returns an actionable 403 rather than a redirect loop. Removing staff/active status revokes existing authenticated access on the next request.
- Only active superusers can manage users, passwords of other users, and groups, even if a staff account is accidentally granted all model permissions. This is a technical security boundary, not a finalized business permission matrix.
- Both login routes use the same authentication backend and database counters. Defaults: 10 attempts per normalized username and 50 per network address within a 900-second fixed window. All credential attempts, including successful ones, count. Counters expire automatically for access decisions; blocked attempts do not extend the window. Limits are environment-configurable positive integers.
- Counters use HMAC keys and atomic reservations in MySQL, so multiple workers share the limit. Stable lock order, committed row creation, and bounded retries handle contention; persistent contention denies authentication. Forwarded-IP headers are ignored pending an explicit production proxy configuration.
- Authentication events record action, actor when authenticated, timestamp, and network address. Failed login records omit attempted usernames and credentials. Existing Django admin LogEntry records user/role edits; both audit screens are read-only, including for superusers. Audit immutability against database administrators is not claimed.
- Public Home, About, Announcements, Events, Programs, Membership Registration information, and Contact routes have working navigation and appropriate active-page indicators. Unimplemented services show honest empty states. Contact information remains unconfirmed; there is no submission form or invented address/telephone number.

The implementation follows Django's documented [group permissions](https://docs.djangoproject.com/en/5.2/topics/auth/default/#permissions-and-authorization) and [authentication backends and proxy models](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/).

## Database changes

Applied `accounts.0001_initial`, `audit.0001_initial`, and `audit.0002_alter_securityevent_action` to native MySQL 8.4.11 on `127.0.0.1:3307`.

- `accounts_loginwindow`: `key` (64-character primary key), indexed `started_at`, unsigned `attempts`.
- `audit_securityevent`: primary key, nullable user foreign key with SET_NULL deletion behavior, action, indexed creation timestamp, nullable IP address.
- Proxy content type/permission for dashboard access; no replacement user table or data reset.

The local `.env` initially pointed at MariaDB 13.0.2 on port 3306, contrary to the foundation documentation. The native MySQL app password was synchronized with the private environment, and `.env` was restored to port 3307 after a byte-verified backup under ignored `.local/`. The native database's one existing administrator was preserved. The other database service was not reconfigured; the initial test run created and destroyed only its disposable test database. Final validation used native MySQL.

## Verification results — passed

- `manage.py test --verbosity 1 --noinput`: **42 tests passed** against a disposable native MySQL database. Includes foundation regression checks, public routes, permission grant/revocation, superuser-only account/role administration, CSRF, session rotation, external redirect rejection, password validation/change, old-session invalidation, audit access, username/address throttling, expiry, cleanup, and six simultaneous login attempts competing for a limit of three.
- `manage.py test scripts.browser_qa --verbosity 1 --noinput`: **1 browser integration test passed**. Chrome checked all seven public pages and the login screen at 320, 390, 768, 1024, and 1440 pixels; no horizontal overflow, page errors, or failed resources. Tested keyboard skip navigation, mobile menu navigation, current-page links, sign-in, role creation with dashboard permission, audit list, password change, logout, and post-logout protection.
- Inspected login desktop, dashboard mobile, events mobile, and password-change mobile screenshots. All screenshots are local QA artifacts in ignored `.local/qa-milestone20/`.
- Configuration/database checks, migration application, pending-migration checks, model/migration consistency, static collection, and dependency checks passed.
- Browser accounts, roles, and authentication events existed only in the disposable test database. No test accounts or default passwords were added to the application database.

## Issues resolved during verification

- Concurrent first-use counters could deadlock when duplicate inserts retained shared locks before a write-lock upgrade. Counter creation now commits before sorted row locks; the concurrency regression passes on native MySQL.
- Audit date hierarchy required MySQL timezone definition tables that are not installed locally. Removed the optional hierarchy; normal timestamps and date filters remain available. Future SQL timezone aggregation must address database timezone-table installation explicitly.
- Browser harness initially used an ambiguous link selector that matched both the success message and result row. Scoped the assertion to the results list; the complete workflow passes.
- Windows sandbox prevented Chrome process launch; the successful browser run used approved execution outside that sandbox.

## Running the optional browser check

The standard test suite has no browser dependency. For the optional check, install/provide Playwright for Node and Chrome/Chromium, then set `PLAYWRIGHT_MODULE` to the installed module location if it is not available through Node's normal resolution. Set `CHROME_EXECUTABLE` to a browser executable if not using Playwright's managed browser.

```powershell
.venv\Scripts\python.exe manage.py test scripts.browser_qa --verbosity 1 --noinput
```

The harness launches Django's test server, uses its disposable test database and a randomly generated test password, captures screenshots, closes Chrome, and destroys the test database.

## Remaining scope

Business role names/assignments, official contact information, announcement publishing, membership applications, document uploads, events/program workflows, and other later modules remain pending. The guide/roadmap announcement-versus-membership sequencing question must be resolved before the next affected module.

This is local development. Production HTTPS/proxy configuration, rate-limit tuning for shared networks, audit retention, backups, hosting, broader accessibility evaluation, and UAT remain later work. Session cookies expire when the browser closes and have a default one-hour server lifetime; browser session-restore behavior can preserve cookies, so the server lifetime remains necessary. Existing sessions using the former authentication backend require a fresh login.
