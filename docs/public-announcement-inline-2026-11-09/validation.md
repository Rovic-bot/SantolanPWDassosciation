# Remove announcement full-page action — November 9, 2026

Removed “Explore More” and the announcement self-link from the popup. General announcements now use the full available text width, and their complete published content remains visible in the dialog. Related program/official Results destinations retain their explicit existing labels when applicable; they do not lead to a full-page announcement.

The current Home palette, artwork and publication checks are preserved. This change removes the popup's full-page action; it does not delete the existing legacy/no-JavaScript detail route.

`node scripts/public_announcement_poster_qa.cjs` passed eight light/dark checks at 1440, 768, 390 and 320px. Confirmed no “Explore More” or general-announcement action, full-width copy, no horizontal overflow, focus containment with only the close button, Escape and focus restoration. Existing contrast, long content at 200% text, image fallback, error recovery, backdrop and no-JavaScript checks passed. Desktop screenshot inspected; no browser JavaScript errors. `git diff --check` passed.

Evidence: [results](results.json), [desktop](card-light.png), [mobile](light-390.png). No database records or business logic changed.
