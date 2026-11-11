# Admin annual observance carousel — 9 November 2026

Replaced the flat quarter grid with the requested centered carousel in both the Events workspace and the dedicated Annual observances page. Q2 starts in front, with angled Q1/Q3/Q4 previews. Compact cards use the existing Admin dark/light palette, with month labels, recurrence, publication status and the original record links. Navigation supports dots, arrows, keyboard, preview clicks, mouse dragging and touch swipes; there is no autoplay.

The active card is 352px wide on desktop and shrinks on narrow screens. Its minimum height is 332px; all quarters are measured to accommodate longer titles, multiple records in a month and enlarged text. Inactive previews are inert and hidden from assistive technology. Without JavaScript and when printing, all four quarters remain available. Resources are managed through `WorkspacePage` so changing Admin tabs disposes listeners and observers correctly.

Only the shared quarter partial, its workspace asset includes, and two new carousel assets changed. No models, migrations, permissions, publication logic or saved records changed. A comparison against the pre-edit partial confirmed the same 12 row labels, recurrence/status text and destinations, ignoring formatting whitespace and the replacement of the text arrow with an SVG.

Validation:

- 40 quarter/theme/viewport combinations passed: Q1–Q4, dark/light, and widths 1440, 1100, 768, 390 and 320px. No page overflow or clipped active-card content.
- Keyboard navigation, wrapping, focus transfer, preview clicks, mouse dragging and native touch swiping passed. Touch capture correctly transfers from the child element to the stage.
- 200% text at 320px, high contrast, reduced motion, multiple rows per month, printing and the no-JavaScript fallback passed.
- Both Admin entry points render successfully; Events retains its filters. Actual workspace replacement without a full page reload initializes one carousel and keeps navigation working.
- No browser JavaScript errors. JavaScript syntax, retained-development Django system/database checks and `git diff --check` passed.
- Desktop/mobile screenshots were visually inspected. Browser checks used read-only rendered previews with real static assets. No forms were submitted or emails sent.
- Refreshed only the identity-checked local web process after checking for active email delivery. MySQL remained running.

Evidence: [results](results.json), [dark desktop](quarters-dark-1440.png), [light desktop](quarters-light-1440.png), [dark mobile](quarters-dark-390.png), [light mobile](quarters-light-390.png), [Events workspace](events-workspace-quarters.png).
