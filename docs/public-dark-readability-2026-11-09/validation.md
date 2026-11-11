# Public dark-mode readability — 9 November 2026

Owner request: make text readable throughout the public portal in dark mode.

## Changes

- Program image fallbacks use a dark neutral gradient behind cream initials. The previous gradient became pale when dark-mode tokens changed, leaving initials below 3:1 contrast.
- Popup badges now receive the same paired foreground/background as page badges, including the application tracking label.
- Loaded assistance forms use readable muted hints, dark alert surfaces, pale red validation errors, and matching file-picker labels. These forms are inserted into Resources without the standalone resident-page stylesheet.
- QR images retain white backing and dark alternative text if an image fails to load.
- When high contrast is enabled alongside dark mode, program fallback artwork and tracking panels use light surfaces; the announcement text gradient is removed to keep black text visible.
- Updated shared stylesheet cache versions. No workflow, data, route, or permission changes.

## Verification

Chrome/Playwright checked rendered text against sampled background pixels, including gradients. Targets: 4.5:1 for ordinary text and 3:1 for large text. Hidden/occluded image fallbacks and lines clipped at a scrollport edge are excluded; scrollable form states are sampled at successive positions. This is a focused visual contrast check, not a complete accessibility certification or a check of text embedded in uploaded images.

Final checks in `checks.json`:

| Coverage | Checks | Text runs | Contrast failures |
| --- | ---: | ---: | ---: |
| Public pages, detail pages, popups, display controls; 1440/390px | 118 | 4259 | 0 |
| Synthetic form/receipt/error states and hover/focus controls; 1440/390px | 209 | 1534 | 0 |
| Resource popups and loading errors at largest text; 320px | 5 | 72 | 0 |
| Programs, announcements and resource popups with high contrast; 390px | 8 | 254 | 0 |

Public coverage includes Home, About, Announcements, Events, Programs, Membership, Resources, Contact, information pages, Association/PDAO registration, tracking, assistance verification, annual observances, published detail pages and official result details. The removed `/results/` list remains removed.

Eleven fictional template states cover private receipt layouts, tracking progress, published result tables, and validation messages without submitting real forms. The renderer allows only read queries; browser checks block non-GET/HEAD requests. Final runs recorded no attempted POSTs or browser errors. The assistance error form was also mounted in the actual Resources popup to exercise its different style context.

The light-mode review found existing low-contrast labels on Home/program guidance; the changes in this task are scoped to dark/high-contrast selectors and leave light-mode styling unchanged.

`scripts/current_development.py check`, Python/JavaScript syntax checks, and `git diff --check` passed. No model changes or migrations. Existing work remains preserved.

## Repeat

From the repository root with the retained local website running:

```powershell
.venv/Scripts/python.exe scripts/public_dark_contrast_fixtures.py
$env:QA_ASSERT='1'
node scripts/public_dark_contrast_qa.cjs
$env:QA_PATHS='["/resources/"]'
$env:QA_FIXTURES='.local/public-dark-contrast-20261109/fixtures'
$env:QA_INTERACTIONS='1'
node scripts/public_dark_contrast_qa.cjs
```

`QA_WIDTHS` selects viewport widths. `QA_PREFERENCES` accepts display settings such as `{"text":"largest"}` or `{"contrast":true}`. Full diagnostic output stays in `.local/public-dark-contrast-20261109`; representative screenshots accompany this note.
