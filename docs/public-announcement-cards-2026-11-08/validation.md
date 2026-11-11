# Announcement swipe cards — November 8, 2026

Implemented the owner's reference-card design for the public Announcements page: translucent rounded cards, date tiles, small category/latest labels, title, excerpt and a plain Read announcement link. Following the owner's latest clarification, the grid fills the available horizontal space with one to four columns and at most two rows per swipe view. It fits three columns at 1440 px and four at 1920 px, with two or one on narrower layouts. Cards share a content-measured height within each batch; fewer published notices use only the rows needed.

The existing swipe component supplies horizontal touch gestures, mouse dragging, previous/next buttons and arrow keys. Announcement pagination returns bounded batches of 24 notices, supporting full swipe groups of 2, 4, 6 or 8 cards. Reaching a batch boundary requests the adjacent page through the existing in-place browsing flow, retaining filters and publication checks. Backward navigation reveals the previous batch's last group. The current visible range is announced and keyboard focus stays on the viewport across group changes. The carousel initializes after result updates and releases observers/listeners belonging to replaced decks. Print, no-JavaScript and editor views retain all cards on the current results page, with ordinary pagination links available.

Validation:

- `node scripts/public_announcement_cards_qa.cjs` (delegates to `public_announcement_grid_qa.cjs`): passed at 1920, 1440, 992, 768, 390 and 320 px. Browser-only response fixtures simulated 31 notices; every notice was reached at every width, with at most two rows. Verified batch transitions in both directions, both touch directions, mouse dragging, repeated keyboard navigation, popup close/focus restoration, in-place filters, empty search, browser Back, reduced motion, 200% text, print and no-JavaScript fallback. No JavaScript errors or horizontal page overflow. Screenshots show actual published content, not simulated records.
- `.venv/Scripts/python.exe scripts/g12_test_runner.py test announcements.test_public_board --noinput`: seven tests passed against fresh disposable MySQL with application data excluded. Includes bounded 24-item pagination/order, retained search/topic parameters, publication privacy and empty results.
- `node scripts/public_event_carousel_qa.cjs`: passed existing event swipe/popup checks.
- `node scripts/public_card_sizing_qa.cjs`: passed 36 responsive deck checks and existing text-size/touch/print/fallback checks.
- Syntax checks for `public-swipe-cards.js` and `public-browse.js`, `scripts/current_development.py check` and `git diff --check`: passed.
- Inspected desktop and mobile screenshots. Screenshots and `results.json` are retained alongside this note.

The local server at `http://127.0.0.1:8013/` was restarted to load the templates and asset version. Browser checks were read-only. No database records, schema, publication permissions, selection rules or private evidence were changed. Existing unfinished repository work was preserved.

## Responsive width and compact results panel

The earlier 64rem row cap and 42rem deck cap are removed. At desktop widths, a compact results column sits at the right edge while announcements use the remaining width, fitting additional columns at a minimum usable card width of 300 px. Below 1200 px, the results panel moves below the announcements. It stays aligned to the top of its area and uses its content height, without the previous minimum/full-row height or auto-pushed button spacing.

The responsive layout recalculates after resizing and preserves the focused card's group. Existing event and general content decks retain their original layout settings. Inspected desktop and mobile screenshots and reran their regression harnesses alongside the announcement acceptance checks.
