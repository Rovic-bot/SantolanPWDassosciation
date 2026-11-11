# Compact program cards and pagination hover — 8 November 2026

Applied the owner's follow-up to reduce card height/text size while retaining the approved widths, and to correct the pagination hover appearance.

- Removed the fixed 512px minimum card height. Image headers are 208px; titles are 22px, body/action text 16px and category/status labels 13px. Reduced vertical padding and gaps. Cards still grow for long content or expanded dates, and action links retain 44px touch targets.
- Existing card widths and grid gaps are unchanged. At 1920px, the first row measures 480px wide and approximately 429px high (previously 512px). Mobile cards expand naturally as text wraps.
- Pagination uses consistent rounded 44px targets, a warm-gray hover/focus surface with dark text, charcoal/white current-page styling, and neutral borders. This overrides the earlier navy hover token and blue active border. Disabled controls retain their existing behavior. High contrast and visible keyboard focus are preserved.

Changed `static/css/program-photo-cards.css` and its stylesheet cache version in `templates/programs/public_catalog.html`. No business logic, models, database fields or migrations changed. Earlier work was preserved.

Read-only Chrome checks passed at 1920, 1688, 1600, 1440, 1280, 1024, 768, 390 and 320px. Compared every measured card width with the previous validation: all were unchanged. Verified no page overflow, clipped content or overlapping text; 44px action targets; exact computed font sizes; stable pagination dimensions during hover; current-page hover colors; keyboard navigation to page 2; Next navigation to page 3 and its disabled Next state; expandable schedules; high contrast; and 200% text at 320px. No browser errors were observed. Desktop, mobile and pagination-hover screenshots were visually inspected; `checks.json` records measurements.

The identity-verified development website was restarted to load the stylesheet version after confirming that no certificate emails were in progress; the existing database stayed running. The configured Django/database check (`scripts/current_development.py check`) and `git diff --check` passed. No application data was changed.
