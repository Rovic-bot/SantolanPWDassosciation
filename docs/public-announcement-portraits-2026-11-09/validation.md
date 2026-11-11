# Portrait announcement cards — November 9, 2026

Applied the owner's card reference: rounded portrait cards with published announcement artwork, a title-initials fallback, category/latest badge and icon, bottom-aligned title/excerpt, compact date and “Read more” footer. The cards retain the Home page's cream/stone/charcoal palette and open the existing announcement popup.

The existing responsive carousel still allows one to four columns and up to two rows. Its minimum card width is now 220px so four cards fit at the checked 1440px desktop viewport. Heights remain content-measured for longer titles and larger text. The 24-notice server batches, filters, history, popup publication checks and full notice content are unchanged.

Images use the existing published-announcement image route and public projection. No private path or new image disclosure was introduced. General notices show their authorized image when present; notices without a public image show initials derived from the displayed title. Failed images also reveal initials, including after filtering replaces the cards.

Validation:

- Eight Django tests passed in fresh disposable native MySQL: `announcements.test_public_board` plus the announcement fragment publication/escaping regression. Updated the existing expected action wording from “Read announcement” to “Read more.” No application records were used by the test runner.
- `QA_OUTPUT=docs/public-announcement-portraits-2026-11-09 node scripts/public_announcement_grid_qa.cjs` passed at 1920, 1440, 992, 768, 390 and 320px. Browser-only 31-notice fixtures verified both batch-navigation directions, all notices reachable, keyboard, mouse/touch swipes, filters/history, popup focus return, 200% text, printing and no-JavaScript rendering.
- `node scripts/public_announcement_portraits_qa.cjs` passed ten light/dark combinations from 1920 to 320px, plus loaded images, initials, failed-image fallback, fallback after filtering, high contrast, forced-colors smoke checks and popup-only general-announcement reading.
- Inspected light/dark desktop and mobile screenshots. Corrected footer layering and inline calendar/date alignment during visual review. No browser JavaScript errors. JavaScript syntax and `git diff --check` passed.

Evidence: [carousel results](results.json), [image/theme results](image-theme-results.json), [desktop dark](portraits-dark-1440.png), [desktop light](portraits-light-1440.png), [failed image fallback](failed-image-initials.png).

No business rules, database records, schemas or publication permissions changed.
