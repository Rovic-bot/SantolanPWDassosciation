# Retain four-card sizing with swipe — November 9, 2026

Restored the owner's approved maximum of four announcement cards across the desktop row. The single-row layout, mobile responsiveness, image/initials presentation, Home palette, swipe/drag, arrows and dots remain. Additional notices are reached through the existing carousel and batch navigation.

`node scripts/public_announcement_grid_qa.cjs` passed six viewport checks from 1920 to 320px, explicitly requiring four columns at 1920 and 1440px and one row throughout. All 31 browser-only synthetic notices remained reachable. Dot selection, both batch directions, keyboard, touch and mouse dragging, popup focus return, filters/history, large text, printing and no-JavaScript fallbacks passed. No browser JavaScript errors. Desktop screenshot inspected; `git diff --check` passed.

Evidence: [results](results.json), [desktop](cards-1920.png), [mobile](mobile-second-card.png). This corrects the removed four-column cap in the preceding validation. No application data or business logic changed.
