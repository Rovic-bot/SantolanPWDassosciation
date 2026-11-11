# Announcement section switch — November 11, 2026

The owner requested separate buttons for Announcements and Program results instead of displaying both lists side by side.

- The private announcement workspace renders one section at a time. Announcements is the default landing section; existing result-chooser routes and selected-program links open Program results.
- Two styled navigation links identify the current section with `aria-current`. The controls support keyboard access and ordinary navigation without JavaScript.
- Section choice is retained in filtering, filter reset and pagination URLs. Changing sections clears the previous selection, review parameter and page numbers. The selected section's existing overview and protected review/publication controls remain available.
- Existing permission checks, query scope, publication services, member data and scoring behavior are unchanged. No schema change is needed.

Validation used synthetic template data with database cursors blocked and browser requests intercepted locally. Eight catalog cases covered defaults, explicit sections, result routes, invalid section input and existing selected-item links. Browser checks passed at 1440, 390 and 320 pixels in light and dark themes: a single full-width list within its existing workspace column, section switching, keyboard activation, filter/reset state, reload, Back navigation, selected-item overview and no page overflow. Both empty states and navigation with JavaScript disabled passed. No browser JavaScript errors were observed. Desktop and mobile dark screenshots were visually inspected.

Python syntax and `git diff --check` passed. No live announcement, publication or member record was created or changed during verification. No emails were sent. This presentation change was checked without running the full application test suite.
