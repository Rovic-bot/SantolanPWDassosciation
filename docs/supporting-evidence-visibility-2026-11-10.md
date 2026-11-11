# Supporting evidence disclosure fix

The Community Assistance Desk upload briefly appeared, then disappeared after opening. Bootstrap replaced its transitional `collapsing` class with `collapse show`; Tailwind's `.collapse` utility then applied `visibility: collapse`. The field occupied space but could not be seen or used.

A narrowly scoped rule in `static/css/public-concern-dialog.css` keeps this disclosure visible while Bootstrap continues to control its open/closed display. The public stylesheet URL is versioned to refresh cached assets. This covers the popup, the direct form, and the no-JavaScript fallback without changing upload validation or submission behavior.

Verified with the existing empty server-rendered form in a private browser preview: repeated opening/closing; popup close/reopen; mobile; light/dark/high-contrast modes; native file-picker opening; and no-JavaScript fallback. No file was selected or uploaded, no concern was submitted, and no automated test suite or fixture was run. Browser inspection reported no JavaScript errors. Django/database system checks and `git diff --check` passed.
