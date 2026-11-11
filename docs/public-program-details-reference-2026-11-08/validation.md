# Public program details reference layout — 8 November 2026

Implemented the owner's requested reference layout using the existing charcoal, cream and warm-gray palette. The left column contains the framed program image/overview and numbered application steps. The right column contains a charcoal eligibility/action card, a separate schedule/capacity card, and Help Desk guidance. Mobile stacks the cards without internal scrolling.

Existing uploaded artwork/initials fallback, overview text, eligibility types, registration/program dates, slots, optional amounts and correction deadlines are retained. Apply remains conditional on open availability; tracking keeps its existing feature flag and popup. Steps explain the existing membership verification/application flow and use reference/Help Desk guidance when tracking is disabled. No reference-image sample program data or green colors were introduced.

Removed the decorative search-icon circle from the catalog empty state. Empty-filter messages, Clear filters and Browse all programs remain available.

Changed `templates/programs/public_detail.html`, `templates/programs/public_catalog.html`, and added `static/css/public-program-detail.css`. Existing card-list sizing and other unfinished changes were preserved. No models, migrations or business-rule code changed.

Read-only Chrome validation passed at 1600, 1440, 1024, 768, 390 and 320px: correct card order, desktop two-column layout, mobile stacking, no horizontal overflow or clipped panel content. Also verified the apply link reaches the existing membership-check screen, ended programs omit the apply button, the tracking popup opens/closes, Help Desk navigation works, empty filtered results contain no search icon, and Browse all programs restores the listing. Keyboard focus, high contrast and 200% root text at 320px passed. No browser errors were observed. Desktop/mobile and empty-filter screenshots were visually inspected; `checks.json` records the results.

The identity-verified local website was restarted to load template changes after confirming that no certificate emails were in progress; MySQL remained running. `scripts/current_development.py check` and `git diff --check` passed. No application forms were submitted, program records edited, or emails sent during verification.
