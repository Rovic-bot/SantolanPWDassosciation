# Announcement banner popup — November 9, 2026

Applied the owner's announcement reference to public notice dialogs: a wide rounded image banner, dark fade, category pill, announcement label, prominent bottom-aligned title, publication date/content and an “Explore More” action. Published artwork uses the existing permission-checked image route. Missing or failed images show a gradient. Full notice text wraps without truncation, and longer dialogs scroll while keeping the close control reachable.

The action retains the existing program or official Results destination when present; general announcements open their full details page. Existing server-projected participation content remains below the banner. Full-page routes, publication rules, privacy projections and records are unchanged. Event and observance popups retain their own layouts.

Validation:

- `node scripts/public_announcement_poster_qa.cjs` passed eight light/dark combinations at 1440, 768, 390 and 320px. Checked visible content/action, colors, no horizontal overflow, Tab containment, Escape, button/backdrop dismissal and focus restoration.
- High contrast, forced-colors smoke checks, long content at 200% text, missing/failed images, actual destination navigation, unavailable notices and no-JavaScript navigation passed. Synthetic cases were intercepted in the browser without saving records. No browser JavaScript errors.
- `node scripts/public_event_poster_qa.cjs` passed all existing event popup browser checks after the shared dialog loader update.
- Two focused Django tests passed using fresh disposable native MySQL: `core.tests.test_public_browsing.PublicBrowsingTests.test_announcement_fragment_escapes_copy_and_withholds_nonpublic_records` and `announcements.test_public_results.PublicResultsTests.test_result_details_keep_projection_while_notice_only_links_to_results`. Application data was excluded.
- Desktop and mobile screenshots were visually inspected. A separate fade behind the bottom content protects text readability over bright images and longer text. JavaScript syntax and `git diff --check` passed.

Evidence: [results](results.json), [banner](card-light.png), [mobile](light-390.png), [high contrast](contrast-320.png).

No database writes, migrations, publication changes or new business rules were introduced. The retained local server was restarted to load the updated template and stylesheet references.
