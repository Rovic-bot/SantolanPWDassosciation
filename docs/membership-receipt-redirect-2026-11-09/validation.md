# Unavailable membership receipt redirect — November 9, 2026

The owner requested that `/membership/registration/receipt/` return to `/membership/register/` whenever it would show the access-denied page. The receipt view now catches denied receipt access and issues a fixed HTTP 302 redirect to the named public Membership route. Both responses use `no-store`/`no-cache`, so the destination loads fresh without a JavaScript reload loop.

Valid owned receipts still show the original submitted information. Missing, malformed, foreign, expired, closed and rate-limited receipt access does not reveal a submission. The underlying service checks, submission/read budgets, Finish revocation, stored applications, issued references and staff permissions are unchanged. Unavailable configuration still returns its existing 503 page. No session-wide reset or deletion of records is performed.

Validation used disposable native MySQL: 80/84 checks passed on the first run. Four older tests had expectations superseded by existing navigation, required PWD numbers and the office-verification workflow; their fixtures/assertions were aligned and all four passed on rerun. The 84 checks cover receipt access, original-data projection, Finish, expiration, cross-session privacy, rate limits, reference/QR preservation and prefill. New checks verify the fixed redirect destination, fresh-page headers, malformed/missing sessions and preserved submissions after expiry.

The local app was restarted. Chrome verified receipt HTTP 302 → `/membership/register/` HTTP 200, `no-store` on both responses and a successful destination reload. No JavaScript errors or POST requests occurred. `git diff --check` passed. No migration, applicant submission, membership decision or email was made.

Evidence: [browser results](browser-results.json), [redirect destination](redirect-destination.png).
