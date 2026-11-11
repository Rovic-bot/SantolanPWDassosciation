# Santolan PWD System

Django + native MySQL application for the Barangay Santolan PWD Association. Public pages use server-rendered templates/Bootstrap. The current **target documentation** is [CURRENT_SYSTEM_SPECIFICATION](../CURRENT_SYSTEM_SPECIFICATION.md), updated 2026-10-10; earlier milestone results and the operator instructions below are historical evidence, not acceptance of the revised system.

## Current development — November 11, 2026

The online deployment branch is `deployment/free-render-supabase`. See [current Render + Supabase instructions](docs/render-supabase-2026-11-11.md) for PostgreSQL, private uploads, Gmail relay, Docker/LibreOffice, configuration and backup boundaries. Older deployment notes below describe earlier environments.

The complete application snapshot is on the [`development` branch of SantolanPWDassosciation](https://github.com/Rovic-bot/SantolanPWDassosciation/tree/development). **Start with [Fresh Checkout Setup](docs/FRESH_CHECKOUT.md).** It covers the database, migrations, current feature settings, registration policy, Gmail, certificate PDF conversion, annual observances, and startup on another computer. The [publication validation](docs/github-development-2026-11-11-validation.md) records the actual checks and publication scope.

This branch includes all application source, migrations, templates, JavaScript/CSS, required images and downloadable forms, certificate templates, dependency manifests, tests, and developer tools. The latest work includes annual-observance creation/editing, email and receipt workflows, household scoring, Admin animations and popups, public result dragging, and immediate processing feedback. Credentials, live database records, private uploads, generated screenshots, and the old private Git history are not part of this public source snapshot.

An installation starts with its own database and administrator account. Gmail must be connected locally and LibreOffice installed for PDF certificates. Existing programs, CMS edits, members, uploaded photos, and saved annual-observance cards are database/storage content; Git does not transfer them. The annual-observance editor and the optional reference-calendar installation command are included. Use a separately authorized private backup/restore process when moving existing records.

## Previous development snapshot — November 9, 2026

The complete current application source running at `http://127.0.0.1:8013/` is published on [`dev-local-8013-2026-11-06`](https://github.com/Rovic-bot/capstone/tree/dev-local-8013-2026-11-06). This includes the frontend, backend, deployable assets, migrations, tests and launchers. The [November 9 publication record](docs/github-development-2026-11-09-validation.md) documents the current feature settings, source verification and test results; the dated snapshots below remain historical.

Recent work includes Association office-invitation and approval emails, PDAO application/review/claim workflows, document preview popups, membership and program reviews, program scheduling and publication, assistance receipts and certificates, EWAF selection updates, and the current public and Admin interfaces. Domain validation notes describe the exact scope. GitHub stores the source; database records, CMS content, private uploads, saved email credentials and machine-specific runtime files stay on the local computer. A separate installation must configure those services and the documented feature settings.

## Earlier development snapshot — October 28, 2026

The current port-8013 source is published on [`deploy/main-development-2026-10-28`](https://github.com/Rovic-bot/capstone/tree/deploy/main-development-2026-10-28). See the [publication validation](docs/github-main-development-2026-10-28-validation.txt) and [local Render compatibility checks](docs/render-compatibility-2026-10-28-validation.md). This is a source snapshot; hosted deployment and full-system acceptance remain pending.

The latest authorized results workflow displays full names in permission-checked Admin views and publishes masked applicant/selection records independently of review readiness. It does not change application decisions, rankings or assistance receipts. The [October 28 results validation](docs/admin-recorded-results-2026-10-28-validation.txt) supersedes earlier result-screen instructions below. Production feature flags must match the actual port-8013 configuration documented in the compatibility note; older `.env` instructions do not establish what is enabled there.

## Historical development branch — October 25, 2026

The publication target is a new [`development` branch in Rovic-bot/capstone](https://github.com/Rovic-bot/capstone/tree/development); `main` remains unchanged. This source snapshot includes the existing application work and the owner's latest membership changes:

- Public online registration shows the applicant's reference number and instructions to visit the barangay for information verification.
- Admin enters that reference, corrects the prefilled fields, and approves or declines. Approval requires Admin to enter the assigned Association member number and creates the member; declining creates no member. There is no separate processing-review or required-reason step on this screen.
- Membership printing follows the supplied `Santolan_PWD_Membership_Form.docx`; the blank Association and PDAO PDF downloads are included.

See the [registration decision validation](docs/simple-registration-2026-10-25/validation.md), [confirmation validation](docs/registration-confirmation-2026-10-25/validation.md), [print validation](docs/membership-print-template-2026-10-25/validation.md), and [publication scope](docs/github-main-development-2026-10-25.md). The latest membership regression run passed **138 focused tests**; this is not a full-system or production acceptance claim. Dated notes below preserve earlier workflows and validation results.

Credentials, databases, member uploads and the machine-specific `.local` runtime are intentionally private. On the owner's configured computer, `Start System.cmd` and `Restart System.cmd` use that retained runtime. A fresh checkout needs its own Python environment and MySQL configuration using the setup instructions below; those two shortcuts do not provision the private runtime. Back up an existing database and review pending migrations before applying them. Keep `DB_TEST_NAME` separate from application data.

## October 10 target and current implementation

Read [source register](../00%20-%20Project%20Overview/Workflow%20References/2026-10-10/Workflow%20Source%20Register.md) and [implementation impact](../05%20-%20Development/October%2010%20Implementation%20Impact.md). Target public navigation: Home, About, Announcements, Events, Programs, Results, Membership. Target Admin groups: Dashboard; Members; Programs & Events; Applications & Verification; EWAF & Selection; Announcements & CMS; Reports & Exports; Administration.

Program applications use secure membership verification, required evidence and a calendar photo or approved accessible alternative only when required by approved policy; submission/reference, Admin review, eligibility, applicable calculation/ranking, human selection, Results publication and actual delivery are distinct. Optional event RSVP needs approval; Gemini is PROPOSED. Workbook directions/evidence/thresholds and future random references remain Open Decisions. No public tracker or member accounts.

The owner-defined 70% milestone remains preserved. Subsequent scoped implementation has validated seven public sections, dedicated authorized Results, application receipt guidance, eight permission-aware Admin groups, confirmed Association/PDAO membership guidance and the Admin UI cleanup. See [Phase 1](docs/phase1-public-results-validation-2026-10-10.md), [Phase 2](docs/phase2-admin-navigation-validation-2026-10-10.md), [membership validation](docs/confirmed-membership-validation-2026-10-10.md) and [UI cleanup](docs/admin-ui-cleanup-validation-2026-10-10.md). Controlled EWAF, conditional evidence and OQ-27 evidence-handling enforcement remain separate unfinished work. Historical statements below describe their original milestones.

## GitHub and Render preparation

The opt-in deployment configuration uses `DJANGO_SETTINGS_MODULE=config.settings_production`; local settings and MySQL development commands remain unchanged. Read [the deployment handoff](docs/render-deployment-preparation.md) before configuring any service. It requires explicit secrets/hosts, verified MySQL TLS and approved private persistent storage. No database, paid service or live deployment is provisioned by these files. Only synthetic data may be used for the first deployment validation. Vault specifications live outside this repository and are not included in the GitHub publication.

## Earlier approved workflow — historical target and current baseline behavior

The October 6 wording below preserves the earlier target underlying current implemented behavior. Conflicting new TARGET requirements are replaced by the October 10 master above; it does not authorize renewed implementation or rollback.

- Membership is strictly IN PERSON at the Barangay Santolan PWD Association Help Desk, entered/verified internally by authorized Admin. Public guidance displays approved changing requirements/steps/contact information. No member account, public registration or government API.
- Public Information Portal supports browsing and member-only login-free program/event applications: minimal internal membership match → requirements/verified-data reuse → proof and current calendar photo → valid submission/unique reference → manual Admin Photo Verification → final eligibility → applicable locked/versioned EWAF → generated ranking → authorized selection/final processing within slots → masked Program Announcement.
- The canonical reference format, branched application lifecycle and separate Photo Verification statuses are defined in the primary specification. Confirmation asks applicants to keep the reference, monitor Announcements and contact the Help Desk. No member inbox, required status/QR page or SMS/email service.
- EWAF has approved configurable criteria/source/scoring/weights. Lock before active evaluation; legitimate new versions automatically recalculate the whole affected eligible pool and retain old runs. Audit source corrections and dependent recalculation. No universal income/matrix default, medical/disability score, manual score/rank change or automatic beneficiary approval.
- Admin manages required modules, approved changing public content and authorized masked final results, with protected audits/references/history. Application deadline closure does not automatically publish applicants/results. Privacy, RBAC, secure evidence and accessible operation are core.

Use [Business Rules](../01%20-%20Requirements/Business%20Rules.md), [Database Plan](../03%20-%20Database/Database%20Plan.md), [Open Decisions](../00%20-%20Project%20Overview/Open%20Decisions.md), [EWAF Specification](../04%20-%20EWAF/EWAF%20Specification.md), [current tracker](../05%20-%20Development/Feature%20Implementation%20Tracker.md) and [acceptance plan](../06%20-%20Testing/Workflow%20Acceptance%20Tests.md). The owner subsequently authorized stages 1–7 implementation. The revised **70% local milestone** is validated in [revised70-validation.md](docs/revised70-validation.md); A later authorized extension completes masked non-EWAF program-result publication and unified Members/sidebar navigation: [validation](docs/announcements-members-validation.md). EWAF computation and its dependent publication, analytics/exports and production/UAT acceptance remain incomplete.

## Run on this computer

The main local development system now uses the retained 12-member EWAF database
and its existing private files. The normal start, restart, stop and administrator
launchers all use that same verified database. Earlier development databases are
preserved separately.

Use the single **Members** sidebar entry for **Member records**, **Onsite registration** and **Membership reviews**. The sidebar remembers its own scroll position across custom/native Admin pages and mobile reopening.

For final results, use **Announcements → Prepare program results** (also linked from Program review), select a program, give a reason, prepare and review the masked draft, then explicitly authorize publication. All application reviews/decisions must be final and current. Old results become private during revision; stale sources are withheld until reviewed/re-published. Full references/names/scores stay private. Existing general news controls remain. Run `scripts.announcements_members_browser_qa` for this acceptance workflow; `scripts.revised70_browser_qa` covers the previous complete application flow.

Current operations: authorize real photo instructions/selection method before publishing a program; link organizational events to their Program Application. Use Photo Verification Queue and Help Desk corrections before eligibility. New references use the canonical format; old references remain searchable. CMS is under Content Management. Legacy EWAF mutations and automatic deadline publication are disabled; do not run old browser harnesses as current acceptance. Use `scripts.revised70_browser_qa` for the revised browser scenario.


1. Double-click **Start System.cmd** in this folder. The server runs in the background.
2. Open **http://127.0.0.1:8013/** for the public community homepage.
3. Open **http://127.0.0.1:8013/accounts/login/** for the administrator login and dashboard. Account/role configuration is available through **http://127.0.0.1:8013/admin/** for superusers.

The launcher starts the retained MySQL instance on `127.0.0.1:3309` and Django on `127.0.0.1:8013`, using `config.current_development_settings`. It verifies the database identity and never recreates the dataset, loads `.env`, migrates another database or falls back to a different connection. XAMPP and Docker are not needed.

Use the existing administrator credentials saved locally in `.local/ewaf-twelve-demo/LOGIN.txt`. To create another administrator in this development database, double-click **Create Admin.cmd** and enter the requested credentials. Password input is hidden. Once signed in, visit **http://127.0.0.1:8013/dashboard/**.

Double-click **Stop System.cmd** to stop the website and its database while retaining all records and uploads. From PowerShell:

```powershell
.venv\Scripts\python.exe -B scripts\current_development.py stop
```

Alternatively, run the website from PowerShell in this folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run.ps1
```

To restart after code changes, run `scripts/restart-current-development.ps1`.
For a configuration check, run `.venv\Scripts\python.exe -B scripts\current_development.py check`.
The previous development launcher remains available as `scripts/run-previous-development.ps1`;
it is not used by Start System.

## Technical setup and Admin access — retained nonconflicting guidance

These commands describe the existing local installation, not actions executed during documentation alignment. Inspect current source/settings before a future implementation/installation task. Permission groups are authorized Admin capabilities, not new association roles.

## Configure administrator access

Sign in with your existing superuser, or create one using **Create Admin.cmd**. There is no default password. Existing accounts are preserved; sessions from the foundation's previous authentication backend require a fresh login.

1. From the dashboard, choose **Manage roles (groups)**. Create a group with a role name selected by your association.
2. Assign **Accounts | administrator | Can access administration dashboard**. Add audit viewing permissions only when needed: **Audit | security event | Can view security event** and **Administration | log entry | Can view log entry**.
3. Choose **Manage accounts**. Add a user with a strong password, then edit the account to enable **Active** and **Staff status** and assign the appropriate **Roles (groups)**. Leave **Superuser status** off for ordinary administrators.
4. Have the administrator sign in at `/accounts/login/`. Active staff without dashboard permission receive an access-denied page with a sign-out option. Changes to roles/permissions take effect on the next request.

Only superusers can create/edit/delete users and groups or change another user's password, even when a staff account has model permissions for those actions. Administrators can change their own password through the dashboard; other sessions become invalid afterward. Deactivate accounts rather than deleting them when preserving their audit identity is important.

Both `/accounts/login/` and `/admin/login/` share these environment settings:

- `LOGIN_USERNAME_LIMIT=10`: attempts per normalized username.
- `LOGIN_ADDRESS_LIMIT=50`: attempts per network address.
- `LOGIN_WINDOW_SECONDS=900`: fixed window duration; blocked attempts do not extend it.
- `SESSION_COOKIE_AGE=3600`: default server session lifetime; browser-close expiry is also enabled.

All credential attempts count, including successful attempts. Wait for the window to expire if a limit is reached. Login errors deliberately do not reveal account existence or lockout status. Forwarded headers are not trusted. Production proxy/shared-network settings require validation before deployment.

Expired counters can be removed with `.venv\Scripts\python.exe manage.py purge_login_windows`; this does not delete audit events or clear active limits. No automatic retention schedule is installed.

## Setup on a new Windows computer

Install Python and Git. In the source folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
```

Put the generated value in `SECRET_KEY` inside `.env`; generate another random value for `DB_PASSWORD`. Do not commit `.env`. Set `DB_NAME=santolan_pwd`, `DB_TEST_NAME=test_santolan_pwd`, and `DB_USER=santolan_app` for the project-local setup.

Download [MySQL Community Server 8.4.11 for Windows](https://cdn.mysql.com/Downloads/MySQL-8.4/mysql-8.4.11-winx64.zip) to `.local/downloads/mysql.zip`, creating the directories first. The setup helper verifies the published checksum and ZIP integrity before extraction:

```powershell
.venv\Scripts\python.exe scripts\local_mysql.py init
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py test
```

`init` refuses to overwrite existing database data or administrator credentials. It creates a loopback-only native MySQL process, a generated root password in ignored `.local/mysql-admin.json`, a dedicated application account, and grants limited to the application and test database names. The normal app never uses root. The initializer temporarily holds bootstrap SQL in `.local` and removes it after successful setup. If setup fails, inspect `.local/mysql-error.log` and `mysql-initialize.log`; preserve data and resolve the failure before retrying.

The initializer updates `.env` to port 3307. Subsequent runs use `start`, not `init`. Keep `.local` private: it contains real database files and local credentials, is ignored by Git, and must not be served as website content.

For an existing compatible native MySQL installation, configure its database/account in `.env` and use `manage.py runserver` directly; the bundled launcher is specifically for the project-local instance. Django migrations define the schema. Never point `DB_TEST_NAME` at important data: Django creates and drops that test database.

## Verification commands

```powershell
.venv\Scripts\python.exe manage.py check --database default
.venv\Scripts\python.exe manage.py migrate --check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py test --verbosity 2
.venv\Scripts\python.exe manage.py collectstatic --noinput
```

See [70% milestone validation](docs/assistance-validation.md) for historical checks and assistance migrations; current workflow acceptance is in [Workflow Acceptance Tests](../06%20-%20Testing/Workflow%20Acceptance%20Tests.md). [60% validation](docs/programs-validation.md) preserves Programs evidence. [50% validation](docs/events-validation.md) preserves Events evidence. [40% validation](docs/members-announcements-validation.md) retains the earlier member/announcement evidence. [Membership validation](docs/membership-validation.md) preserves the earlier milestone evidence. [Authentication/portal validation](docs/authentication-validation.md) and [foundation validation](docs/foundation-validation.md) preserve earlier milestone evidence.

## Troubleshooting

- **Port 8000 already in use:** an existing website may still be running. Open its URL first; do not terminate an unrelated process. For another port, use `manage.py runserver 127.0.0.1:8001`.
- **Database connection refused:** run `scripts/local_mysql.py start` with the virtual-environment Python. Check `.local/mysql-error.log` if startup fails.
- **Port 3307 occupied:** the helper refuses to manage another database. Resolve the conflict before starting this instance.
- **Missing MySQL DLL/runtime:** install Microsoft's supported Visual C++ Redistributable for x64, then retry. Do not download individual DLLs from third-party sites.
- **Forgot admin password:** run `.venv\Scripts\python.exe manage.py changepassword YOUR_USERNAME`.

## Development and publication boundary

This is local development, bound to loopback. Before production: use a production WSGI/ASGI server, `DEBUG=False`, explicit hosts, HTTPS and secure cookies, a production database/storage/backup plan, validated login/proxy settings, and the remaining domain authorization/audit requirements. Run `manage.py check --deploy` with the actual production environment. This milestone is not a public deployment approval.

The `feature/events` branch continues the existing membership and frontend work. No remote publication is performed by the startup scripts. Vault planning notes live outside this application repository and need their own backup.

References: [Django database requirements](https://docs.djangoproject.com/en/5.2/ref/databases/#mysql-notes), [Bootstrap downloads](https://getbootstrap.com/docs/5.3/getting-started/download/). Bootstrap's MIT license is included in `static/vendor/bootstrap/LICENSE`.

## Legacy domain operator instructions — OUTDATED / HISTORICAL

> [!warning] OUTDATED / HISTORICAL — earlier scope and evidence only
> Everything below retains the original dated text, checkbox states, source paths and test results. Former "current", "next", "complete" and "approved" labels refer to that revision only. They do not establish the 2026-10-06 workflow or authorize application/source/database actions now. [[CURRENT_SYSTEM_SPECIFICATION]] supersedes contradictory rules.

## Historical implemented baseline — prior to the approved workflow revision

- A responsive community homepage plus About, Announcements, Events, Programs, Membership Registration, and Contact pages with working navigation and honest empty states.
- Public and administrator layouts, dedicated sign-in, POST-only sign-out, password change, and a permission-protected dashboard.
- Configurable roles using Django groups/permissions; only superusers manage accounts and role assignments. Business role names are not preconfigured.
- Shared database-backed login attempt limits, password hashing, CSRF, secure session handling, and read-only authentication/administration audit views.
- Public membership applications with configurable document requirements, private uploads, manual PRPWD verification, audited approval/rejection, and atomic creation of an official Member after approval.
- Private member search, editing, status management, original documents, and retained change history.
- Announcement drafting, publishing, withdrawal, archiving, deletion with retained audit history, and validated images; published news appears on the homepage and announcement pages.
- Event drafts/publication/cancellation/archive, capacity-limited member registration, attendance corrections, and retained participation history.
- Assistance program publication, per-program uploads/questions, verified-member applications, review/cancellation, and member application history.
- Modular app shells for future milestones; configuration via `.env`.
- MySQL built-in migrations and a separate disposable test database.
- Local static assets; media storage is configured but deliberately has no unrestricted public file route.

Member management, announcements, events, and program application workflows are implemented. Eligibility, assistance release/history, EWAF, and reports remain later milestones. Public pages do not expose member records. Official contact details are awaiting confirmation.

## Use onsite membership registration

Public `/membership/register/` displays the current Membership Guidelines and active requirements. It accepts no online submission, regardless of the retained legacy registration-open flag.

1. An authorized administrator configures the association-approved document types/active requirements, disability classifications and official HTTPS PRPWD URL. Do not invent official values. Existing role assignments are preserved.
2. An active staff officer signs in and opens **Dashboard → Onsite member registration**, or `/membership/applications/new/`. Encode the applicant's onsite information and upload supplied documents for private review, then **Save onsite registration for review**. This creates Pending intake only.
3. Review the original documents, open the configured PRPWD website link and manually record the result and verification notes. The system performs no PRPWD API lookup.
4. Record the explicit approval/rejection and decision notes. Approval requires successful manual verification and original required files, then creates the Official Member. Rejection creates no Member. History and original evidence remain retained; applicants receive no user accounts.

In addition to active staff status, the workflow requires `accounts.access_dashboard` and `membership.view_membershipapplication`. Assign the separate capabilities deliberately: `membership.encode_membershipapplication`, `membership.verify_membershipapplication`, `membership.decide_membershipapplication`, and `documents.view_membershipapplicationdocument` for private downloads. `membership.view_membershipevent` allows activity viewing; `members.view_member` allows the resulting member-record link. Configuration administration has its own model permissions. No existing staff account receives these capabilities automatically.

Local acceptance: 55 focused automated cases plus one Chrome workflow, 35 responsive/seven enlarged-text checks, and unchanged normal application data across 43 tables. See [onsite membership validation](docs/onsite-membership-validation.md) for commands and limits. Official configuration, UAT and production readiness remain separate tasks.

## Open and use membership registration

> **SUPERSEDED — 2026-09-28: historical public-intake instructions.** Current membership is onsite/admin-side with public guidelines only. The original steps below document the prior implementation and must not be used as the current registration specification.

Registration starts **closed**. No document names, real applicants, test accounts, or official PRPWD URL are seeded into the application database.

1. Sign in with your existing superuser at `/accounts/login/`.
2. From the dashboard, open **Document types** and add the association's approved document names. Open **Document requirements**, select each type, and set Active, Required, and any instructions. Deactivate obsolete requirements; submitted application snapshots remain unchanged. If the association deliberately requires no documents, leave the list empty.
3. Open **Registration settings**, select **Membership registration settings**, enter the current official HTTPS PRPWD verification link, check **Registration open**, and save. Confirm the link with the association before opening registration.
4. Applicants can now submit at **http://127.0.0.1:8000/membership/register/** without accounts. The receipt confirms submission only and exposes no personal data or public application lookup.
5. From the dashboard, choose **Review applications**. Open an application, download its documents if authorized, use **Open PRPWD website**, and manually record Yes/No with verification notes. The system never calls a registry API or transmits applicant fields to that link.
6. Record an approval or rejection with decision notes. Approval requires successful verification and the originally required uploads, and creates one official member. Rejection creates no member. Membership application decisions are locked; reopening remains future work. Approved member profiles can be corrected through the member directory.

All reviewers need Active, Staff status, `accounts.access_dashboard`, and `membership.view_membershipapplication`. Grant additional capabilities individually or through groups:

- `membership.verify_membershipapplication`: record manual PRPWD results.
- `membership.decide_membershipapplication`: approve or reject.
- `documents.view_membershipapplicationdocument`: download private documents.
- `membership.view_membershipevent`: see application activity (also requires application viewing).

Configuration uses the corresponding Membership settings, Document type, and Membership document requirement model permissions in Django admin. Superusers already have access. Role names remain the association's choice. Application/member records cannot be added or edited through a generic Django admin page to bypass review.

Technical defaults: PDF/JPG/JPEG/PNG only; extension, declared MIME, and signature checks; 5 MB per file, 20 MB aggregate, at most 20 uploaded files. Size limits are configurable in `.env`. Signature validation is not malware scanning. Private files are attachment downloads with authentication, permission checks, no-store headers, and audit records; never add a public `/media/` route.

Submission attempts use a separate shared counter with HMAC network-address keys. Defaults are 20 attempts per network per hour, adjustable with `MEMBERSHIP_SUBMISSION_LIMIT` and `MEMBERSHIP_SUBMISSION_WINDOW_SECONDS`. Invalid attempts count; retry after expiry when limited. Use `.venv\Scripts\python.exe manage.py purge_submission_windows` to remove expired counters without deleting applications. Login-counter cleanup is independent. Production needs validated proxy/network limits and request-size enforcement at the web server.

Employment and disability descriptions are collected as text, without invented categories or scores. Control numbers are trimmed and uppercased for storage and member uniqueness. Four-field event and program matching is implemented as described below. Duplicate control numbers may be submitted for private administrator review, but cannot produce duplicate official members. The same signed submission form can be retried for 24 hours without creating another application; changing configured requirements invalidates old forms.

## Manage official members

> **2026-09-28 alignment:** Official Member creation now requires reviewed onsite admin encoding and manual PRPWD approval. Existing directory controls below remain; creation exclusions and registration-linked histories describe the earlier baseline pending alignment.

Open **Dashboard → Open member directory**, or `/members/`. Members are created through approved membership applications. Search by name/control number and filter Active, Inactive, Archived, or all records. Open a member to edit their profile, change status with a reason, download original documents, and inspect changes. Archiving preserves records; selecting Active or Inactive restores an archived member. Restore before editing an archived profile.

All actions require an active staff account and `accounts.access_dashboard`. Assign these separately through groups or individual permissions:

- `members.view_member`: directory and member detail.
- `members.change_member`: profile corrections; original applications remain unchanged.
- `members.change_member_status`: activate, deactivate, archive, and restore.
- `members.view_memberevent`: detailed member-change history, together with member viewing.
- `documents.view_membershipapplicationdocument`: original document download, together with member viewing.

There is no member-create/delete screen and no member account. Event participation appears on member records with both event and event-registration viewing permissions. Program applications appear with both program and program-application viewing permissions. Assistance release history remains a later milestone. A stale edit is rejected; reload the record before retrying.

## Publish association announcements

> **2026-09-28 alignment:** General announcement controls below remain. Automatic registration-close program applicant publication and masked approved results are additional approved requirements, pending implementation.

Open **Dashboard → Manage announcements**, or `/announcements/manage/`.

1. Choose **Create announcement**, enter the title and plain-text content, optionally upload a PNG/JPEG and its image description, then **Save draft**.
2. Review the content. Under Publication controls, select **Publish on the public website**, confirm, and apply the change.
3. Published items appear at `/announcements/`; the three most recently published items also appear on the homepage.
4. Edit published content only when ready for the changes to appear immediately. Use **Withdraw to draft** to work privately. Archive removes an item from public view and allows later republication.
5. Delete removes an announcement from public view and the default management list. It remains in the **Deleted** filter with its audit history and cannot be edited or republished.

In addition to staff/dashboard access, assign `announcements.view_announcement` and the required capabilities: `add_announcement`, `change_announcement`, `publish_announcement`, `delete_announcement`, and `view_announcementevent` (all in the `announcements` app). Editing an already published announcement requires both change and publish permissions. Superusers already have access; existing ordinary roles are not automatically expanded.

Images default to 5 MB and 16 million input pixels, configured by `ANNOUNCEMENT_IMAGE_MAX_MB` and `ANNOUNCEMENT_IMAGE_MAX_PIXELS`. Pillow decodes/re-encodes still PNG/JPEG input, limits output dimensions to 1920 pixels, and strips source metadata. Invalid images are rejected. Raw `/media/` remains private; only the image of a currently published announcement is publicly served. Draft/archive/deleted images require authorized workspace access. New installation: install `requirements.txt` and run `manage.py migrate`.

Detailed scope, migrations, checks, and limitations: [40% milestone validation](docs/members-announcements-validation.md).

## Use open event attendance

Locally validated 2026-09-30 under DEC-022. Open **Dashboard → Manage events → Review an event → Open event attendance → Record attendee**.

1. Publish the event and wait until it starts. Record an attendee name, Attended/Absent status and attendance notes. Nonmembers can attend; no registration, control-number verification or active membership is required.
2. Optionally link an existing Member. Staff need Member viewing permission to select/change the link. Inactive and archived members are permitted; leaving it blank records a nonmember/unlinked attendee.
3. Open a record to correct name, optional link or status with a reason. History retains the actor, time and changes; stale forms must be reloaded. Linked records also appear in the member's Open event attendance history.
4. Search/filter the private roster. The Attended count covers this new roster only. Legacy registrations and their attendance/history remain separately available; no automatic conversion, merge or name deduplication occurs. Repeated submission of the same form is safe.

Active staff need `accounts.access_dashboard`, `events.view_event` and `events.view_eventattendance`. Assign `events.add_eventattendance` for intake, `events.change_eventattendance` for corrections and `events.view_eventattendancelog` for history. `members.view_member` permits optional linking/member-record access. Superusers have standard full access; existing ordinary roles were not expanded automatically. Publishing still requires its existing permission. No public attendee list or deletion control is provided.

`events.0004_open_event_attendance` adds two tables and preserves existing records; it was applied locally after a private backup. For another installation, back up its database before `manage.py migrate`. See [current attendance validation](docs/open-attendance-validation.md) for fields, tests, migration and remaining deployment/UAT scope.

## Publish events and record attendance

> **SUPERSEDED — 2026-09-28: historical registration/attendance instructions.** Events are now open to anyone without registration or identity verification. Preserve publication and history; design the transition of registration-linked administrative attendance. The original steps below document the prior implementation only.

Open **Dashboard → Manage events**, or `/events/manage/`.

1. Choose **Create event**. Enter the title, description, venue, start/end, and registration period in Philippine time. Registration must close no later than the event starts. Capacity is optional; blank means no limit. Add an optional PNG/JPEG with an image description, then **Save draft**.
2. Review the schedule and image. Under Publication controls choose **Published**, provide a reason, confirm, and apply. Public events appear at `/events/`; the homepage shows the next three public activities.
3. During the registration period, active members enter their PWD control number, full name, birthdate, and contact number. Names ignore case/repeated spaces; phone formatting and equivalent `+63`/`0` prefixes are normalized. Birthdate is exact. Accents, name order and missing digits are not guessed. No account or additional PRPWD check is required.
4. Successful registration provides a random reference and a receipt in the submitting browser session. The session retains only the most recent event receipt. Repeated submissions return the existing registration without using another slot. There is no public member directory or lookup by reference.
5. Open **Registrations and attendance**, search/filter participants, then open a registration to confirm, cancel, restore, or record attendance. Every change needs a reason. Attended/Absent are available after the event starts; cancellation frees a slot, and restoration rechecks capacity and active membership. Member records link to their event participation history.
6. **Cancelled** closes registration while retaining a public cancellation notice. **Draft** and **Archived** hide the event and its image. Existing registrations/history are retained; cancellation of the whole event does not rewrite individual attendance records. Use existing official communication channels to notify participants of changes; no automatic email/SMS is sent.

All administrators need active staff status, `accounts.access_dashboard`, and `events.view_event`. Assign additional capabilities as needed:

- `events.add_event`: create drafts.
- `events.change_event`: edit details. Editing published/cancelled public content also requires publishing permission.
- `events.publish_event`: publish, withdraw, cancel, and archive with confirmation.
- `events.view_eventregistration`: private participant roster and registration details, also required for member participation history.
- `events.change_eventregistration`: change registration/attendance status, together with roster viewing.
- `events.view_eventlog`: detailed event or registration history, together with access to that record.

Superusers already have these capabilities. Existing ordinary roles are unchanged; the association assigns permissions deliberately. There are no generic create/delete registration endpoints or physical event deletion controls. Event registrations never contribute to EWAF or previous-assistance counts.

Technical limits are configurable: `EVENT_IMAGE_MAX_MB=5`, `EVENT_IMAGE_MAX_PIXELS=16000000`, `EVENT_VERIFICATION_MEMBER_LIMIT=10`, `EVENT_VERIFICATION_ADDRESS_LIMIT=50`, and `EVENT_VERIFICATION_WINDOW_SECONDS=900`. Verification counters use HMAC keys and count all attempts across events. Only the actual network address is used; forwarded headers are ignored. Rate-limited requests return 429 with Retry-After. Clean expired counters using `manage.py purge_event_verification_windows`; this preserves active counters and event records. No scheduled cleanup is installed.

The existing image processor decodes/re-encodes event PNG/JPEG uploads and removes metadata. Public images follow current event publication status. Run `manage.py migrate` after updating an existing installation. Details: [Events plan](docs/events-plan.md) and [50% validation](docs/events-validation.md).

## Publish assistance programs and review applications

> **SUPERSEDED — 2026-09-28 (affected workflow portions):** These original implementation instructions lack the newly required disability gate, initial Under Review, QR/status page, EWAF ranking and masked program publications. The current approved sequence is above; unchanged configuration/security/history controls below remain.

Open **Dashboard ? Manage programs**, or `/programs/manage/`.

1. Choose **Create program**. Enter its name, description, association-defined assistance type, and application period in Philippine time. Program dates, beneficiary slots, internal budget, amount, benefit description, and public instructions are optional. Save a draft.
2. Choose **Add requirement** for each document upload, written question, or acknowledgement checkbox. Set its label, instructions, required/optional setting, active state, and display order. Deactivate obsolete items instead of deleting them. No institutional requirements or assistance categories are seeded.
3. Review and publish through **Publication controls**, providing a reason and confirmation. Public programs appear at `/programs/`. Budget remains private. Beneficiary slots are planning information: **applications may exceed the slot count** for later selection.
4. Members choose **Apply for this program** and verify their control number, full name, birthdate, and contact number against an active official membership. Matching follows the event normalization rules above. They then upload the configured documents, answer the questions, and submit. No member account or new PRPWD check is required.
5. Submission creates one application per member/program and a private browser-session receipt containing only a random reference and status. Repeated verified submissions return the existing application. Original program details, requirements, answers, and documents are retained when configuration changes later.
6. Open **Review program applications**, search/filter the private roster, then review an application and its documents. Authorized administrators change **Submitted**, **Under review**, or **Cancelled**, with a required reason. A cancelled application needs administrator restoration with active membership on a published program. Member profiles include program application history.
7. **Cancelled** closes applications and leaves a public notice. **Draft** and **Archived** hide the program. Existing applications/history remain. Changes to public details or requirements take effect immediately and invalidate unfinished forms; existing submissions keep their original snapshots. Use existing official channels to communicate changes.

In addition to active staff status and `accounts.access_dashboard`, assign `programs.view_program` plus the required capabilities:

- `programs.add_program`: create drafts.
- `programs.change_program`: edit details; public edits also need publication permission.
- `programs.publish_program`: publish, withdraw, cancel, and archive.
- `programs.configure_program`: add/edit/deactivate requirements and questions; changes to public programs also need publication permission.
- `programs.view_programapplication`: private roster, application detail, and member program history.
- `programs.change_programapplication`: reasoned status changes, together with application viewing.
- `programs.view_programdocument`: audited private attachment downloads, together with application viewing.
- `programs.view_programlog`: detailed history, together with viewing permission for the associated record.

Superusers already have access. Existing ordinary roles are unchanged. There is no generic Django admin mutation bypass or physical delete workflow. Submission and Under review **do not establish eligibility, approval, or receipt of assistance**. Use the separate assistance workflow below for eligibility, human decisions and release records; applications never contribute to previous-assistance counts. EWAF remains a later milestone.

Technical limits: a verification grant lasts 15 minutes and is scoped to this browser session and one program/member. A new verification replaces the previous grant; changed program configuration/member records or inactive membership require verification again. `PROGRAM_VERIFICATION_MEMBER_LIMIT=10`, `PROGRAM_VERIFICATION_ADDRESS_LIMIT=50`, `PROGRAM_VERIFICATION_WINDOW_SECONDS=900`, and `PROGRAM_VERIFICATION_GRANT_SECONDS=900` are configurable. HMAC counters count attempts across programs without storing raw verification data; forwarded headers are ignored. Rate-limited responses return 429 and Retry-After. Run `manage.py purge_program_verification_windows` to remove expired counters; no schedule is installed.

Program documents reuse membership upload limits: PDF/JPG/JPEG/PNG, matching extension/MIME/signature, 5 MB per file, 20 MB aggregate, up to 20 files. A program supports at most 50 active uploads/questions in total. Downloads require explicit authorization and use no-store, attachment, sandbox, and nosniff headers. Signature checks are not malware scanning. No public `/media/` route is added.

Run `manage.py migrate` after updating an installation. Scope and verification: [Programs plan](docs/programs-plan.md) and [60% validation](docs/programs-validation.md).

## Assess eligibility and record assistance

> **SUPERSEDED — 2026-09-28 (interim approval path only):** The prior procedure below permits review/approval without EWAF. The current specification additionally requires mandatory disability eligibility and EWAF/ranked-list review before explicit slot-based admin selection. Release/void/history controls remain unchanged; the revised prerequisites are pending implementation.

Open **Dashboard → Review eligibility and assistance**, or `/assistance/`. The same review is linked from every program application.

1. Open an application and inspect its submitted requirements and private documents. Choose **Assess eligibility**, record each checklist result and remarks, then select the eligibility outcome. Required items must pass and membership must be active for Eligible. The original submission requirements are retained when program configuration changes.
2. Choose **Record decision** to approve, reject or return for review, with remarks and confirmation. Approval requires a current Eligible assessment, active membership, a published program and an available beneficiary slot. Applications remain uncapped. Return for review or a new assessment clears the prior approval; member/program changes require reassessment.
3. After actual delivery, choose **Confirm release**. Record assistance type, delivered benefit, release date, optional cash amount/non-cash estimated value and receipt reference, and required remarks/confirmation. Dates cannot be in the future or before approval. One current successful release is allowed per application.
4. If a release was recorded incorrectly, choose **Void incorrect release**, explain why and confirm. The original record stays in history and stops contributing to received-assistance counts. Renew the assessment and approval before recording a replacement. Released applications cannot be cancelled or reassessed until an incorrect release is voided.
5. Member records show retained release history and a successful-only Previous Assistance count. Pending applications, eligibility assessments, approvals, rejected/cancelled applications, events and voided releases do not count.
6. **Configure eligibility labels** edits the user-approved Pending, Eligible, Review Needed and Not Eligible labels and their availability. Stable underlying meanings prevent a renamed label from bypassing approval checks. Existing assessments retain their original label. Reasons and history are retained for configuration changes.

Access requires active staff, `accounts.access_dashboard`, `programs.view_program`, `programs.view_programapplication`, and `assistance.view_assistancecase`. Assign only the additional capabilities required:

- `assistance.review_eligibility`: record eligibility checklists.
- `assistance.decide_assistance`: approve, reject and return decisions for review.
- `assistance.view_assistancerelease`: view release details and counts, including member history (which also requires `members.view_member`).
- `assistance.record_release`: confirm successful releases; also requires release viewing.
- `assistance.void_release`: void incorrect releases; also requires release viewing.
- `assistance.view_assistancelog`: view detailed retained history. Release/void entries additionally require release viewing.
- `assistance.view_eligibilitystatus` and `assistance.change_eligibilitystatus`: view/edit eligibility labels; these configuration screens need dashboard access but not application access.

Superusers already have access. Existing roles are unchanged. Document downloads continue to require `programs.view_programdocument`. Slots constrain approvals and cannot be reduced below existing reservations. Budget remains planning information; there is no automated budget-based eligibility rule. No generic admin mutation/delete endpoints exist for assistance. EWAF and the fuller analytics/human-validation workspace remain later milestones.

Apply migrations on new installations. Scope and evidence: [70% plan](docs/assistance-plan.md) and [70% validation](docs/assistance-validation.md).
