# Newly published programs filter

November 10, 2026. The owner requested a New button beside All programs, Open, Upcoming and Closed, using a one-hour publication window.

## Behavior

- Public Programs now includes **New (count)** immediately after All programs. The URL is `/programs/?period=new`; the count remains visible when zero.
- New includes currently published programs whose `published_at` is later than one hour before the request and no later than the current time. At exactly one hour old, a program leaves New. Drafts, archives, cancellations and future publications cannot enter this filter.
- Results sort by publication time, newest first, with a stable ID fallback for equal timestamps. Creation time and ordinary edits do not restart the window. The existing admin publication service already records `published_at`, including when republishing; no publication behavior was changed.
- New describes publication recency. It does not imply that applications are open. Existing Open, Upcoming, Closed, unavailable/readiness checks and their ordering remain intact.
- Search and category restrictions apply to New results and its count. Pagination retains the filter. Tab changes reset pagination.
- A short explanation identifies the one-hour window. An empty result has a specific message and a link to browse all programs.
- Counts and results are recalculated on catalog GET requests, including filter changes, pagination, Back navigation and reload. Existing no-cache responses and in-place browsing are reused. No background polling or scheduled data updates were added.
- The tab uses the existing public colors and responsive styling, including dark mode and high contrast.

## Verification

Eleven focused Django tests passed on a fresh disposable MySQL instance through `g12_test_runner.py` and `RegistrationIntakeTestRunner`: six new publication-window tests and five existing catalog search/count/pagination/escaping/tracking regressions. System checks reported no issues. The disposable test database was destroyed afterward; no application database was used for these tests.

Coverage includes publication versus creation/update time, the exact one-hour cutoff, the inclusive current instant, future timestamps, visibility exclusions, expiration without changing publication/application status, search/category/count consistency, pagination, both public route names, and required EWAF readiness remaining separate from New.

Read-only Chrome checks on the running local portal passed for 1440px and 390px in light, dark and high contrast with both theme preferences. The checks verified the New tab's placement/count/results, in-place browsing without a document reload or viewport jump, browser Back, a no-JavaScript GET fallback, no horizontal overflow and readable tab/count colors. Screenshots were visually inspected. No browser errors occurred.

`git diff --check` passed, and the local app was restarted. No migration, program publication, application submission or email was performed. The earlier catalog test that assumes non-EWAF application readiness was not part of this focused run; the new readiness test uses the current mandatory-EWAF rule.

Evidence: `backend-tests.log`, `results.json` and the theme screenshots in this directory. Fixed navigation/display controls were hidden only during screenshots of the program header.
