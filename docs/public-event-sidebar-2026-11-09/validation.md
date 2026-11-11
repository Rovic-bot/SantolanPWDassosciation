# Visible event details beside the card — November 9, 2026

Following the owner's correction, the scheduled-event popup now grows to 800px with the portrait artwork/summary on the left and the description, complete schedule and participation guidance on the right. Removed the “About this event” disclosure. Details are visible immediately. Below 650px, both panels stack inside the scrollable popup. Existing published content and linked-program actions remain intact.

This supersedes the collapsed-details layout recorded in `../public-event-popup-2026-11-09/validation.md`.

Verification:

- Updated `scripts/public_event_poster_qa.cjs` passed eight light/dark checks at widths 1440, 768, 390 and 320px. Assertions cover side-by-side versus stacked placement, visible descriptions/schedules, no disclosure controls, no horizontal overflow, colors and focus containment.
- Close button, Escape, backdrop dismissal and focus restoration passed, along with high contrast, forced-colors smoke checks, long content at 200% text, image fallback, unavailable-content handling, observance isolation and no-JavaScript navigation. No browser JavaScript errors.
- Desktop and mobile screenshots were visually inspected. Browser checks were read-only; synthetic edge cases were intercepted in the browser only.
- Three existing `events.test_public_popup` tests passed against a fresh disposable native MySQL database via `scripts/g12_test_runner.py`; application data was excluded. JavaScript syntax and `git diff --check` passed.

Evidence: [results](results.json), [desktop](light-1440.png), [mobile](dark-390.png).

Only popup presentation, stylesheet cache version and its browser checks changed. No database records, business rules or schema changed.
