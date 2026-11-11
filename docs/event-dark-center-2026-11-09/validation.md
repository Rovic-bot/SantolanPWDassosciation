# Event dark colors and centered quarters — 9 November 2026

Public scheduled-event cards now fade into the portal's charcoal surface in dark mode. The image fallback uses the same backing color as the photo region, and the text area no longer has a white overlay. The mobile vertical gradient follows the same theme. Light mode, high-contrast precedence, printing, event content and popup links are retained.

The Admin quarter carousel now has equal previews to the left and right of the active card. The opposite quarter sits behind the active card instead of extending the right edge of the stack. All four quarters remain reachable through the existing navigation, keyboard and swipe controls.

Validation:

- Ten public event theme/viewport checks passed: dark/light at 1920, 1440, 768, 390 and 320px. Checked photo and initials cards, theme gradients, dark text/button-hover contrast, content fit and page overflow. Event popup, high-contrast precedence and print fallback also passed.
- Forty Admin quarter/theme/viewport checks passed. The active card and the complete stack each stay within 1px of the stage's horizontal center across all quarters, dark/light modes, and 1440, 1100, 768, 390 and 320px.
- Existing quarter keyboard, focus transfer, wrapping, preview clicks, mouse dragging, native touch swiping, 200% text, high contrast, multiple rows per month, printing, no-JavaScript fallback and workspace navigation checks passed.
- Compared all 12 Admin row labels, recurrence/status text and destinations with the earlier template; these remain unchanged.
- Screenshots visually inspected. No browser JavaScript errors. JavaScript syntax and `git diff --check` passed. Only presentation assets and their cache versions changed; no database writes or forms submitted during verification.
- Refreshed only the verified local web process; MySQL and application records were retained.

Evidence: [public checks](public-results.json), [Admin checks](results.json), [dark event cards](public-events-dark-1440.png), [mobile event card](public-events-dark-390.png), [centered quarter cards](quarters-dark-1440.png).
