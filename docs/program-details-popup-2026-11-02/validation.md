# Program Details popup — November 2, 2026

Opening a program from the portfolio (title, Open program, or draft shortcut) or Applications & Eligibility (Open program details) now displays the existing protected Program Details view in a native modal dialog.

- Shared light/dark glass styles, a pinned close toolbar, internal scrolling, and responsive layout.
- Close button, Escape, backdrop dismissal, keyboard focus containment, and return focus. Background scrolling is locked while open.
- Current list URL and filters remain in place. History pagination loads inside the popup with the correct program URL.
- Existing publication/status forms submit to their original protected view and render results/errors in the popup. The underlying list refreshes afterward. Writes are never retried automatically.
- Edit, proposal download, and applicant-review links retain their existing destinations. Open full page and native links provide a fallback.
- No new API, dependency, database schema, or business rule was added. Public pages and removed lifecycle/readiness/EWAF sections remain unchanged.

## Verification

- **23 focused Django tests passed** (`programs.test_detail_workspace`, `programs.test_portfolio`, `programs.test_review_workspace`).
- Existing browser harness passed **14 standalone layouts and 12 popup layouts** across dark/light themes and 320–1600 px widths.
- Both popup entry points, filter/URL preservation, history pagination, focus containment/restoration, Escape, backdrop, failed-load retry, aborted loads, and no-JavaScript fallback passed.
- Real publication, reasoned withdrawal, underlying-card refresh, and blocked EWAF publication were exercised only on synthetic records in a disposable MySQL instance. No JavaScript errors remained.
- Browser testing caught and corrected tab traversal into collapsed sections and the named `action` control shadowing a form's URL property.
- Retained workspaces rendered read-only with the popup. System/database checks, JavaScript syntax checks, and `git diff --check` passed.
- Production asset collection passed: **207 files** to `.local/program-dialog-static-build`.

Final browser artifacts: `santolan-g12-tests-4zu2o4wj/program-detail-browser`. Focused Django checks: `santolan-g12-tests-fvld7c9o` (23 passed; the initial browser run identified the focus issue before the final successful run).

## Files changed

- `templates/programs/portfolio/{base,card,operations}.html`
- `templates/programs/application_workspace/{page,selected}.html`
- `templates/programs/profile/{dialog,dialog_styles,dialog_scripts}.html` (new shared popup)
- `templates/programs/manage_detail.html` (asset versions)
- `static/css/{program-detail,program-dialog}.css`
- `static/js/{program-detail,program-dialog,program-portfolio,application-workspace}.js`
- `programs/test_detail_workspace.py`
- `scripts/program_detail_browser_qa.py`, `scripts/program_detail_browser_qa.cjs`
- This validation directory.

[Dark popup](program-dialog-dark-1600.png) · [Light popup](program-dialog-light-1600.png) · [Mobile popup](program-dialog-dark-390.png) · [Applications popup](program-dialog-applications.png) · [Browser results](results.json)

## Follow-up: remove summary cards

Removed the shared metrics include from `templates/programs/manage_detail.html`: Capacity and slot usage, Applicants, Registration window, Program delivery, and their time-zone note no longer appear in either the full detail page or popup. Updated existing expectations in `programs/test_detail_workspace.py` and `scripts/program_detail_browser_qa.cjs`. No stored data or other pages changed.

All seven focused tests plus the existing browser harness passed (14 page layouts and 12 popup layouts). Fourteen retained profiles rendered read-only without the removed section. System checks, syntax checks, `git diff --check`, and static collection passed (207 unchanged assets). Final follow-up browser artifacts: `santolan-g12-tests-xvng6u23/program-detail-browser`.

[Popup after summary removal](program-dialog-summary-removed.png)

## Follow-up: compact overview and publication row

Reduced the popup maximum width from 1360 to 1120 pixels. Program overview and publication controls now share the first row; Eligibility profile, Requirements and evidence, and Program history span the full width below. Smaller screens stack the publication controls immediately after the overview. The full-page fallback uses the same section order. Removed the unused sticky-rail height observer; existing forms, permissions, data, and publication guards are unchanged.

Changed `templates/programs/manage_detail.html`, the profile partials `overview.html` (new), `configuration.html`, `dialog_styles.html`, and `dialog_scripts.html`; `static/css/program-detail.css`, `static/css/program-dialog.css`, `static/js/program-detail.js`; and the existing `scripts/program_detail_browser_qa.cjs` layout checks.

All seven focused Django tests plus the browser harness passed. Browser checks covered 14 full-page and 12 popup layouts in both themes, including full-width lower sections, the narrower dialog, accessible publication controls, modal navigation, history, and protected publication/status submissions on disposable synthetic records. Screenshots were visually inspected. System checks, JavaScript syntax checks, and whitespace checks passed. Production static collection completed: three files copied, 204 unchanged. Artifacts: `santolan-g12-tests-5dsr1tie/program-detail-browser`.

[Compact dark popup](program-dialog-compact-dark.png) · [Compact light popup](program-dialog-compact-light.png) · [Mobile layout](program-dialog-compact-mobile.png)
