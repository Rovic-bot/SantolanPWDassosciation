# Main admin login redirect — November 10, 2026

## Authorized behavior

The owner requested that the native Django admin login URL use the existing main admin sign-in page and open Dashboard after login.

`/admin/login/` (also without the trailing slash) now returns a non-cacheable HTTP 302 to `/accounts/login/?next=/dashboard/`. Incoming query parameters are discarded, including `/admin/auth/user/` or external `next` destinations. The main sign-in form retains its existing staff authentication, throttling, CSRF, session rotation, and audit behavior. A POST to the old URL redirects without authenticating or forwarding credentials. No schema changes or migrations are required.

## Validation

- Ten focused account/foundation tests passed using the isolated native MySQL runner, with no application data used as the test database. Coverage includes both legacy URL variants, internal/external destinations, GET/HEAD/POST, the main login template, successful Dashboard login, invalid/nonstaff/inactive authentication, throttling, CSRF/session handling, and credential-free security events.
- Disposable test run: `santolan-g12-tests-olm6x9jv`; result: 10 tests, OK.
- Headless Chrome against the running site verified the exact requested link, the no-slash URL, and an external `next` parameter all redirect to `/accounts/login/?next=/dashboard/`. The visible main sign-in form contains `/dashboard/` as its hidden next destination. No live account was signed in during this browser check.
- Application configuration check, Python compilation, and `git diff --check` passed.
