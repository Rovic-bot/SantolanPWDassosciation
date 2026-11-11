# Independent Program Details panels — November 10, 2026

The owner requested that Program overview and the other panels fit their own content rather than inherit the height of the adjacent Publication panel.

Program Details now uses independent desktop columns: overview, schedule, and requirements on the left; publication and eligibility on the right. Each card keeps its natural height and a consistent gap to the next card. Opening the archive review no longer stretches the overview or leaves a large empty row beneath it. Eligibility retains an independently scrollable long list. The existing single-column visual order is preserved on mobile. The shared layout applies to the popup and full page.

Only presentation templates and CSS changed. Publication actions, permissions, validation, and saved records were not changed.

Validation used an unsaved fictional program rendered through the existing view under a database wrapper that rejects writes. Headless Chrome checked 16 combinations: full page/popup, light/dark, 1440/390 pixels, and closed/expanded publication controls. Opening the controls left the heights of overview, schedule, eligibility, and requirements unchanged. A long overview also left Publication's height unchanged. Desktop columns maintained a 16-pixel gap between their own cards; mobile order, non-overlap, and horizontal overflow checks passed. No browser errors or database writes occurred.

Screenshots were visually inspected. Application configuration and `git diff --check` passed. The retained local app was refreshed.

[Browser measurements](results.json) · [Dark popup](popup-dark-1440.png) · [Light full page](page-light-1440.png)
