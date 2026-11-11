# Public swipe cards and event popups — 2026-11-08

Implemented the owner's requested public portal changes. The existing seven-section navigation, publication rules, member verification and private assistance workflow remain in place.

## Behavior

- Mission and background uses a 320px card viewport. Home guidance, Resources FAQs and resource guides use the same swipe component. Card changes do not resize the deck; longer copy scrolls inside its card.
- Previous/next controls, left/right keys, Home/End keys and touch gestures work. Forward navigation moves the outgoing card left. Hidden cards are inert, the current position is announced, and reduced motion is respected. Text remains available with JavaScript disabled and when printing.
- Home guidance no longer opens dialogs. Existing privacy, EWAF, FAQ and accessibility bookmarks reveal the corresponding card.
- Contact / Help Desk and the Home support action navigate to `/resources/#referral-support`. The old `/#contact` bookmark also forwards there. `/assistance/referrals/` redirects there instead of serving the retired guidance page. “Read the guidance first” is removed; verification and submission routes remain available through “Send a concern.”
- Scheduled events use a responsive three/two/one-column grid. Clicking a card opens event details in a native dialog with keyboard close, focus restoration and a full-page fallback. The fragment uses the existing publication-checked event lookup, including cancellation notices. Withdrawn, archived and future-publication events remain unavailable.
- Announcement categories are All, Announcements and Program Results. Announcements combines general and published program notices. Legacy general/programs category URLs map to that combined view. Current authorized result projections and safe search behavior remain authoritative.
- The Programs requirements card no longer contains “Search and filter programs.” Existing program availability tabs remain.

## Verification

- `scripts/current_development.py check`: no issues.
- JavaScript syntax checks: passed for the shared swipe component, public navigation helpers and event dialogs.
- 26 focused Django tests: passed in a fresh disposable native MySQL instance, with `.env` disabled and isolated test database grants. Included notice filtering and search, authorized result separation, content escaping, public routing/method restrictions, event fragment publication gates and the assistance entry point.
- `node scripts/public_swipe_updates_qa.cjs`: passed 100 card/viewport checks at 1440, 768, 390 and 320 pixels. Also passed real Chrome touch swipes, vertical text scrolling, keyboard controls, fixed deck heights, no horizontal overflow, bookmark handling, Help Desk redirects, popup close/focus, simulated withdrawn-event response, reduced motion, print and no-JavaScript fallbacks. No browser JavaScript errors.
- Touch verification caught and corrected horizontal gesture cancellation caused by the new inner scroll containers: both the card and its viewport now specify vertical native panning with pinch zoom.
- `git diff --check`: passed.
- Desktop and mobile screenshots were inspected. Artifacts and detailed browser results are in this directory. The updated browser harness is the acceptance check for this request; earlier home-dialog checks describe the superseded popup design.

The local development server was restarted on port 8013. Browser checks were read-only. No application records, uploads, business rules, scores, or database schema were changed for this request.

Focused test command:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test announcements.test_public_board announcements.test_public_results.PublicResultsTests.test_result_details_keep_projection_while_notice_only_links_to_results core.tests.test_public_portal core.tests.test_content events.test_public_popup assistance.test_referrals.ReferralTests.test_public_guidance_home_and_staff_navigation --noinput
```
