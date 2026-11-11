# Public browsing and content editor validation — November 8, 2026

## Authorized scope and implemented behavior

This update implements the owner's public portal request for artwork, in-place browsing, popup details, responsive swipe cards, event alignment and editable home/help content. Existing unfinished work and the previously validated program lifecycle remain intact.

- Program list cards and details show the program image, or title initials when no image exists. Failed image loads also reveal the initials. Public images pass the existing public-program visibility gate; no unrestricted media route was added.
- Program pagination and public Programs, Announcements, Events and Results filters update their results region without navigating the document or jumping to the top. Links retain ordinary server-rendered destinations when JavaScript is unavailable. Browser Back restores the prior results and viewport; failed requests preserve the current contents.
- Announcement cards open a native dialog with published announcement content and its existing destination link. Full-page routes remain available as a fallback. Publication checks and the approved results projection apply to popup requests too.
- Scheduled event cards have image/initial artwork, aligned details and actions. Event and annual-observance details open dialogs with keyboard focus containment, Escape/backdrop dismissal and focus restoration.
- Annual observances use the shared swipe cards. The visible annual-observance heading/intro block was removed. The Programs verification-and-selection disclosure and its included content were removed from the catalogue.
- Shared swipe sections display as many cards as fit at a minimum usable width of 300 px, with a fixed 320 px card area. Next/previous, keyboard and touch gestures reveal the next group. Long text scrolls inside each card. The editor, no-JavaScript rendering and print retain access to all cards.
- Content Management → Home edits the background image, Guidance and support heading, and guidance card titles/body text. Content Management → Resources & Help edits FAQ questions/answers, including each application description, plus resource card titles/summaries. Existing draft, publish, permission, escaping and revision controls are reused.

No model/schema changes or database migration were needed for this update. This work does not change membership verification, eligibility, ranking, selection, result disclosure or private document access. The guidance text defaults retain their existing meaning.

## Backend and static verification

Using the isolated disposable MySQL runner (`scripts/g12_test_runner.py`), with `.env` disabled and application data excluded:

- 16 tests passed: `core.tests.test_public_browsing`, `core.tests.test_portal_editor`, the announcement result-projection popup regression, and `events.test_public_popup`.
- 15 additional regressions passed: `announcements.test_public_board`, `programs.test_public_catalog`, the observance public-preview permission check, and the annual-calendar publication/history check.
- The nine content-editor tests were rerun after wiring the remaining four FAQ descriptions and passed.

Coverage includes program image visibility for published/draft/archived/future programs; safe request methods; popup publication gates; escaped content; private drafts; CMS authorization/CSRF; stale saves; image replacement; retained revisions and audit-failure rollback.

`scripts/current_development.py check`, JavaScript syntax checks and `git diff --check` passed. The development server was restarted to load the current templates and field registry at `http://127.0.0.1:8013/`.

## Browser verification

Chrome/Playwright harness: `scripts/public_browsing_qa.cjs`. Machine-readable evidence and screenshots are in this directory.

- Six public pages checked at widths 1440, 768, 390 and 320 px, without horizontal page overflow.
- Twenty swipe-layout combinations checked for responsive card count, fixed height and navigation.
- Program pagination, filters, announcement search/empty results, browser Back and network-failure recovery checked for no document reload and viewport movement under 2 px.
- Announcement, event and observance dialogs checked for content, stable page URL, keyboard focus, Escape and focus return after closing.
- Real Chrome touch events verified Home and Events swipe gestures.
- Admin image control opened, a local image preview was applied and discarded, and the saved CMS state was confirmed unchanged. Guidance/resource fields and all four FAQ descriptions were verified editable.
- No-JavaScript and print views expose every resource card. No browser script errors were observed.

Browser checks did not save or publish demonstration content. Image publication/replacement is covered with synthetic uploads in the isolated backend tests.

This validation supersedes earlier single-visible-card and announcement full-page UI expectations. Earlier validation records remain as historical evidence.
