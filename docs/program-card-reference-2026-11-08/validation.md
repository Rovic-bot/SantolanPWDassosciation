# Public program card reference layout — 8 November 2026

Applied the owner's latest reference: separate image headers, light content surfaces, category/status rows, dark headings, a footer divider and simple arrow action links. Retained the active public portal's charcoal/cream palette and existing uploaded images or initials fallback. Cards grow with their content; the desktop example is approximately 445px tall. Existing descriptions, availability wording, expandable dates and detail links are preserved.

Changed `static/css/program-photo-cards.css` and its cache version in `templates/programs/public_catalog.html`. No database fields, migrations or business logic changed. This supersedes the earlier full-image card presentation and fixed minimum heights.

Read-only Chrome checks on port 8013 passed at 1440, 1024, 768, 390 and 320px: image/header/content ordering, no page overflow or clipped content, action links inside cards with at least 44px height. Keyboard date expansion, high contrast, 200% root text sizing at 320px and navigation to the detail page passed; no browser errors. Desktop/mobile screenshots visually inspected. Evidence is in this directory.

`manage.py check` and `git diff --check` passed. No database writes or server restart were performed.
