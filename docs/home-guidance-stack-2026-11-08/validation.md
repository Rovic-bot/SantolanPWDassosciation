# Home guidance carousel - 8 November 2026

Implemented the owner's stacked-card reference for the Home page's Guidance and support section using the existing charcoal, cream and warm-gray palette. Contact / Help Desk starts in the center, with smaller angled previews behind it. Arrows, indicator dots, clicking the exposed previews, horizontal drag/swipe, and Left/Right/Home/End keys select cards. There is no automatic rotation.

The change is scoped to `templates/public/home.html`, `static/css/home-guidance-stack.css` and `static/js/home-guidance-stack.js`. Existing guidance copy, CMS fields, card anchors and Help Desk destinations remain intact. The hero and other pages' shared scrolling cards are unchanged by this work. No models, database records, business rules or application gates changed.

Every card is measured at the active reading width. The stack uses the tallest required height so full content remains available without internal text scrollbars or height changes between cards. Inactive previews are inert and hidden from assistive technology; navigation announces the selected card. Reduced motion and enlarged text are supported. Print and JavaScript-disabled layouts expose all cards. Enhancement is skipped when CMS editing markers are present; an authenticated editor session was not exercised.

## Validation

Read-only Chrome checks passed for all six cards at 1920, 1440, 1024, 768, 390 and 320px (36 card/viewport cases). All active text fits, page width does not overflow, content is preserved and the section height remains stable between cards. Only the selected card is exposed to keyboard focus and assistive technology.

Arrows and wrap-around, dot state, keyboard controls, preview clicks, mouse drag, and native touch swipes passed. Dragging does not activate links. The Privacy bookmark reveals its card; the existing Contact bookmark and Help Desk links still reach Resources referral support. The Resources scrolling row remains functional. Enlarged text at 200% on a 320px viewport, high contrast, reduced motion, print and no-JavaScript layouts passed. No browser JavaScript errors were recorded.

`node --check static/js/home-guidance-stack.js`, `.venv\Scripts\python.exe scripts/current_development.py check`, and `git -c core.safecrlf=false diff --check` passed. Django reported no issues. Desktop and mobile screenshots were visually inspected.

Evidence: [browser results](checks.json), [desktop](home-1440.png), and [mobile](home-390.png).

The retained development web process was refreshed after verifying its identity and checking that no certificate email was in progress. MySQL remained running. No forms were submitted, messages sent or program records edited.
