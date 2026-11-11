# Fresh checkout setup

This guide is for the `development` branch in `Rovic-bot/SantolanPWDassosciation`. It installs the current application on a separate computer with its own empty database. Do not apply empty-database instructions to an existing operational database; back up and review its upgrade path first.

## Requirements

- The development machine uses Python **3.14.5**, Django **5.2.17**, and native MySQL **8.4.11**. Python packages are pinned in `requirements.txt`. These exact versions are the reproducibility baseline; other combinations need their own validation.
- Git and a browser. Windows development launchers are included. On another OS, use the equivalent virtual-environment Python and Django commands; the Windows launcher is not portable to Linux/macOS.
- LibreOffice, including its `soffice` executable, for converting personalized certificate DOCX documents into PDFs. This is a separate application, not a pip dependency.
- An authorized Gmail account and Gmail app password for actual email delivery. Each installation supplies its own connection in **Community Assistance Desk → Association email settings**.
- Node is optional for rebuilding the already committed Tailwind stylesheet and running browser checks. `npm ci` and `npm run build:guidance` rebuild that stylesheet. No frontend build is required just to run the committed assets.

## Clone and configure

PowerShell, in the folder where you keep projects:

```powershell
git clone --branch development https://github.com/Rovic-bot/SantolanPWDassosciation.git
Set-Location SantolanPWDassosciation
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
```

Put the generated secret in `SECRET_KEY` in your local `.env`. Set your own MySQL database, application username/password, host, and port. Keep `DB_TEST_NAME` a different disposable name starting with `test_`. Do not publish `.env` or reuse another installation's credentials. Keep the secret stable after connecting Gmail: stored credentials are encrypted with it.

The example enables the current EWAF vault/scoring, application workflow, online Association/PDAO intake, secure tracking, and Assistance Desk. It selects Gmail for certificates. `ASSOCIATION_REGISTRATION_POLICY_FILE=config/registration_policy.development.json` loads the non-secret workflow configuration used by the current development system, including onsite registration and handoff. It contains no users, member records, mail credentials, or connection manifests. Review its institutional instructions before live use; software configuration is not government approval or institutional sign-off.

## Supply MySQL

Choose one route:

1. **Existing MySQL installation:** create an empty `utf8mb4` database and dedicated application account, then set `.env` to that database. The account needs schema privileges for migrations. Test grants, if provided, must be limited to a separate disposable test database. Avoid a root application account.
2. **Project-local MySQL on Windows:** the existing `scripts/local_mysql.py` helper supports the exact MySQL **8.4.11** Windows archive. Download `mysql-8.4.11-winx64.zip` from MySQL's official distribution to `.local/downloads/mysql.zip`. Use `DB_NAME=santolan_pwd`, `DB_USER=santolan_app`, `DB_TEST_NAME=test_santolan_pwd`, and your own random `DB_PASSWORD` in `.env`, then run:

```powershell
.venv\Scripts\python.exe scripts/local_mysql.py init
```

The helper verifies its pinned archive checksum, refuses an existing data directory/account configuration, binds to loopback, and sets the local port to 3307. On subsequent runs use `scripts/local_mysql.py start`. Never copy the original developer's `.local` folder: it contains private runtime credentials and database files.

## Create the schema and administrator

Only after pointing `.env` at the new empty database:

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py check --database default
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8013
```

Open `http://127.0.0.1:8013/` and sign in at `/accounts/login/`. No default username/password is provided. Migrations create schema/reference configuration, not the developer's members, programs, receipts, or users. Do not run `demo_data`, `ewaf_demo`, historical scenario harnesses, or model-sync commands to initialize this installation.

`Start System.cmd` also starts a configured fresh checkout after checks; it does not migrate or seed data. Keep its console open and stop it with **Ctrl+C**. Close that server before using `Restart System.cmd`. `Create Admin.cmd` and `Create Administrator.cmd` use this checkout's database.

The original developer's computer retains its identity-checked startup when `.local/development/` exists. Missing or invalid manifests inside that managed directory still fail closed. New clones do not need that directory. Explicit `DJANGO_SETTINGS_MODULE` / `--settings` arguments retain Django's usual precedence.

## Complete the feature configuration

- **Email:** connect your sender in Association email settings. Existing email actions and saved retry statuses are included. A completed SMTP request is not proof of arrival in the recipient's inbox. Do not copy the developer's password or encrypted connection row.
- **PDF certificates:** install LibreOffice and either put `soffice` on PATH or set `CERTIFICATE_OFFICE_EXECUTABLE` to its executable in `.env`, then restart the app. The required DOCX template is committed at `announcements/certificate_templates/assistance.docx`. Publishing results can trigger certificate generation/email; configure and test the authorized sender first.
- **Membership and permissions:** review Membership settings, the manual PRPWD link/checklist, local registration policy, and staff roles. Ordinary staff need the corresponding model/workflow permissions. No member account is required. There is no government-database connection to configure.
- **EWAF:** code and migrations include the current rules. Administrators still configure/approve weights and program requirements, verify inputs, generate rankings, and select beneficiaries. An empty database has no earlier approved weights or calculation history.
- **Annual observances:** use **Events Calendar → Annual observances → Create annual observance**, then review and publish. To intentionally initialize the bundled reference catalogue instead, the existing audited command is available:

```powershell
.venv\Scripts\python.exe manage.py publish_annual_calendar --username YOUR_ADMIN --notes "Approved initial reference calendar for this installation"
```

This command publishes reference calendar entries and preserves previously installed entries/edits. Run it only when you intend to publish that catalogue. The creation/editing UI works independently. Local customized cards and uploaded artwork do not transfer through Git.

- **Public content and images:** required default assets are committed. Database-backed CMS edits, announcements, schedules, uploaded images/documents and results must be entered or transferred separately through an authorized private process. Protected uploads must never be exposed as unrestricted `/media/`.

## Verify and update

```powershell
.venv\Scripts\python.exe manage.py check --database default
.venv\Scripts\python.exe manage.py migrate --check
.venv\Scripts\python.exe manage.py collectstatic --noinput
```

Run tests only against disposable data. `scripts/action_feedback_browser.cjs` uses a synthetic loopback fixture server; it requires Playwright and Chrome (`PLAYWRIGHT_MODULE` / `CHROME_EXECUTABLE` can point to your installations). The retained G12 harness additionally requires its MySQL binary and creates a separate temporary database instance. Historical test notes are dated evidence, not a blanket claim that every old test matches the current UI.

Before updating an installation, back up its database and private media, review migration changes, then pull the intended branch and install its requirements. Preserve the local secret and Gmail configuration. See the publication validation note for checks actually performed on this snapshot.

For online deployment use `config.settings_production`, `requirements-production.txt`, explicit HTTPS/hosts, MySQL TLS, private persistent storage, and backups; see `render-deployment-preparation.md`. Pushing this branch does not provision or deploy a server.
