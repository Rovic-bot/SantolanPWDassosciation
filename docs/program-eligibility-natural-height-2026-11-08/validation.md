# Content-sized eligibility cards — 8 November 2026

Updated the owner's follow-up: short eligibility lists now use their natural content height. The overview height is a maximum, not a required height. Longer lists still scroll inside the capped card with the heading/actions visible. The existing minimum for readable heading/actions and one full item remains for enlarged text. Print has no height cap.

Changed `static/css/public-program-detail.css`, its cache version in `templates/programs/public_detail.html`, and the descriptive comment in `static/js/public-program-detail.js`. No business rules, models or data changed.

Chrome checks passed across 1600, 1440, 1024, 768, 390 and 320px. Long lists remain capped at the overview with all ten types reachable by keyboard; action buttons stay stationary. A one-type card at 320px measured 236px tall versus the 358px overview, with no unnecessary scrollbar/tab stop. A longer overview does not stretch the eligibility card. Enlarged text, complete printed lists and no-JavaScript fallback passed; no browser errors or page overflow. Desktop short-list screenshot visually inspected. JavaScript syntax and `git diff --check` passed.

The existing development web process was refreshed after its identity and email-in-progress checks; MySQL remained running. No forms were submitted or program records edited.
