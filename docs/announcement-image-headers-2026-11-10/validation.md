# Wide announcement and result image headers — November 10, 2026

The owner's follow-up requests the existing illustrated announcement-card treatment at the full width of the filtered view, with complete information available by scrolling below the image.

Both filtered topics now have a full-width image header with the existing rounded corners, icon/category badge, title, short excerpt, date and source. A gradient fades the artwork into the current light/dark surface; the text has an opaque finish behind it for readability. Complete announcement text or authorized result tables follow below in the same card. “View details” is an accessible in-page anchor, not a popup. Single-record swipe navigation and the All view's compact cards/popups remain.

General announcements use their uploaded artwork. Program results and linked-program notices use the program's presentation picture through `programs:public_picture`, which independently checks publication. Title initials remain when no image exists or loading fails. Compact All cards and their popup also use this program artwork. No application photos, private uploads, storage URLs, new disclosure rules or publication actions were introduced. Related artwork is loaded with the board query to avoid a per-card lookup.

Validation:

- **17 Django tests passed** in a fresh disposable MySQL database (`santolan-g12-tests-hxyqcms5`): announcement composer/public board regression tests, the existing program-artwork publication boundary test, and synthetic browser fixture generation. The results integration test verifies actual program-image URLs in the filtered card, All view and popup, excludes private paths, and confirms withdrawal removes the notice and its image reference.
- **20 browser layout/contrast checks passed** at 1440px and 390px in light, dark and high contrast, plus 200% text and forced colors. No horizontal overflow, JavaScript errors or contrast findings. Image loading, full-width cover sizing, gradient presence, in-page detail focus, complete results, no-image initials, swipe/history, All popups and admin-editor regressions passed. [Browser results](results.json).
- Visually inspected the [running portal announcement header](live-announcements-header.png), [desktop program-results header](results-header-dark-1440.png) and [mobile program-results header](results-header-dark-390.png).
- Read-only checks of the running portal returned HTTP 200 and one full card without popup links for each filtered topic. The current first announcement's image loaded; the current first results record has no program picture and correctly uses initials. Image-present result layouts were verified with disposable fixtures using an existing public portal photo.
- JavaScript syntax checks, the development system check and `git diff --check` passed. The development server was restarted with the changes.

No migrations, live record changes, publications or email deliveries. Earlier validation remains historical; this follow-up replaces its unadorned filtered image layout with the requested wide gradient header.
