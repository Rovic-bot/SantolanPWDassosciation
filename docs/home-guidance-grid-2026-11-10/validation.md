# Home guidance and support grid

November 10, 2026. Implemented the owner's five-card Tailwind layout on the home page.

The initial dark/indigo palette below was superseded by the owner's same-day request to match the current portal theme. See [theme palette validation](../home-guidance-palette-2026-11-10/validation.md). The grid, content and interactions are retained.

## Presentation

- Deep `#070a11` section canvas, `#1c1d22` cards, 24px card corners, transparent white borders and indigo accents.
- One column below 768px and two columns from 768px. The EWAF card spans both columns at the wider breakpoint. Cards have independent natural heights.
- A 300ms hover transition scales a card to 1.03 and moves it up 4px, with a border highlight and indigo shadow. `group-hover` reveals the details with height/opacity transitions and moves the action arrow.
- The same details appear on keyboard focus. Touch devices show the extra information without requiring hover, and long content remains scrollable. Device and in-app reduced-motion preferences disable motion. Existing large-text and high-contrast settings are respected.
- Contact / Help Desk links to the Community Assistance section; FAQs open the existing FAQ section; EWAF and privacy actions expand and focus the full text in place; Reading help opens the existing Display controls with Escape and focus return.
- Existing published content and editable guidance title/body fields supply the detailed text. Five editable excerpt fields were added to the existing portal content catalog. No publication records, membership data or program rules changed.

## Tailwind build

All new section styling, states and animations are Tailwind utilities in `templates/public/guidance/`. Tailwind 3.4.19 is pinned in `package.json` and the lockfile. Run `npm ci --ignore-scripts` and `npm run build:guidance` after changing utility classes. The generated local file is `static/css/home-guidance.css`; no browser CDN/compiler is needed.

`tailwind.guidance.config.cjs` scopes utilities to `#main-content #home-guidance` and disables Preflight to preserve the Bootstrap-based surrounding portal. Important modifiers resolve existing Bootstrap spacing, border, visibility and opacity utility collisions. The CSS entry point contains only Tailwind directives; the small custom variants connect utilities to existing display preferences and hover capability.

Implementation reference: [Tailwind selector strategy](https://v3.tailwindcss.com/docs/configuration#selector-strategy) and [CLI installation](https://v3.tailwindcss.com/docs/installation).

## Browser verification

Read-only checks against the retained local home page in headless Chrome covered:

- Five cards and exact responsive column/EWAF span behavior at 1440, 768, 767, 390 and 320 pixels in both light and dark portal themes; no horizontal overflow.
- Hidden default details, 1.03 hover scaling, upward movement, shadow, revealed content and moving arrow.
- Keyboard focus, all five actions, privacy/EWAF full-text expansion, Display controls and Escape.
- A touch-enabled 390px viewport, high-contrast colors and both operating-system and application reduced-motion settings.
- No JavaScript errors. No forms were submitted and no records or emails were created by the checks.

`results.json` and section screenshots are included here. Fixed navigation/accessibility controls were hidden only during section screenshots to prevent overlapping the captured cards; the product controls were not changed.

Django database checks, the Tailwind build and `git diff --check` passed. The retained local app was restarted. This validates the revised UI; older carousel-specific screenshot/DOM expectations describe the superseded home guidance layout.
