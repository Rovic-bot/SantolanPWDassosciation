# Program card palette — 8 November 2026

Updated the public program cards to match the active public portal's charcoal, warm gray and cream palette. Replaced olive fallback gradients, green-tinted overlays and badges, and olive buttons. Buttons now use the shared cream surface and dark text, with the shared stone hover color. Existing imagery, layout and program behavior are retained. The catalog stylesheet version was advanced for browser cache refresh.

Changed `static/css/program-photo-cards.css` and the stylesheet version in `templates/programs/public_catalog.html`. No models, database fields or migrations changed.

Read-only Chrome checks against the existing local server on port 8013 passed at 1440, 390 and 320 pixels: six rendered cards, matching computed palette values, no page overflow or clipped card content, button hover, black/white high contrast, and keyboard schedule disclosure. No browser errors were observed. Desktop screenshot was visually inspected. Screenshots and `checks.json` are in this directory.

`manage.py check` and `git diff --check` passed. `manage.py check --database default` could not complete because the shell's configured MySQL login was denied (error 1045). No credentials or database configuration were changed.
