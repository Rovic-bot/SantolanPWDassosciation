# Chart card surfaces and public card scrolling — November 8, 2026

The owner confirmed that Membership growth and Membership breakdown should use the colors of the other dashboard charts. They now inherit the shared chart-card background, border, shadow and theme text colors. The compact layout, chart data, individual series colors and responsive column proportions remain in place. This supersedes the separate flat surface described in `../dashboard-top-charts-2026-11-08/validation.md`.

The owner identified two scrolling sections: Guidance and support on Home, and Guides and resources in Resources & Help. These sections now have a continuous horizontal scroll row, hidden native scrollbars and a short scrolling hint when content overflows. The previous paging arrows are removed from these two sections. Mouse-wheel movement, horizontal trackpad input, native touch scrolling, keyboard arrows/Home/End, focus and direct anchors can reach every card. Mouse-wheel movement at a row boundary can continue scrolling the page. Cards are kept in document flow and are not hidden or made inert when offscreen. The visual editor and no-JavaScript fallback retain their ordinary grid. Print uses the complete stacked content.

Other swipe sections, including the FAQ dropdown, retain their existing behavior. Shared asset versions were updated and the retained local development server restarted after confirming no membership or certificate email was in the sending state.

Validation:

- `node scripts/card_surface_scroll_qa.cjs` passed: Home and Resources at 1920, 1440, 768, 390 and 320 px; no page overflow or clipped card text; hidden scrollbars; wheel and keyboard movement; final-card anchor and focus visibility; native mobile touch input; 200% text; print and no-JavaScript fallback. The FAQ still opens and initializes its existing carousel.
- Dashboard computed background, border, shadow and backdrop match the other chart cards in both dark and light themes at 1440 and 390 px. Dashboard screenshots use saved synthetic aggregate fixtures rendered through the current chart templates with database queries prohibited. They do not depict application records.
- The browser harness allowed same-origin GET requests only. No browser JavaScript errors occurred. Screenshots were visually inspected.
- `scripts/current_development.py check`, JavaScript syntax checks and `git diff --check` passed.

Results are in `results.json` and screenshots beside this document. The browser harness uses the local synthetic dashboard fixture at `.local/card-surface-scroll-20261108/dashboard.html`; that fixture was built from `.local/dashboard-charts-20261029/expected.json` and the current dashboard/chart template section. No migrations or business-rule changes were needed.
