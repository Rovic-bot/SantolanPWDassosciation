# Eligibility height and scrolling — 8 November 2026

The owner requested an eligibility card matching the program overview's height, with excess disability types scrolling vertically. A ResizeObserver now measures the rendered overview and updates the eligibility height when the viewport, text or overview content changes. Only the list scrolls; its heading and existing action buttons stay visible. Short lists retain their natural row sizes. At unusually large text sizes the card can grow enough to keep its heading, actions and one full list item usable.

The scrolling list keeps list semantics, has an accessible name, and enters the keyboard tab order only when overflowing. Print and no-JavaScript views show the full list. All eligibility types and application/tracking gates remain unchanged.

Changed `templates/programs/public_detail.html`, `static/css/public-program-detail.css`, and added `static/js/public-program-detail.js`. No database fields, migrations or business logic changed.

Read-only Chrome checks passed at 1600, 1440, 1024, 768, 390 and 320px. The ten-type example's overview and eligibility heights matched exactly at every size. Verified vertical overflow, every original type retained, keyboard End reaching the last item, actions remaining stationary during list scrolling, dynamic overview resizing, 200% text at 320px, a short one-type list without an unnecessary tab stop, complete printed lists and complete no-JavaScript lists. No page overflow or browser errors. Desktop screenshot visually inspected; measurements and screenshots are in this directory.

JavaScript syntax, configured Django/database check and `git diff --check` passed. The identity-verified development web process was refreshed after checking that no certificate emails were in progress; the existing database stayed running. No program records were edited or application forms submitted.
