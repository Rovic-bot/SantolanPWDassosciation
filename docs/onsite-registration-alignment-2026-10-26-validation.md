# Association onsite registration alignment — 2026-10-26

The owner requested the public **Pending Association registration** fields on the Admin **Onsite registration** form, with a required PWD number on the Admin side. This scoped request applies to the current online Association workflow documented in `online-membership-2026-10-26-validation.md`; it does not adopt other October 10 target requirements.

## Changed behavior

- `OnsiteRegistrationForm` inherits the public registration form. Applicant fields, order, options and validation remain shared; the existing PWD number becomes required for onsite intake, with an appropriate label and instructions. Public submission still permits an absent PWD number. Numeric strings retain leading zeros and hyphens.
- With the current Association profile enabled and the existing pending-intake permissions, the main Onsite registration entry uses the existing walk-in pending intake. The printed and walk-in entry points use the same form. Older policies and role configurations retain the historical onsite writer; no permissions were granted or broadened.
- Staff intake and the pending registration decision page reuse the public section/grid partial, stylesheet and number/age behavior. Online-reference lookup remains available. The decision page marks PWD No. required for approval; declining an incomplete submission remains possible without supplying an ID number.
- The service independently validates the required onsite PWD number. New intake remains pending until an explicit existing Admin decision. Original online submissions, references, private attachments and decision/correction history remain retained. There are no model, migration, PDAO, program or EWAF changes.

## Verification

**101 focused tests passed** on a newly initialized disposable MySQL instance, with project `.env` loading disabled and separate synthetic media. Coverage includes field parity, the main onsite/printed/walk-in pages, required and malformed PWD rejection at HTTP/service boundaries, public submission without PWD, same-record prefill, onsite persistence and approval, number formatting, permissions, idempotency, duplicate members, concurrent decisions, rollback, retained history and the existing manual approval path.

Command (the existing Windows temporary-directory compatibility wrapper was copied into the task's ignored directory):

```powershell
.venv\Scripts\python.exe -B .local\onsite-registration-20261026\run_tests.py test membership.test_onsite_registration_alignment membership.test_registration_decisions membership.test_registration_intake membership.test_pdf_registration membership.test_number_fields membership.test_registration_prefill membership.test_quick_approval --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Retained log: `.local/onsite-registration-20261026/temp/santolan-g12-tests-spvfcp5q/django.log`. The temporary-folder wrapper only inherits the already restricted workspace ACL for newly created synthetic directories; it does not change application configuration or data.

`manage.py check`, browser harness JavaScript syntax, and `git diff --check` passed. `makemigrations --check --dry-run` reported no changes, with a warning that the ordinary configured database was unavailable. `check --database default` could not connect to that database; no application database was started, migrated or used for tests.

The new browser journey covers shared visible fields, required PWD, saved intake, explicit approval and responsive screenshots. Browser execution is **not validated** here: Node launch failed with `EPERM`; a file-backed Python launch reached Chromium but failed on Windows IPC access before a page opened. No screenshots or responsive-pass claim is made. The harness remains available as `scripts.onsite_registration_browser_qa` for an environment allowing browser processes.

## Main development verification

The owner confirmed **http://127.0.0.1:8000/** as the main development site and supplied the public form screenshot as the layout reference. The site's branch header and local launcher identify this source checkout, using `.local/ronnel-development-20261026/ronnel_settings.py` and its retained fictional database. `Start System.cmd` and `Restart System.cmd` now target that configuration on port 8000. They no longer launch the separate port-8003 runtime.

The identified main server was successfully restarted. An authenticated HTTP check against port 8000 verified all **30 fields** in the public and onsite forms, including identical order and required status except for the onsite-only PWD requirement. Both use the same seven section/grid groups shown in the screenshot. The current main Onsite route is `/membership/applications/new/`.

Fresh-process rendering in the actual main settings also passed `check --database default` and `makemigrations --check --dry-run` with no changes. The verification rejected every non-read SQL statement and substituted only the staff GET's submission-token issuer, so no applicant data was written. Its ignored helper is `.local/onsite-registration-20261026/validate_main.py`; the subsequent real HTTP check is `validate_main_http.py`. The HTTP check signed in through the normal login, opened both forms and the requested EWAF breakdown, then signed out. It submitted no applications and generated no calculations.

The separate, divergent membership runtime was not overwritten. The pre-existing edits to `templates/ewaf/tabs.html`, `templates/programs/manage_detail.html` and concurrent documentation changes were preserved. No commit, push, migration or hosted deployment was performed. Browser screenshot verification remains unavailable as described above; HTML/HTTP checks are not a browser visual pass.
