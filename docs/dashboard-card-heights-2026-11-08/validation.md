# Dashboard chart card heights — November 8, 2026

The owner requested less empty space beneath Membership growth. Dashboard chart cards now align at the top of each grid row and size to their own content, rather than stretching to the tallest neighboring card. Chart rendering, the support-needs legend and data controls are unchanged. The dashboard stylesheet version was updated and the development server restarted.

Read-only browser checks used synthetic dashboard HTML at 1920, 1440, 768, 390 and 320 px. At 1440 px the growth card decreased from 576 to 442 px; space between its chart and View data decreased from 146 to 12 px. The support-needs chart retained all seven sample segments. Neither the growth plot nor the page overflowed. The data dialog still opens and closes. No JavaScript errors occurred.

Django system check and `git diff --check` passed. `desktop.png` was visually inspected; `results.json` records the measured comparisons. No application data, schema or business logic changed.
