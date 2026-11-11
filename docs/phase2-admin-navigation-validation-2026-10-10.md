# Phase 2 — Eight-module Admin navigation (G01)

Validated locally on **2026-10-10**. Authority: [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md), [Admin Portal V2](../../00%20-%20Project%20Overview/Admin%20Portal.md), [UI guide](../../UI_Design_Guide_For_Codex.md), [Open Decisions](../../00%20-%20Project%20Overview/Open%20Decisions.md), and [implementation gap analysis, G01](implementation-gap-analysis-2026-10-10.md). [Phase 1](phase1-public-results-validation-2026-10-10.md) and [DEC-027 membership](confirmed-membership-validation-2026-10-10.md) remain preserved.

## Implementation status

**G01 Admin navigation: IMPLEMENTED AND TESTED.** Custom and native Admin pages share eight ordered, collapsible navigation groups for the fully authorized superuser. Restricted staff see only groups containing their permitted destinations; the reporting unavailable notice is shown to superusers, without operational links. This completes the navigation portion of G01, not the unimplemented V2 functionality listed beneath those modules. The owner-defined **70% baseline remains unchanged**.

## Eight modules and destinations

1. **Dashboard:** existing Overview at `core:dashboard`; no new cards, metrics or charts.
2. **Members:** Member Directory, Onsite registration and Membership reviews. Existing record/detail/correction/document/history screens and their permission-aware local Member navigation are retained. No new intake or evidence engine.
3. **Programs & Events:** Program Management, Create program, Events and Create event according to existing view/create permissions. Edit, requirements, publication controls and attendance remain available through their existing record detail screens. No RSVP or opening/authorization change.
4. **Applications & Verification:** a read-only program chooser links to existing per-program applications. Photo Verification Queue and Eligibility review retain their complete backend view gates. Supporting evidence, application review and history remain inside existing application/detail views; no new criterion evidence states/readiness feature.
5. **EWAF & Selection:** existing honest EWAF availability page, eligible-applicant selection queue (`?eligibility=eligible`) for authorized decision staff, and assistance-release entry (`?decision=approved`) for authorized release-record viewers. These are existing queue filters, not new selection/release logic. A selected record is not a completed release. EWAF-dependent final decisions remain blocked by services; historical calculations remain read-only.
6. **Announcements & CMS:** Announcements, Prepare program results, Content Management. Result preparation requires its complete existing permission set. Preview/publication/withdrawal remain in the existing announcement detail workflow; content revisions remain in the CMS editor. No public Results substitute or duplicate publication engine.
7. **Reports & Exports:** explicitly unavailable text, no reporting/export endpoint, download link, form, invented statistic or fake button.
8. **Administration:** superuser-only accounts/roles; individually authorized Disability types, Registration settings, Document types/requirements, Sign-in activity, Administration changes and existing Eligibility statuses. Domain-specific histories remain at their record screens; a complete unified audit system is not newly implemented. Account password/logout actions remain in the existing footer.

## Reused components and presentation changes

`templates/partials/workspace_header.html` is still shared by custom and native Admin. One template tag projects navigation from the signed-in active staff user's actual permissions, existing named routes, resolver and native model metadata. It reuses `PHOTO_VIEW`, `VIEW_PERMISSIONS`, `RESULT_PERMISSIONS` and read-only EWAF view permissions. No service calculation or business mutation is invoked while building navigation.

Native HTML `details`/`summary` provide keyboard and screen-reader-compatible disclosure, visible focus and group/current-page labels. Existing mobile menu/Escape behavior remains. Expansion preferences are stored per tab/account/desktop-or-mobile layout, restored before the existing sidebar scroll offset, and the current module opens on arrival. Storage failures leave workspace navigation usable. Only Admin styles and the Admin branch of shared navigation JavaScript were extended; public behavior is unchanged.

The only new route, `core:application_programs` at `/workspace/applications/`, is a GET/HEAD-only, non-cacheable program chooser. It requires both existing program and application view permissions plus active staff/dashboard access, supports bounded search/pagination and links to `programs:applications`. It performs no updates, application processing, evidence verification, eligibility assessment or ranking. It does not complete G10's target consolidated application dashboard.

## Permissions and privacy evidence

Focused tests verify link visibility matches backend gates rather than one broad Admin permission. A restricted onsite encoder sees only Dashboard/Members. Even granting ordinary staff `auth.view_user/change_user/view_group/change_group` does not reveal privileged accounts/roles or bypass their superuser-only direct-URL checks. Native reference-data staff without dashboard permission retain only their authorized native Administration link; custom workspace access remains denied.

Application-only reviewers can open the chooser/per-program reviews without receiving eligibility, photo, creation or publication privileges. Photo queue requires all three existing view permissions; direct photo review still requires its action permission. Result preparation requires every source/draft permission; lacking publication permission still hides its actual control and returns HTTP 403 for a direct publish POST, with the synthetic draft unchanged. Private evidence/audit URLs remain protected. Selection/release entry points do not grant decision, release, evidence or EWAF permissions.

Seven public sections, current authorized privacy-masked Results, withdrawal/source freshness, immutable revisions, session receipts and issued reference generation remain unchanged. No private member/application information is placed into the navigation projection. No new roles, government integration, login, tracker, RSVP, scoring or automatic publication/selection was introduced.

## Files changed in this phase

New repository files:

- `core/templatetags/__init__.py`
- `core/templatetags/workspace_navigation.py`
- `core/workspace.py`
- `core/tests/test_workspace_navigation.py` — 14 focused behavior/permission tests.
- `templates/admin_portal/application_programs.html`
- `scripts/admin_navigation_browser_qa.py`
- `scripts/admin_navigation_browser_qa.cjs`
- `docs/phase2-admin-navigation-validation-2026-10-10.md` — this report.

Modified repository files:

- `core/urls.py` — additive read-only navigation route, existing routes preserved.
- `templates/partials/workspace_header.html` — eight shared groups.
- `static/css/admin.css` — narrow disclosure/group styling.
- `static/js/site.js` — Admin-only expansion state alongside existing scroll restoration.
- `scripts/announcements_members_browser_qa.cjs` — checks one Members group/Directory destination and stores new regression screenshots separately from Phase 1 evidence.

Vault notes:

- [System Development Progress](../../05%20-%20Development/System%20Development%20Progress.md).
- [Development Roadmap](../../05%20-%20Development/Development%20Roadmap.md).

## Commands and actual results

Run from the repository using its existing virtual environment:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test core.tests.test_workspace_navigation core.tests.test_public_portal announcements.test_results announcements.test_public_results membership.test_confirmed_requirements programs.test_public_receipt --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test scripts.admin_navigation_browser_qa --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test membership members documents core accounts programs announcements assistance events ewaf --noinput --verbosity 1
$env:NODE_PATH = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
.\.venv\Scripts\python.exe manage.py test scripts.public_navigation_browser_qa scripts.announcements_members_browser_qa scripts.revised70_browser_qa scripts.membership_browser_qa --noinput --verbosity 1
node --check static/js/site.js
node --check scripts/admin_navigation_browser_qa.cjs
node --check scripts/announcements_members_browser_qa.cjs
git diff --check
git diff --stat
git status --short
```

- System check passed, no issues.
- Final focused run: **63 run, 63 passed, zero failures/skips**.
- Affected-app regressions: **317 run, 317 passed, zero failures/skips**; includes the focused cases, not an additional distinct-test total.
- Dedicated Admin Chrome workflow: **1 run, 1 passed, zero failures/skips** on its successful rerun.
- Prior public/publication/application/membership Chrome regressions: **4 run, 4 passed, zero failures/skips**. Five distinct browser workflows passed across these two successful runs.
- JavaScript syntax and final diff whitespace checks passed.

Initial runs are not omitted: the first focused run passed 62/63 because a new assertion matched static help text describing publication rather than an actual button. It was corrected to assert the real control and direct forbidden publish behavior; no production authorization was weakened. The first dedicated browser run failed its blanket error assertion under deliberate total session-storage denial because unchanged Django native `admin/js/filters.js` reads storage outside a guard. The revised test verifies navigation remains functional, explicitly checks/reports that specific third-party error, and still requires zero errors in normal operation. This is a recorded limitation, not a claimed fix.

## Browser validation

The new workflow checked exact order/unique sidebar destinations on custom/native pages; Member intake/review, application chooser/links, photo queue, eligible selection, result preparation, CMS and native reference data; ordinary staff with deliberately insufficient privileges; keyboard Enter/Tab, visible outline, mobile Escape/focus restoration; persisted collapsed groups, current-module auto-expansion, independent desktop/mobile scroll restoration, blocked storage and Largest text/high contrast. Responsive checks ran at **320, 390, 768, 1024 and 1440 pixels**. Normal browser runs reported no captured JavaScript errors.

Prior workflows revalidated seven public destinations and support links, real non-EWAF prepare/preview/privacy-confirm/publication, masked public Results and old announcement links, public application reference/receipt through correction/photo review/eligibility/selection/release, and ordinary staff onsite membership. Membership browser checks included 35 responsive/seven enlarged-text checks, confirmed Association/PDAO separation, protected downloads, manual PRPWD, approval blocked before verification, approval/rejection, duplicates and logout.

Inspected `.local/qa-phase2-admin-navigation/native-documents.png`, `mobile-largest-groups.png` and `restricted-encoder-mobile.png`. New publication regression screenshots are in `.local/qa-phase2-results-regression/`; Phase 1 screenshots were preserved. All fixtures are synthetic and all media/database use is disposable. Local tests are not full accessibility certification or association UAT.

## Preservation and database review

Required initial Git status/stat were inspected. A verified backup of **338 pre-existing nonignored repository files** and the two development notes is retained outside the note index at the vault's `.local/phase2-admin-navigation-20261010/`. Exactly five pre-existing repository files changed in this phase; the other **333 files remain byte-identical**, none were deleted. The new files above are additive. Phase 1 source/templates, DEC-027 guidance/partial and membership workflows, all business services, private documents, models, migrations, settings, issued reference logic and audit behavior remain unchanged from the starting working tree. Earlier dirty/untracked work was preserved; final review uses this baseline rather than attributing the whole HEAD diff to this phase.

**Schema changes: NONE. New migrations: NONE. Development database changes: NONE.** Django created/removed only its isolated test database; file tests used temporary media. No reset, clean, commit, push or branch change.

## Remaining gaps and next task

- Controlled EWAF configuration, calculation, ranking/recalculation and EWAF-dependent final processing remain unavailable; only existing read-only/unavailable interfaces were grouped.
- Analytics/dashboard expansions, reports/exports, consolidated application queues, complete audit aggregation, proposed Gemini and optional RSVP remain separate gaps. Navigation does not implement their V2 requirements.
- OQ-27 still blocks complete membership evidence handling/enforcement. The confirmed five-item guidance is not a received/verified/completed checklist; no historical member or evidence state was changed. Other reference/disclosure/program-evidence decisions remain open.
- **Native filter limitation:** deliberately denying all session storage produces one error from unchanged Django `admin/js/filters.js`; workspace disclosure, direct navigation and current indicators still work. Normal storage runs are clean. Native filter-state resilience needs a separately scoped follow-up; no dependency/library or unrelated filter refactor occurred here.
- G28 account-security audit failure behavior remains an early integrity dependency identified by the gap analysis. Recommended next narrow task: inject audit-write failures in disposable tests for password change/sign-in/sign-out, verify the required atomic/fail-safe outcome and scope any necessary fix separately. Program-governance/evidence G06/G11/G13 needs its policy approvals before affected behavior changes. No such work began in this phase.
