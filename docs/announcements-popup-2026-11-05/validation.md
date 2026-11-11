# Announcements popup and program list — November 5, 2026

The owner requested a smaller popup with a visible X and no programs without applicants on `/announcements/manage/`.

## Changes

- The results preview is capped at **880px**, reduced from 1,180px, and at 82% of the viewport height (760px maximum). Phones retain surrounding space instead of switching to a full-screen dialog. Long lists scroll inside the popup; the header and publication actions stay visible.
- The header now has an explicit SVG X in a 44×44px button, using the current theme colors and the existing accessible close label. Existing Close, Escape, focus handling and publication forms are retained.
- `announcements/catalog.py` now requires an existing `ProgramApplication` before shared search, sorting, counting and pagination run. Any recorded applicant counts, regardless of review/decision status or program status. Resetting filters or changing `with_applications` cannot reintroduce empty programs.
- The Announcements filters show a static “Programs with applicants” note instead of an optional checkbox. The shared filter keeps the checkbox for other program lists.

This changes the private chooser and presentation only. Existing program records, application decisions, publication history, public visibility gates, permissions, source/version checks and explicit publication actions remain intact. No migration or live publication was performed. Unfinished Git work was preserved, with the five affected source files copied to ignored `.local/announcements-popup-20261105/before/` first.

## Validation

**23 focused tests passed** in fresh disposable native MySQL through `scripts/g12_test_runner.py` (19.043 seconds excluding database setup):

- New catalog tests cover excluding more than a page of empty programs before pagination, multiple applicants without duplicate cards, all three chooser routes, search, filter reset/query parameters, and pending/ineligible/closed applicants in draft/published/cancelled programs.
- Existing recorded-result and generation tests cover private/public projections, explicit publication, CSRF, permissions, stale data and rollback. Existing notice-editor access and combined filter/status tests also passed.
- Django system check and targeted Git whitespace checks passed. Updated assets were collected and the retained local server restarted.

Native Brave checks on the owner's current session confirmed:

- The list changed from **14 to 10 programs**, hiding the four cards with zero applicants.
- The X closes the popup and returns to the filtered grid. Escape also dismisses it.
- The desktop popup leaves visible surrounding space. At 390px and 320px CSS widths the X and footer actions remain reachable, and the long applicant list scrolls within the popup.
- Only the existing **fictional HM Focus demo** was used for preview screenshots. No Publish results action was clicked.

[Desktop screenshot](popup-desktop.png) · [320px screenshot](popup-320.png) · [Check summary](checks.json)

Screenshots were captured using Brave DevTools and visually inspected. These focused checks do not claim a complete accessibility certification or a production deployment.
