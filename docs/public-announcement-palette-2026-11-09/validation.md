# Announcement popup Home palette — November 9, 2026

Replaced the announcement popup's separate purple/black interface colors with the existing Home/public-portal palette. Its surface, text, muted copy, borders, fallback artwork, fade, badge, action, close control and focus indicator now use shared theme variables. Light mode uses cream/stone/charcoal; dark mode uses warm charcoal with cream text. Original uploaded artwork, layout, content and destinations are retained.

Palette authority: `public-bento.css`, `public-home-v2.css` and `public-dark.css`. The popup uses `--surface`, `--ink`, `--muted`, `--line`, `--stone`, `--brand-primary`, `--control-edge` and `--focus`, so it follows existing display settings rather than introducing another fixed palette.

`node scripts/public_announcement_poster_qa.cjs` passed eight theme/viewport combinations at 1440, 768, 390 and 320px. Verified theme-specific surfaces/text, action and arrow colors, and action contrast of at least 4.5:1 both normally and on hover. Existing keyboard, closing/focus return, high-contrast, forced-colors smoke, long-text/200% text, image fallback, destination, unavailable-content and no-JavaScript checks passed. No browser JavaScript errors. Light/dark desktop screenshots were visually inspected; `git diff --check` passed.

Evidence: [results](results.json), [light palette](card-light.png), [dark palette](card-dark.png), [mobile](light-390.png). No backend logic, database records or event-popup presentation changed in this follow-up.
