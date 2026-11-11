# Foundation validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


Date: 2026-09-18 (Asia/Manila).

## Verification results — passed

- Django configuration check: passed, no issues.
- Full suite: **19 tests passed** against MySQL (2.482 seconds, excluding database creation/migration). Twelve configuration/public tests cover required environment values, strict boolean parsing, host lists, separate test database naming, public homepage, HTTP methods, private media, security headers, allowed hosts, local assets, and login CSRF. Seven database/access tests cover native MySQL/strict SQL/UTF-8/InnoDB, anonymous/nonstaff/inactive access, staff versus superuser permissions, password hashing, session rotation, and CSRF-protected logout.
- Chrome browser checks: passed. Desktop/mobile rendering, keyboard skip navigation, mobile navigation expand/collapse, labeled admin login, and no horizontal overflow at 320, 390, 768, and 1440 pixels. No page exceptions or failed resource responses during the successful run.
- Desktop, mobile, and admin-login screenshots inspected. Fixed narrow-screen grid overflow and decorative illustration/caption overlap found during QA.
- Static collection: passed, 132 files copied, including local Bootstrap and Django admin assets.

Browser screenshots and the local QA harness are in ignored `.local/`. They are verification aids, not application dependencies. The final successful browser run used the normal Django launcher after MySQL setup. A temporary WSGI preview used during development was stopped.

## Database and final launcher verification

- MySQL 8.4.11 archive: 281,191,914 bytes; verified against published MD5 `2e833921898a9a030ea6bfe81bd811bc` and ZIP CRCs before extraction.
- Native instance: `127.0.0.1:3307`, data under ignored `.local/mysql-data`. XAMPP's MariaDB 10.4.32 was not modified or used. No Docker or SQLite.
- `manage.py check --database default`: passed, no issues.
- `manage.py migrate --noinput`: all 18 built-in auth/admin/contenttypes/session migrations applied successfully. No custom fields or domain tables were added.
- `manage.py migrate --check`: passed; no outstanding migrations.
- `manage.py makemigrations --check --dry-run`: no changes detected.
- `manage.py test --verbosity 2`: all 19 passed; `test_santolan_pwd` was created and destroyed independently of `santolan_pwd`.
- `pip check`: no broken requirements. Python source compilation passed.
- `scripts/local_mysql.py stop` followed by `scripts/run.ps1`: database shut down cleanly, restarted, and Django started successfully.
- Live HTTP checks: `/` and `/admin/login/` returned 200; anonymous `/dashboard/` returned 302 to the admin login; site CSS and Bootstrap CSS/JS returned 200; private `/media/private.pdf` returned 404.
- No superuser was seeded. Create Admin.cmd provides interactive account creation; tests verified authenticated staff and superuser behavior in the disposable test database.

`manage.py check --deploy` against the local HTTP environment reported five expected warnings: W004 (HSTS), W008 (HTTPS redirect), W012/W016 (secure cookies), and W018 (DEBUG). This is not a production-readiness pass. Production settings and hosting must be configured and checked during the deployment milestone.

## Scope limitations

- This is a local foundation, not a production release. No real member records or sample business announcements are seeded.
- The user creates their own administrator using Create Admin.cmd; no default admin password is assigned.
- Future membership, publishing, events, assistance, EWAF, configurable RBAC, login attempt protection, and domain audit workflows are not implemented.
- Authentication currently uses Django's built-in User. Resolve the custom-user decision before adding domain relationships.
- Sensitive media is not served publicly. Upload validation and authorized document delivery belong to their future modules.
- Manual assistive-technology evaluation and broader UAT remain future work; responsive/keyboard checks do not establish complete accessibility conformance.
