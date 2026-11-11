# Public card sizing — November 8, 2026

Implemented the owner's follow-up to remove vertical card scrolling and combine the short About background and mission sections.

- Shared Home, About, FAQ, resource and observance decks measure their actual rendered content. Longer cards receive additional width before the row grows taller; cards fit into groups with consistent gaps and padding.
- Every card in a deck uses the same height, measured across the entire deck. Switching groups never changes that height. At narrow widths, the shared height grows enough to display the full content; cards have no internal vertical scrolling or clipped text.
- Available row width is distributed among the visible cards. Each group's cards can have different widths according to content length, and more than one appears when space permits.
- About's Background and Our mission headings and text now share one card. The other published sections remain intact. The visual editor still edits the original source content.
- Keyboard, button, pointer/touch, reduced-motion and hash-reveal behavior remain available. Hidden cards are inert. Layout recalculates after viewport, text-size, font or image changes.
- Print and no-JavaScript views keep all content available.

This supersedes the fixed 320 px / vertically scrolling card behavior documented in `../public-browsing-2026-11-08/validation.md`. No business logic, stored content, publication permissions or database schema changed.

Validation: `node scripts/public_card_sizing_qa.cjs` passed 30 deck/viewport combinations across 1920, 1440, 992, 768, 390 and 320 px. Every card was visited and checked for full text visibility, equal height, stable row height, correct offscreen accessibility and no horizontal page overflow. Verified the combined About card, variable widths, the portal's Largest text setting, 200% text, Chrome touch input, print and no-JavaScript fallback. No browser errors were observed. Screenshots and `results.json` are in this directory.

The older public browsing harness was adjusted to accept content-based widths and stable calculated heights. JavaScript syntax and whitespace checks passed. The development server at port 8013 was restarted with updated asset versions. Browser checks did not save content.

## Follow-up: centered cards and full-width downloads

The Resources Download a form card now spans the full help-options grid row. Swipe groups keep their content-sized widths and are centered in the available row; a lone final card is no longer stretched across the viewport. The shared height, complete text visibility and responsive packing are preserved.

Reran the 30 deck/viewport checks with explicit assertions for centered groups on every page and a full-width download card at every tested screen width. All passed, including large text, touch, print and no-JavaScript checks. The final guidance card is shown in `centered-last-guidance.png`.

## Follow-up: compact Guides and resources cards

The resource guide deck now uses its measured content height without the 320 px minimum. Cards still share one stable height, retain centered positioning and show all text without internal scrolling. Read-only Chrome checks visited every group at widths 1440, 768, 390 and 320 px; the shared heights were 245, 245, 234 and 257 px respectively. Screenshot: `compact-resource-cards.png`. JavaScript syntax and whitespace checks passed, and the local server was restarted with the new asset version.
