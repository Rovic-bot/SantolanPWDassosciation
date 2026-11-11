# Single-row announcement carousel — November 9, 2026

Announcements now display exactly one row of portrait cards. The carousel calculates the number of columns from the available width and a 220px minimum card width, expanding the cards across the row. The former four-column cap and second row are removed. Existing artwork/initials, Home palette, content and popup actions remain.

When more cards are available, a “Swipe or drag to browse” toolbar places previous/next arrows above the row. Clickable position dots sit below it; the current group uses a wider marker. Accessible labels identify the card ranges. Larger batches show a compact dot window with first/last positions, while arrows continue across the existing 24-record server batches. Dot selection returns focus to the carousel. The existing live count, touch/mouse gestures, keyboard navigation and reduced-motion behavior remain.

The old numbered page links are hidden only in the JavaScript-enhanced view because the carousel arrows handle those boundaries. Printing and no-JavaScript rendering retain all cards and ordinary pagination. Other carousels use the existing controls; dots are an optional enhancement activated by the announcement template.

Validation:

- `node scripts/public_announcement_grid_qa.cjs` passed at 1920, 1440, 992, 768, 390 and 320px. Every checked viewport had one row: five cards at 1920, four at 1440, three at 992/768 and one at 390/320. All 31 browser-only synthetic notices were reached, including both server-batch boundaries. Dot selection/current state, arrows, keyboard focus, touch/mouse swipes, popup closing, filters/history, 200% text, reduced motion, print and no-JavaScript fallbacks passed.
- Existing event-carousel checks passed after the shared JavaScript change, with artifacts in `event-regression/`.
- Ten light/dark portrait checks, image/initials and failed-image fallback after filtering, high contrast, forced-colors smoke checks and popup behavior passed with artifacts in `theme-regression/`. The fallback check was updated to navigate to its image card now that mobile displays only one card.
- Desktop and mobile screenshots were visually inspected. No browser JavaScript errors. JavaScript syntax and `git diff --check` passed. The existing Django template assertion now expects one row; backend logic was unchanged.

Evidence: [carousel checks](results.json), [desktop row](cards-1440.png), [mobile second card and dots](mobile-second-card.png), [theme checks](theme-regression/image-theme-results.json), [event regression](event-regression/results.json).

No database records, publication rules, privacy boundaries or schemas changed. Browser edge cases were intercepted responses, never saved records.
