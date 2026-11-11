# Results listing removal — November 9, 2026

The owner requested removal of the “Looking for program results?” announcement sidebar and the separate `/results/` page.

## Implemented scope

- Removed the callout and its sidebar allocation. Announcements retain one swipeable row, up to four desktop cards, arrows, dots, keyboard controls, and mobile swiping.
- Removed the `/results/` listing route, view, and template. The URL now returns 404.
- Repointed footer, receipt, workflow, tracking guidance, and result-detail return links to `/announcements/?category=results`.
- Removed the retired listing and callout fields from the public portal editor. Existing saved content and revision history were not deleted.
- Preserved authorized individual result pages at `/results/<uuid>/`, accessible through their announcements, along with the existing masking, publication checks, administrative workflow, and stored records. No database migration or application-data deletion was performed.

This request supersedes earlier validation that expected the standalone Results listing. Historical browser scripts and earlier evidence may still refer to that retired page.

## Validation

- Django configuration check passed against the retained development database.
- Browser navigation checked all seven public sections: HTTP 200 and no links to `/results/`. The removed URL returned 404; the footer opened the Program Results announcement filter; a published result popup and its authorized detail remained accessible. See `navigation.json`.
- Responsive carousel checks passed at 1920, 1440, 992, 768, 390, and 320 pixels, including all 31 browser-only sample notices, server-batch navigation, touch/mouse swipes, keyboard navigation, filters/history, enlarged text, print, and no-JavaScript fallback. No fixture records were inserted into the development database. See `results.json`.
- Inspected desktop and mobile screenshots: `announcements-1440.png` and `announcements-390.png`.
- All 26 focused Django checks passed across the initial run and targeted rerun: public result visibility/masking, announcements, the result catalog, portal editor, Resources links, receipt guidance, and tracking shortcuts. The initial run passed 24 checks; an old callout assertion was updated and the Resources check was rerun using its required `scripts.added_targets_phase1_test_runner.PhaseOneTestRunner`. Both remaining checks passed. Temporary run directories: `santolan-g12-tests-h2vryu0a` and `santolan-g12-tests-d03lqok2`.
- `git diff --check` passed.

Focused database checks use fresh, disposable native MySQL through `scripts/g12_test_runner.py`; the retained development data is never the test target.
