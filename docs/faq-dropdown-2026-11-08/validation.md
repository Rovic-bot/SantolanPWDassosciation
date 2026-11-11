# FAQ dropdown — November 8, 2026

Resources & Help now starts with the FAQ cards collapsed inside a native disclosure. Clicking the heading or arrow reveals the existing five cards and swipe controls; clicking again hides them. The arrow and View/Hide questions label follow the open state. The public content editor opens the disclosure initially so its text remains available for editing.

All FAQ copy, editable content fields and carousel controls are retained. The existing `#faq` bookmark reveals the dropdown. Printing opens the FAQ temporarily and restores its prior state afterward. No records, permissions, application rules or database schema changed.

Read-only Chrome checks passed at 1730, 1024, 768, 390 and 320 pixels: initially collapsed, Enter/Space and pointer toggling, all five cards reachable, closing/reopening, no horizontal overflow, bookmark reveal, printing/restoration and no-JavaScript disclosure with all five cards. No browser JavaScript errors occurred. JavaScript syntax and `git diff --check` passed. The retained local server was refreshed.

- [Desktop collapsed](collapsed-1730.png)
- [Desktop expanded](expanded-1730.png)
- [Mobile collapsed](collapsed-390.png)
- [Mobile expanded](expanded-390.png)
- [Browser results](checks.json)
