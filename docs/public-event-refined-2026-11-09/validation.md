# Refined event popup reference — November 9, 2026

Applied the owner's latest visual reference to the existing event popup: balanced 49/51 columns, a 760px maximum width, pastel artwork fading into a dark green summary, a darker details panel, uppercase badge and metadata, green category/icons/timezone accents, section dividers and a muted guidance footer. The description stays visible beside the artwork. Mobile layouts stack the panels.

The popup-specific schedule now shows separate Start and End rows with the date, year and time, followed by the Philippine timezone, location and capacity. Existing audience, participation rules, cancellation warnings and conditional program links remain. The shared full-page schedule and all publication/permission logic remain unchanged. No records, uploaded artwork, business rules or schema were edited.

Validation:

- `node scripts/public_event_poster_qa.cjs` passed all eight light/dark and desktop/mobile combinations (1440, 768, 390 and 320px). Checks include panel placement, metadata and icon colors, Start/End timestamps, visible footer, no horizontal overflow, focus containment and dismissal/focus return.
- High contrast, forced-colors smoke checks, long content with 200% text, image success/failure fallback, unavailable-fragment handling, observance isolation and no-JavaScript full-page navigation passed. Browser-only synthetic responses were never saved to application data.
- Three existing `events.test_public_popup` Django tests passed in a fresh disposable native MySQL database via `scripts/g12_test_runner.py`: publication gates, cancellation, escaping and protected image URLs remain covered.
- Desktop and mobile screenshots were visually inspected. No browser JavaScript errors. JavaScript syntax and `git diff --check` passed.

Evidence: [results](results.json), [desktop](dark-1440.png), [mobile](light-390.png), [high contrast](high-contrast-320.png). This visual treatment supersedes the preceding sidebar styling; its historical evidence is retained.
