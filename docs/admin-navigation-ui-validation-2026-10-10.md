# Admin navigation presentation refinement — 2026-10-10

**Implemented and locally validated: frontend presentation only.** The owner-defined **70% milestone remains unchanged**. Authority: [UI design guide](../../UI_Design_Guide_For_Codex.md), [Admin Portal V2](../../00%20-%20Project%20Overview/Admin%20Portal.md) and the existing [Phase 2 validation](phase2-admin-navigation-validation-2026-10-10.md).

## Presentation and scope

The existing 252px desktop sidebar now uses a warm white surface, ink text, restrained teal selection/focus, 18px outline icons, small disclosure chevrons and subtle submenu guide lines. Branding and account controls use the existing font system consistently on custom and native Admin pages. Comfortable 44px minimum navigation targets and the existing 48px mobile menu remain. No new animation, dependency, navigation state system or desktop collapse mechanism was introduced.

The exact eight-module order is preserved: Dashboard; Members; Programs & Events; Applications & Verification; EWAF & Selection; Announcements & CMS; Reports & Exports; Administration. Existing links, native details semantics, active/current attributes, permission projection, mobile collapse/Escape/focus return, expansion persistence and independent scroll restoration are reused unchanged. Restricted staff still see only their permitted destinations, and direct URL permissions remain enforced. EWAF and Reports remain honestly unavailable where previously unavailable.

## Files changed in this task

- [templates/partials/workspace_header.html](../templates/partials/workspace_header.html): decorative icons/chevrons replace module numbers; labels, links, authorization and state attributes retained.
- [templates/partials/workspace_icon.html](../templates/partials/workspace_icon.html): new small outline SVG partial; icons are hidden from assistive technology and excluded from focus.
- [static/css/admin.css](../static/css/admin.css): scoped sidebar presentation, responsive branding, high contrast and forced-colors active indicators; page/dashboard styling retained.
- [scripts/admin_navigation_browser_qa.cjs](../scripts/admin_navigation_browser_qa.cjs): responsive before/after captures, rendered contrast/icon/target checks, forced-colors and console checks added to existing behavioral tests. Defaults to the after checks; `QA_VISUAL_STAGE=before` captures a baseline without asserting the new appearance.
- This validation note.

No application Python, permission/navigation service, URL, model, migration, runtime JavaScript, public template or membership component changed. No development progress percentage or vault requirement note was modified.

## Commands and actual results

Executed from the repository with its existing virtual environment:

```powershell
$env:QA_VISUAL_STAGE = 'before'
.\.venv\Scripts\python.exe manage.py test scripts.admin_navigation_browser_qa --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test core.tests.test_workspace_navigation core.tests.test_public_portal announcements.test_results announcements.test_public_results membership.test_confirmed_requirements programs.test_public_receipt --noinput --verbosity 1
$env:QA_VISUAL_STAGE = 'after'
.\.venv\Scripts\python.exe manage.py test scripts.admin_navigation_browser_qa --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test membership members documents core accounts programs announcements assistance events ewaf --noinput --verbosity 1
$env:NODE_PATH = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
.\.venv\Scripts\python.exe manage.py test scripts.admin_navigation_browser_qa scripts.public_navigation_browser_qa scripts.announcements_members_browser_qa scripts.revised70_browser_qa scripts.membership_browser_qa --noinput --verbosity 1
node --check scripts/admin_navigation_browser_qa.cjs
git diff --check
git diff --stat
git status --short
```

Environment variables above were command-local in separate shell executions; the final browser run used the harness's default after stage.

- Fresh before browser baseline: **1/1 passed**.
- System check: **no issues**.
- Focused Django tests: **63/63 passed**, zero failures/skips.
- Affected-app regressions: **317/317 passed**, zero failures/skips. These include the focused cases; counts are not additive unique coverage.
- Dedicated after browser rerun: **1/1 passed**.
- Final combined Chrome run after the last responsive CSS adjustment: **5/5 passed**, zero failures/skips. The dedicated Admin workflow is included in these five, alongside public navigation, announcements/results, revised application workflow and membership.
- JavaScript syntax, final diff whitespace and task-file whitespace checks passed.

The first after browser run failed because the new harness requested the nonexistent text-size option `normal`. It was corrected to the existing `default` option and successfully rerun. No application behavior or acceptance requirement was weakened.

## Screenshots and accessibility

Fresh synthetic-data captures are retained locally in [before](../.local/qa-admin-navigation-ui/before/) and [after](../.local/qa-admin-navigation-ui/after/). Dashboard captures exist at **320, 390, 768, 1024 and 1440px**. Inspected the rendered final captures at all five widths, the [eight-module overview](../.local/qa-admin-navigation-ui/after/eight-module-overview.png), native document-type and sign-in pages, restricted-staff onsite intake, [320px Largest text/high contrast](../.local/qa-admin-navigation-ui/after/mobile-largest-viewport.png) and [forced-colors mode](../.local/qa-admin-navigation-ui/after/forced-colors.png). Original desktop/mobile/native captures were inspected before styling. Screenshots contain synthetic fixtures only and are ignored local artifacts.

Checks confirmed no document-level horizontal overflow at the five widths, consistent icons and font, working custom/native active states, 44px summary targets, usable navigation scrolling and retained layout offsets. Existing mobile disclosure is used below 1100px; the desktop sidebar remains 252px. Enter/Tab disclosure, visible 3px focus, Escape/focus restoration, collapsed-group persistence, current-module auto-expansion and desktop/mobile sidebar offsets passed. Native details and visible labels retain accessible semantics; decorative SVGs have `aria-hidden=true` and `focusable=false`.

Rendered sidebar text/background checks covered group headings, links, unavailable notices and account text in normal and high-contrast modes: minimum measured contrast **5.1749:1**. Largest text remains usable at 320px. Reduced-motion emulation and forced-colors active outlines were checked. Normal Admin operation reported **zero captured JavaScript errors and zero console errors**; intentional HTTP 403 denial messages are excluded from the console-error assertion. These local checks do not constitute assistive-technology certification or client UAT.

## Preservation, data and limitations

The final regressions cover Phase 2 navigation/RBAC and direct protected routes; Phase 1's seven public sections, authorized masked Results, announcement links and session-protected receipt; DEC-025 preparation/preview/privacy-confirmed publication and Members navigation; DEC-027 Association/PDAO separation, private document access, manual PRPWD review, approval safeguards and ordinary-staff intake. Application/photo review, eligibility, non-EWAF selection/release and existing CMS/history tests remain green.

A verified backup/hash manifest of **346 pre-existing nonignored repository files** was recorded before edits at the vault's `.local/admin-navigation-ui-20261010/`. Exactly three pre-existing files changed; the other **343 remain byte-identical**, none were deleted. The icon partial and this note are additive. Earlier tracked/untracked work is preserved. Final scope was assessed against this starting worktree, since the existing HEAD diff contains earlier unfinished work.

**Database schema changes: NONE. New migrations: NONE. Development database changes: NONE.** Tests created/destroyed only the distinct disposable test database and used temporary private media. No reset, clean, commit, push or branch change.

The previously documented native Django filter limitation remains: deliberate denial of all session storage produces one error in unchanged `admin/js/filters.js`. The browser test checks that specific error separately and verifies workspace navigation still works; normal storage operation is clean. It was not repaired in this frontend navigation scope.

Controlled EWAF, reports, future analytics and other gaps remain unimplemented. OQ-27 evidence-handling decisions remain open: displaying the confirmed membership requirements is **not full document-verification enforcement**. No policy, verification state, historical member record or approval condition was changed. No further implementation phase was started.
