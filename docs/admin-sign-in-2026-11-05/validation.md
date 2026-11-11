# Administrator sign-in redesign — November 5, 2026

The owner identified `/accounts/login/?next=/dashboard/` as missing from the public portal redesign and requested its UI be updated. The page now uses the public Make palette, local Manrope fonts, official Association seal, and existing community photograph. The Make export explicitly provides no staff sign-in, so this is a matching authentication layout rather than a copied prototype login screen.

## Changes

- `templates/accounts/login.html` now extends the shared base with a dedicated header, desktop community introduction, login panel, help text, and compact footer. Small screens prioritize the form. The authenticated state retains workspace and POST sign-out actions.
- `static/css/staff-sign-in.css` provides the scoped navy/blue theme, responsive layout, visible field labels and focus states, error styling, and display-preference colors. Existing local font and image assets are reused.
- The existing resident layout boundary test was renamed to describe the separate authentication layout; its assertions are unchanged.

The form action, Django fields and errors, CSRF token, hidden `next` value, password input, authentication backend, permissions, throttling and session logic remain unchanged. No migrations or application data edits were needed. Existing unfinished Git work was preserved. The original login template is retained in ignored `.local/admin-sign-in-20261105/before/login.html`.

## Checks

- Django system check passed; static files were collected and the retained local server restarted.
- The exact live URL returned HTTP 200. Read-only HTML checks confirmed the POST action, CSRF field, password input, associated labels and `/dashboard/` redirect value. The dedicated CSS, local Manrope font and community image returned 200. See [HTTP check results](http-checks.json).
- Ran `accounts.tests.test_accounts` and `core.tests.test_resident_layout_boundary` with `scripts/g12_test_runner.py`: **20 passed, 2 failed**, out of 22 tests. This used fresh disposable MySQL with `.env` disabled. Passing checks cover generic invalid-login errors, redirect safety, CSRF, session rotation/invalidation, throttling/concurrency, audit handling, and layout boundaries.
- Both failures are existing dashboard text expectations: `test_group_permission_grants_access_and_revocation_is_immediate` expects the configured group name in dashboard HTML; `test_superuser_login_and_safe_default_destination` expects `Manage roles (groups)`. Re-running those two tests with the original login template overlaid in memory produced the same failures. `scripts/admin_sign_in_baseline_runner.py` records this comparison mechanism without rolling back live files. See [authentication and baseline summaries](authentication-checks.json). No dashboard files or test expectations were changed for this task.
- Native Brave inspection checked the laptop desktop layout, a 1440×900 CSS-pixel preview and a 320×700 CSS-pixel preview. The mobile form, labels and action fit without horizontal scrolling. The blank live form was not submitted and no stored credentials were used.
- Saved and visually inspected [desktop](sign-in-desktop.png) and [320px mobile](sign-in-320.png) full-page screenshots through Brave DevTools. These were captured at device pixel ratio 2.
- Git whitespace checking passed. The new CSS, template, baseline helper and boundary-test file also passed explicit trailing-whitespace checks.

The retained local preview is [Administrator sign in](http://127.0.0.1:8013/accounts/login/?next=/dashboard/). This validation does not claim that the unrelated dashboard assertions pass or establish a production deployment or full accessibility certification.
