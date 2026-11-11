# Event portrait popup — November 9, 2026

Applied the owner's screenshot reference to scheduled-event popups: a compact rounded portrait card, published image fading into a dark green surface, pastel initials fallback, badge, title/location and three-column date/capacity/time row. The badge says “Community event” rather than inventing a featured designation or exposing an internal author. Cancelled events retain their visible warning.

The full event description, exact schedule including year and Philippine timezone, audience, participation guidance and existing linked-program action remain accessible under “About this event.” Announcement and annual-observance dialogs retain their previous layout. No business logic, records, schema or publication permissions changed.

Validation completed:

- Three existing `events.test_public_popup` Django tests passed using `scripts/g12_test_runner.py` and a fresh disposable native MySQL database. Coverage retained publication gates, cancellation, HTML escaping and permission-checked image URLs. Application data was not used for these tests.
- `node scripts/public_event_poster_qa.cjs` passed eight light/dark combinations at widths 1440, 768, 390 and 320px. Checked fit, no horizontal overflow, badge/text colors, keyboard disclosure, Escape, close button, backdrop dismissal and focus return.
- Browser checks also passed high contrast, forced-colors smoke checks, 200% text with long content, image loading/failure fallback, unavailable-fragment recovery, annual-observance style isolation and no-JavaScript full-page fallback. Edge-case content was intercepted only in the browser; nothing was saved or published.
- Desktop, mobile, dark-mode and high-contrast screenshots were visually inspected. This caught and corrected the shared dark-theme text override on the badge and image fallback.
- `scripts/current_development.py check`, JavaScript syntax validation and `git diff --check` passed. No browser JavaScript errors.

The existing carousel harness now waits for the stable event-content attribute instead of the retired two-column layout class. The retained local server was restarted at `http://127.0.0.1:8013/` to load the template changes.

Evidence: [browser results](results.json), [desktop](light-1440.png), [mobile dark](dark-390.png), [high contrast](high-contrast-320.png).
