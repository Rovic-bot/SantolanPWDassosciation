# Admin annual observances restored to a grid — 9 November 2026

At the owner's request, removed the Admin annual observance carousel and restored the regular quarter grid in both the Events workspace and the dedicated Annual observances page. The existing responsive styles show four columns on desktop, two on tablet and one on mobile. All four quarters remain visible in document flow without carousel controls, transformations or inert cards.

Removed the carousel-only CSS/JavaScript assets and their template includes. Retained the original 12 observance labels, recurrence/status text and editing/detail destinations, verified against the pre-carousel template. Public portal carousels and the event-card dark-mode fixes are unchanged.

Twelve read-only browser layouts passed across both Admin entry points, light/dark themes, and widths 1440, 768 and 390px. Confirmed the expected grid columns, all 12 visible record links, readable content, no page overflow, no carousel assets/controls, and retained Events filters. No browser JavaScript errors. Desktop screenshot visually inspected and `git diff --check` passed.

Refreshed only the identity-checked local web process after checking active deliveries; MySQL and saved application data were retained. No forms were submitted or database records edited.

Evidence: [checks](results.json), [dark desktop](quarters-dark-1440.png), [light desktop](quarters-light-1440.png), [dark mobile](quarters-dark-390.png).
