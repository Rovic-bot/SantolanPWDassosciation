# Dashboard card packing — November 8, 2026

The owner requested tighter card spacing and widths/heights that use available screen space. The dashboard now uses the available workspace width, responsive card columns, smaller internal spacing and natural chart heights. A page-scoped layout helper places cards in available grid space beneath shorter cards. Wider charts occupy up to two columns. The document order is preserved; the visual grid can fill earlier gaps with later cards.

Chart SVGs retain their plotted area and labels while unused space below the content is trimmed. The existing five-row stacked-chart viewport remains controlled by its renderer. No counts, percentages, queries, permissions or source data changed.

Read-only verification used the synthetic dashboard HTML from the isolated analytics fixture and the current static assets:

- 2560, 1920, 1440, 1024, 768, 390 and 320 px layouts: all 12 cards present, no overlapping cards, clipped SVG labels, render fallbacks or page overflow. Observed four columns at 2560, three at 1920, two at 1440/1024, and one at smaller widths.
- The 1920 px packed chart grid measured 2002 px high, compared with 2173 px for regular rows using the same card sizes. Short cards begin immediately beneath the preceding card in their column, with a 12–13 px gap.
- All chart-data dialogs opened and closed. Resizing, 200% text, high contrast and returning to normal text preserved the layout.
- Without JavaScript, the normal grid and all 12 data tables remain available.
- The existing disability-chart browser checks passed for both themes, all recorded sample types, overlapping classifications, tiny segments, empty/single-category data, enlarged text and forced colors.
- Django system check, JavaScript syntax checks and `git diff --check` passed. Desktop/mobile screenshots were visually inspected.

`results.json` contains measurements; `dashboard-1920.png`, `dashboard-1440.png` and `dashboard-390.png` show synthetic content. The development server was restarted to load the versioned dashboard assets. No application records or schema were modified.
