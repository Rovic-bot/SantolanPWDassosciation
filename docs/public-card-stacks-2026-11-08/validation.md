# Public card stacks - 8 November 2026

Applied the owner's Home carousel design to Mission and background, all 12 published annual observances, the five FAQ cards, and the seven Guides and resources cards. These sections use the existing charcoal, cream and warm-gray palette with a centered active card, angled previews, dots, arrow buttons and swipe/drag navigation.

The FAQ remains a native, initially collapsed View/Hide questions disclosure. Opening it measures the cards; closing and reopening preserves the selected question. Guides use a compact 320px reading width and 220px minimum height, growing only when the content or reading settings require it. Other sections retain enough room for their complete copy. Card switching keeps each stack's height stable.

The Home implementation was extracted to shared `static/css/public-card-stack.css`, `static/js/public-card-stack.js` and `templates/public/stack_controls.html`. The Home template now uses these shared assets; its Contact / Help Desk starting card and existing geometry are preserved. The superseded Home-only assets were removed. Template changes are limited to the public base, Home, About, observance cards and Resources index. Scheduled events retain their existing carousel.

All original text and action URLs were compared with a snapshot of the working page before this change. About keeps its existing Background/Mission grouping and safe plain-text CMS parsing. No business rules, models, publication filters, database records or application flows changed.

## Validation

- Passed 216 card/viewport combinations across the five stacks at 1920, 1440, 1024, 768, 390 and 320px. Full text fits, card changes preserve section height, and pages have no horizontal overflow.
- Every card is reachable through dots, arrows and keyboard navigation. Side-preview clicks, mouse dragging and native mobile touch swipes passed; vertical gestures still scroll the page. Inactive previews remain inert and hidden from assistive technology, and changes are announced.
- All 12 annual observance detail popups loaded their corresponding published content, closed with Escape and restored link focus. Dragging did not open a popup. Scheduled events still initialize their original carousel.
- FAQ pointer and Enter/Space toggling, initially collapsed state, selection retention, the FAQ bookmark and the final resource-card bookmark passed.
- Enlarged text at 200% on a 320px viewport, high contrast, reduced motion, complete printing and the no-JavaScript fallback passed. A legacy high-contrast token conflict was corrected and screen/print foreground and background colors were checked afterward. Printing restores the prior FAQ disclosure state.
- Local synthetic CMS checks confirmed that saved HTML-like text stays escaped and editing markers skip enhancement. No authenticated content-editor session or content save was performed.
- Desktop and mobile screenshots were visually inspected. No browser JavaScript errors occurred. Django's retained-development system/database check, JavaScript syntax and `git diff --check` passed.

The retained development web process was refreshed after verifying its identity and checking that no certificate or membership email was being sent. MySQL stayed running. Browser checks were read-only; no forms were submitted or messages sent.

Evidence: [check results](checks.json), [Mission and background](about-0-1440.png), [annual observances](events-0-1440.png), [FAQ expanded](resources-0-1440.png), [FAQ collapsed](faq-collapsed-1440.png), [compact guides](resources-1-1440.png), and [mobile guides](resources-1-390.png).
