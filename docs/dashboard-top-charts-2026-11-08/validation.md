# Top dashboard charts — November 8, 2026

The two leading cards now match the owner's focused reference: flat dark surfaces with subtle borders, a blue growth area with dashed grid lines and a smooth curve, and a smaller Membership breakdown doughnut with colored dots, counts and percentages in a compact legend. The duplicate breakdown headline is removed; its member count remains in the center. Its explanatory footer has a divider and a working View data button. Light, high-contrast and forced-color modes remain supported.

Long legend labels use ellipses in the compact view, with the complete name in an SVG title and the accessible data table. Enlarged text switches the legend to wrapping names and separate amounts to prevent overlap. Every recorded category remains rendered. Ring segments still use classification counts; percentages still use current-member totals. The explanatory footer retains the overlap qualification.

The growth curve uses monotone cubic interpolation through recorded points, with no change to stored values or displayed totals. Flat intervals remain flat, and cumulative growth does not overshoot or decrease between samples. A single recorded point remains visible.

Validation used current Django chart templates rendered from saved synthetic aggregates, without database access:

- Responsive layout checked at 1920, 1440, 1024, 768, 390 and 320 px; all cards remain available, no clipped SVG text or page overflow, and the data dialog works.
- Disability chart cases passed both themes, all seven sample categories, all ten catalog types plus missing classification, overlapping classifications, tiny segments, single/empty data, 200% text, high contrast, forced colors and no-JavaScript table fallback. Legend names and values do not overlap.
- Growth curve checks passed for cumulative data, flat months, all-zero values and one point; source values remain unchanged.
- Django system check, JavaScript syntax and `git diff --check` passed. Desktop and mobile screenshots were visually inspected.

No application records, source queries, membership rules or program-completion behavior changed. The development server was restarted with versioned assets. Screenshots and JSON files contain synthetic data.
