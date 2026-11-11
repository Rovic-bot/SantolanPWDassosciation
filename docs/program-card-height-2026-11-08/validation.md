# Shorter public program cards — 8 November 2026

Reduced the catalog card minimum height from 32rem to 29rem on desktop and from 30rem to 27rem on mobile (48px shorter at the default text size). Reduced the artwork-to-content spacer and moved fallback initials upward to preserve separation. Cards can still grow for longer content or expanded application dates. The palette, text sizes and button touch targets are preserved.

Changed `static/css/program-photo-cards.css` and advanced its cache version in `templates/programs/public_catalog.html`. No models, database fields or migrations changed.

Read-only Chrome validation on the existing local server passed at 1440, 1024, 768, 390 and 320px: card heights were 464px on desktop/tablet and 432px on mobile, with no page overflow, clipped card content, initials/title overlap or buttons outside cards. Buttons retain at least 44px height. Keyboard schedule expansion also passed. Desktop screenshot visually inspected. Screenshots and measured heights are saved alongside this note.
