# Admin Portal UI cleanup — 2026-10-10

Frontend presentation cleanup across the existing Admin workspace. The eight permission-aware modules, underlying routes and business workflows are preserved. The owner-defined **70% milestone is unchanged**.

## Root causes and fixes

1. The existing inline SVGs depended on external CSS for their dimensions, stroke and fill. With Admin styles withheld in Chrome, they rendered as oversized solid black geometric shapes. Module icons and disclosure chevrons now have explicit size, `fill="none"`, stroke and line attributes in the HTML. The fallback browser test confirms small outline icons even without Admin CSS. Stylesheet URLs also carry an updated version token. This reproduces a concrete failure mode; it does not establish that the owner's browser cache was the original trigger.
2. Native Django `admin/css/forms.css` applies dark fieldset styling to `:not(.inline-related) .collapse summary`. That selector also matched the workspace sidebar on native add/edit pages. Explicitly scoped navigation summary rules now prevent that collision without changing Django's files or form behavior.

Visual inspection also caught an overlapping native Add action after title sizing changed. The object-tools spacing was corrected, and browser assertions now protect the title/action separation.

## UI changes

The existing 252px sidebar and responsive disclosure remain. White surfaces, a soft neutral background, restrained teal accents, consistent outline icons and quieter headings replace inconsistent presentation. Existing active states retain weight, an accent indicator and `aria-current` semantics. The header displays current module context and keeps Public website access.

Admin pages share consistent buttons, inputs, filters, panels, status badges, table spacing and pagination. Dashboard destinations are compact work panels using existing actions and permissions; no analytics or statistics were added. Application/program choosers, photo review, CMS lists and the EWAF unavailable page use the same visual hierarchy. Native Administration lists/forms receive compatible styling. No runtime JavaScript or navigation state mechanism changed.

The module order remains Dashboard; Members; Programs & Events; Applications & Verification; EWAF & Selection; Announcements & CMS; Reports & Exports; Administration. Permission projection and backend checks remain authoritative. Unavailable functionality remains unavailable.

## Complete task file list

Modified existing files:

- [templates/admin/base_site.html](../templates/admin/base_site.html)
- [templates/admin_portal/base.html](../templates/admin_portal/base.html)
- [templates/admin_portal/dashboard.html](../templates/admin_portal/dashboard.html)
- [templates/admin_portal/application_programs.html](../templates/admin_portal/application_programs.html)
- [templates/partials/workspace_header.html](../templates/partials/workspace_header.html)
- [templates/partials/workspace_icon.html](../templates/partials/workspace_icon.html)
- [templates/programs/manage_list.html](../templates/programs/manage_list.html)
- [templates/programs/photo_queue.html](../templates/programs/photo_queue.html)
- [templates/events/manage_list.html](../templates/events/manage_list.html)
- [templates/members/list.html](../templates/members/list.html)
- [templates/content/list.html](../templates/content/list.html)
- [templates/ewaf/unavailable.html](../templates/ewaf/unavailable.html)

Added files:

- [static/css/admin-ui.css](../static/css/admin-ui.css): Admin-only presentation layer.
- [scripts/admin_ui_browser_qa.py](../scripts/admin_ui_browser_qa.py): disposable synthetic fixtures and Chrome test runner.
- [scripts/admin_ui_browser_qa.cjs](../scripts/admin_ui_browser_qa.cjs): rendered UI, responsive and icon-fallback assertions.
- This validation note.

## Validation commands

Executed from the repository using its existing virtual environment:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test core.tests.test_workspace_navigation core.tests.test_public_portal announcements.test_results announcements.test_public_results membership.test_confirmed_requirements programs.test_public_receipt --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test membership members documents core accounts programs announcements assistance events ewaf --noinput --verbosity 1
$env:NODE_PATH = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
.\.venv\Scripts\python.exe manage.py test scripts.admin_ui_browser_qa scripts.admin_navigation_browser_qa scripts.public_navigation_browser_qa scripts.announcements_members_browser_qa scripts.revised70_browser_qa scripts.membership_browser_qa --noinput --verbosity 1
node --check scripts/admin_ui_browser_qa.cjs
git diff --check
git diff --stat
git status --short
```

- Django system check: **no issues**.
- Focused Django run: **63 passed, 0 failures, 0 skips**.
- Affected-app regression run: **317 passed, 0 failures, 0 skips**. This includes the focused tests; counts are not additive unique coverage.
- Final combined Chrome run: **6 passed, 0 failures, 0 skips**, 110.796 seconds. The six workflows cover populated Admin presentation, permission-aware Admin navigation, public navigation, announcement/Results integration, revised applications and onsite membership. Captured output: [final-browser-tests.log](../.local/qa-admin-ui-cleanup/final-browser-tests.log).
- JavaScript syntax and task-file whitespace checks passed.

Before/after runs of the new Chrome harness were also executed during visual iteration. The initial baseline reproduced the black SVGs; native form collisions and title/action overlap were found by inspecting screenshots and corrected. New assertions cover both. Iteration runs are not added to the final regression count.

## Browser inspection and accessibility

The populated synthetic-data harness checks **14 pages** at **320, 390, 768, 1024 and 1440px**: Dashboard, Members, Programs, program creation, Events, program application chooser, application list, Photo Verification Queue, non-EWAF selection, EWAF unavailable state, Announcements, CMS, native document-type list and native document-type creation. Desktop/mobile screenshots were inspected across these areas, including the final native form correction. All captures use synthetic records.

Local evidence is in [before](../.local/qa-admin-ui-cleanup/before/), [after](../.local/qa-admin-ui-cleanup/after/) and [diagnostics](../.local/qa-admin-ui-cleanup/diagnostics/). The [original fallback](../.local/qa-admin-ui-cleanup/before/icons-without-admin-css.png) reproduces the oversized black shapes; the [corrected fallback](../.local/qa-admin-ui-cleanup/after/icons-without-admin-css.png) retains bounded outline icons. These ignored local artifacts are not deployment assets.

Checks cover no document-level horizontal overflow, responsive layout, real GET filters and record links, empty states, bounded outline icons, active navigation, keyboard disclosure, Escape/focus return, sidebar expansion/scroll persistence, high contrast, Largest text at 320px, reduced motion and forced colors. Tables retain their existing keyboard-accessible horizontal scroll regions where needed. Normal operation reported zero captured JavaScript/console errors. Measured sidebar text contrast was at least **5.707:1** across tested normal/high-contrast states. Decorative icons remain hidden from assistive technology; visible navigation labels and existing focus controls are preserved.

## Regression preservation and data safety

The focused and affected-app suites cover Phase 2 navigation and restricted staff/direct URL permissions; Phase 1 seven-section public navigation, authorized masked Results and session-protected receipts; DEC-025 publication authorization, withdrawal/freshness and Members navigation; DEC-027 separate Association/PDAO guidance and existing membership approval/PRPWD controls. Application/photo review, eligibility, non-EWAF selection, assistance records, private documents, CMS and audit/history regressions remain covered.

A verified starting manifest of **348 pre-existing nonignored repository files** is retained at the vault's `.local/admin-ui-cleanup-20261010/`. Exactly **12 existing templates changed**; the other **336 original files remain byte-identical**, with no deletions. Existing named URL tags and permission conditions were compared with the starting templates. The pre-existing tracked and untracked work is preserved; the full HEAD diff includes earlier work and is not this task's scope.

**Backend domain changes: NONE. Database schema changes: NONE. New migrations: NONE. Development database changes: NONE.** Tests use the separate disposable test database and temporary private media. No application reference, member record, approval, evidence state or publication was changed in the owner's database. No commit, push, reset, cleanup or branch change.

## Limitations

- Validation uses local Chrome and synthetic fixtures, not a full browser matrix or assistive-technology certification.
- Existing native Django `admin/js/filters.js` produces one error when all session storage access is deliberately denied. The existing browser harness treats that known error separately and verifies navigation still works; normal operation must remain error-free. Vendor JavaScript was not modified.
- OQ-27 evidence-handling policies remain unresolved. Visible confirmed membership guidance is **not full document-verification enforcement**. This cleanup changes neither the checklist nor approval conditions.
- Controlled EWAF, reports, future analytics and other unfinished modules were not enabled or credited. No further implementation phase was started.
