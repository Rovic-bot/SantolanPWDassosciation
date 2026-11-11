# Program card reference dimensions — 8 November 2026

Implemented the owner's follow-up to match the supplied card layout's dimensions and spacing using the existing charcoal/cream public palette.

- Wide-screen cards measure 480 × 512px, with 240px image headers, 30px content insets, 40px grid gaps and 20px corner radii. The catalog overrides the older nested container width restriction so three full-size cards fit when space permits.
- Category/status labels use 15px type, titles 26px and description/action text 18px. Titles and footer links align across the reference-size row. The application dates and description share a summary text block; keyboard expansion still reveals the complete schedule.
- Closed catalog badges say “Period ended.” Other views retain the full existing availability label. Status computation and application behavior are unchanged.
- Cards narrow with the available page width and use two/one columns on smaller screens. Long content and expanded dates can increase height instead of clipping; mobile uses 24px content padding and 28px gaps.

Changed `static/css/program-photo-cards.css`, `templates/programs/public_card.html`, `templates/programs/availability_label.html`, and the stylesheet version in `templates/programs/public_catalog.html`. No models, database fields or migrations changed. Earlier unrelated working changes were preserved.

Read-only Chrome checks passed at 1920, 1688, 1600, 1440, 1280, 1024, 768, 390 and 320px. Verified all six visible cards fit without page overflow, overlapping content or clipped action links. All three reference-width cards measured exactly 480 × 512px with aligned titles and footer links. Keyboard date expansion, high contrast including description text, 200% root text at 320px, and the detail link passed. No browser errors occurred. Wide-screen and mobile screenshots were visually inspected; measured dimensions are in `checks.json`.

The identity-verified development website was restarted to load cached template changes after checking that no certificate emails were in progress. The existing database remained running. `scripts/current_development.py check` (including the configured database check) and `git diff --check` passed. No application data was changed.
