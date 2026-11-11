# Public button alignment - 8 November 2026

Centered the Home Get Help & Support arrow by overriding the inherited `space-between` alignment and using a 44px circular target. The heading leaves space for the button. Hover and keyboard focus use a cream background with a charcoal icon; pressed styling stays within the neutral palette.

The Programs Before you apply tracking button now has a compact 44px minimum height, content-sized width, readable wrapping and 16px of space before the divider. Its hover/focus colors use warm gray and dark text. The existing tracking popup hook, destination and availability condition remain intact.

Changes are scoped to `static/css/public-home-v2.css`, `static/css/program-photo-cards.css`, the tracking button's CSS class, and the two templates' asset versions. No business rules, data, forms or routes changed.

Read-only Chrome checks passed at 1920, 1440, 1024, 768, 390 and 320px. The SVG center matches the button center on both axes; the circle remains 44px square, and normal/hover colors match the palette. Tracking measures 44px high with a 16px divider gap and no page overflow. Enlarged text at 200%, high contrast, the Help Desk destination, and opening/closing the blank tracking popup with focus restoration passed. No reference was entered or form submitted. Browser errors: none. Desktop and mobile screenshots were visually inspected.

The configured Django/database check and `git diff --check` passed. The identity-verified development web process was refreshed after checking that no membership or certificate email was being sent; MySQL remained running.

Evidence: [checks](checks.json), [support hover](support-hover-1440.png), [tracking button](tracking-1440.png), and [mobile tracking button](tracking-390.png).
