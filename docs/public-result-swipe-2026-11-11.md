# Public program result swipe — November 11, 2026

The owner requested a visible drag/slide animation like Annual Observances, with the previous/next arrows on opposite sides of the full result card.

## Changes

- The filtered Program Results carousel opts into live dragging. Full cards share a grid cell, keeping the outgoing and incoming cards on the same horizontal track instead of stacking them vertically during the animation.
- The current card follows the pointer and reveals its neighbor. Release advances the slide or animates a short/cancelled drag back into place. The current viewport height is held during the drag and natural card height is restored afterward.
- Desktop/tablet navigation arrows flank the result cover. On narrow phones they flank the heading above the full-width card so the tables remain readable. Arrows retain 44 px targets, focus indicators, disabled-end states, and existing keyboard navigation.
- Reference-search inputs and scrollable result tables retain their interactions. Vertical gestures remain page scrolling. Both OS and in-app reduced-motion preferences disable moving-card animation.
- Existing server pagination, public result projection, publication permissions, masking, and release status are unchanged. No backend or database change is required.

## Verification

Current Django templates were rendered with fictional in-memory notices and blocked database cursor access. Chrome/Playwright intercepted all page and asset requests; the external Tailwind script was stubbed without contacting its service.

Passed: held mouse drag with the next card visibly alongside the current card; completion and short-drag snap-back; arrow and keyboard navigation; end boundaries; local reference search; table gestures; desktop/dark layout; 768/390/320 px layouts without horizontal page overflow; native touch swipe; OS/in-app reduced motion; single/empty results; Annual Observances navigation regression. Desktop and mobile screenshots were visually inspected. JavaScript syntax and diff whitespace checks passed.

No actual records were read or changed, no emails were sent, and no migrations or database test suite were run.
