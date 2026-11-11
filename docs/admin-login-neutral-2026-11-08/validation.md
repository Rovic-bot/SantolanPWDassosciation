# Admin login visual alignment — November 8, 2026

The owner requested that `/accounts/login/` match the current public portal. The dedicated login template and stylesheet now use its warm canvas (`#e8e5df`), cream cards (`#f4f2ec`), charcoal actions (`#2a2826`), dark text (`#1c1a18`) and muted text (`#6b665f`). Arial typography, rounded surfaces, pill badges, the current Association logo and a softly faded existing community image match the public pages. On small screens the login form takes priority.

The Django form action, rendered fields and errors, CSRF token, hidden `next`, password input, authenticated-state workspace link and POST logout remain intact. No authentication code, permissions, session policy, records or database schema changed. The stylesheet is scoped to `staff-sign-in` and does not restyle the admin workspace or public pages.

Validation:

- `node scripts/admin_login_neutral_qa.cjs` passed at 1440, 1024, 768, 390 and 320 px: no horizontal overflow, associated visible labels, password masking, required form metadata and keyboard order.
- Inspected screenshots for normal, generic error, already-signed-in and enlarged-text/high-contrast states. Error appearance was simulated in the browser without invalid live login attempts. The no-JavaScript form remained available.
- A successful sign-in using the existing local test administrator reached `/dashboard/`. The authenticated login screen showed the workspace and logout actions; POST sign-out returned to the anonymous form. No credentials are included in screenshots or results.
- Seven existing tests passed in disposable MySQL through `scripts/g12_test_runner.py`: generic invalid-user errors, unsafe redirect rejection, CSRF/session rotation/logout, credential-free security audit events and resident/staff layout boundaries.
- Django configuration, browser harness syntax and `git diff --check` passed. No browser script errors were observed.

Evidence is in `results.json` and the screenshots alongside this note. The local server on port 8013 was restarted with the versioned stylesheet and template. This supersedes the November 5 navy/blue login presentation; that earlier validation remains historical evidence.
