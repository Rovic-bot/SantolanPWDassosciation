# Community Assistance Desk back button — November 11, 2026

Added a back-arrow link before the member avatar in the request header. It uses the named inbox URL, participates in existing workspace navigation, has a descriptive accessible name, a 44×44 pixel target and a visible keyboard focus indicator. Theme colors are inherited and the link is hidden in print.

Actual detail/inbox templates were rendered with synthetic data and database cursors blocked. Intercepted Chrome checks passed at widths 1366, 390 and 320: placement left of the avatar, target dimensions, focus visibility, Enter activation and arrival at the inbox. No JavaScript errors or horizontal page overflow occurred. The desktop dark screenshot was visually inspected. Requests were limited to local fixtures/assets and GET operations; no member record or conversation was changed. Fixtures: temporary directory `santolan-inbox-back-lzm5h1m2`. `git diff --check` passed.
