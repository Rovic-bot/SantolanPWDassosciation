# Public portal redesign — October 27, 2026

Implemented locally on `EWAF-testing`. This redesign has not been committed, pushed, merged, or deployed. The earlier branch push and Association-logo work preceded this redesign and remain preserved.

## Follow-up: header links and replacement logo

At the owner's subsequent request, removed **Display & reading** and **Get help** from the top public header. The floating Display button, saved preferences, help navigation, and footer links remain available.

Copied the newly supplied `Assets/Logo.png` unchanged to `static/images/association-logo.png` (1254×1254 RGBA; transparency preserved). Updated the shared logo partial, public/Admin favicons, and Association print-form logo. This is an authorized logo replacement; Admin layout styles are unchanged. The previous JPEG remains as an inactive historical asset.

Follow-up files: `templates/public/base.html`, `templates/partials/association_logo.html`, `templates/base.html`, `templates/admin/base_site.html`, `templates/membership/registration/association_print.html`, and the new PNG.

Verified nine desktop/mobile page combinations across Home, About, and native Admin sign-in at 1440, 390, and 320px: PNG and favicon load, square proportions are preserved, no horizontal overflow, and the two header controls are absent. Floating Display opening/Escape and all eight navigation links remain functional. Django checks, template compilation, migration dry run, and `git diff --check` passed.

Current header screenshots: [Desktop](public-portal-2026-10-27/header-update-desktop.png) · [Mobile](public-portal-2026-10-27/header-update-mobile.png). The validation and full-page screenshots below document the preceding redesign before this requested logo/header follow-up.

PNG SHA-256: `bfe9b65266222fada6703e416769ce01cd0f8775d6480a4bdf9259179f8a7ad5`.

## Preview

The subsequent registration-form simplification and privacy pop-ups are documented in [registration privacy validation](registration-privacy-dialog-2026-10-27-validation.md).

Open **http://127.0.0.1:8000/** on this computer. Use Ctrl+F5 if an older stylesheet is cached. The preview uses the existing retained fictional development database; published testing notices and program names have not been rewritten.

If the local server is stopped, open **Start System.cmd**, or run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-current-development.ps1
```

The existing ignored local launcher remains pinned to its separate development database. No ordinary application database fallback was introduced.

| Page | Route | Desktop screenshot | Mobile screenshot |
| --- | --- | --- | --- |
| Home | `/` | [Desktop](public-portal-2026-10-27/home-desktop.png) | [Mobile](public-portal-2026-10-27/home-mobile.png) |
| About | `/about/` | [Desktop](public-portal-2026-10-27/about-desktop.png) | [Mobile](public-portal-2026-10-27/about-mobile.png) |
| Announcements | `/announcements/` | [Desktop](public-portal-2026-10-27/announcements-desktop.png) | [Mobile](public-portal-2026-10-27/announcements-mobile.png) |
| Events | `/events/` | [Desktop](public-portal-2026-10-27/events-desktop.png) | [Mobile](public-portal-2026-10-27/events-mobile.png) |
| Programs | `/programs/` | [Desktop](public-portal-2026-10-27/programs-desktop.png) | [Mobile](public-portal-2026-10-27/programs-mobile.png) |
| Results | `/results/` | [Desktop](public-portal-2026-10-27/results-desktop.png) | [Mobile](public-portal-2026-10-27/results-mobile.png) |
| Membership & PWD ID | `/membership/register/` | [Desktop](public-portal-2026-10-27/membership-desktop.png) | [Mobile](public-portal-2026-10-27/membership-mobile.png) |
| Resources & Help | `/resources/` | [Desktop](public-portal-2026-10-27/resources-desktop.png) | [Mobile](public-portal-2026-10-27/resources-mobile.png) |

The separate PDAO service is also shown in [this screenshot](public-portal-2026-10-27/membership-pdao-desktop.png).

## Presentation and behavior

- Public-only design tokens: soft backgrounds, deep teal actions, dark text, restrained borders, Segoe UI, 18px default body text, responsive content widths, visible focus, and comfortable controls.
- Actual Association logo, concise Home welcome, three service entry points, published updates, and existing Help Desk content.
- About combines a community photograph with a short purpose summary; the full published background and mission remain available in a disclosure.
- Announcements and Programs use readable rows with existing search, categories, periods, status labels, deadlines, and pagination. Program requirements remain on their detail pages.
- Events separates scheduled activities from annual observances. Observances have an accessible list, month grouping, source details, and expandable information. Empty views do not invent activities.
- Results lists only existing authorized publication payloads and distinguishes them from private program tracking.
- Membership provides keyboard-operable service tabs and separate Association/PDAO checklists. Both remain available without JavaScript. Direct links to either checklist reveal the correct panel.
- Resources offers tracking, referral guidance, FAQs, existing resource publications, and Help Desk information. External verification remains conditional on explicit publication.
- Public detail and form templates inherit the same presentation. Existing verification, form fields, privacy notices, expiry instructions, and submission behavior remain in place.
- Existing text size, contrast, reduced-motion preferences, and supported browser read-aloud controls continue to use `santolan-display`. No language selector or translation system existed in this checkout; none was invented.

## Scope and preservation

Source comparison against the start-of-redesign hashes found no changes to Admin templates/styles, authentication, permission code, models, migrations, EWAF, membership requirements, form validation, or decision/release logic.

The shared `base.html` gains an empty `final_styles` block. Only `public/base.html` fills it. All new CSS is scoped to `.public-portal`; the new JavaScript also checks this class. Custom and native Admin templates do not load either public asset.

The only Python change supplies the existing **published** contact content to the Resources template. It does not change publication rules or expose drafts.

Checklists continue to use the current `membership/guidance.py` values, including quantities and alternatives. The later approved current Association checklist is preserved: completed form, one long brown envelope, four PWD ID photocopies, two Voter's Certificate photocopies, two Birth OR Marriage Certificate photocopies, and four 2×2 photographs. The separate PDAO checklist and renewal-only old-ID instruction remain distinct. The redesign does not reinterpret the earlier October 10 TARGET specification as implementation authority.

## Assets

All 21 supplied assets were visually reviewed. The selected photographs were copied unchanged; SHA-256 comparison confirms the static files match the source bytes. Existing face blurring is retained. No generated images, stock photographs, new face processing, or replacements with identifiable originals were used.

| Source in `Assets/` | Public static file | Purpose |
| --- | --- | --- |
| `photo_10_2026-10-27_06-00-22.jpg` | `static/images/community/gathering.jpg` | Home community gathering |
| `photo_12_2026-10-27_06-00-22.jpg` | `static/images/community/community-walk.jpg` | About, community participation and banner |
| `photo_13_2026-10-27_06-00-22.jpg` | `static/images/community/activities.jpg` | Events introduction |
| `photo_5_2026-10-27_04-10-15.jpg` | `static/images/community/assistance-supplies.jpg` | Programs supporting photograph |

Images use Django static URLs, informative alternative text, responsive containers, and deliberate proportions. Banner information is repeated as readable captions. Historical activity photographs are not presented as current service availability. The previously implemented actual-logo asset remains `static/images/association-logo.jpg`.

## Checks completed

1. Django database/configuration check: **passed**. Migration dry run: **no model changes detected**. Pending migrations: **0**. Public templates compiled successfully. These checks used a wrapper that rejected database writes.
2. Existing tests: **13 passed** using `scripts/g12_test_runner.py` with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`. Eight ResourceTests covered draft privacy, publication snapshots, source validation, unsafe URLs, permissions, stale edits/audit rollback, external verification, and guide navigation. Five PublicPortalTests covered primary navigation, all eight public pages and their methods, membership landing behavior, contact information, and login configuration constraints.
3. Tests used a fresh loopback MySQL instance, `test_g12_disposable`, isolated media, and a model-synchronized schema. No retained application data was used. The first attempt with the generic durable runner stopped the eight resource tests at its temporary-media guard; rerunning with the repository's isolated-media runner passed all 13.
4. Initial responsive browser review: **79 page/viewport combinations passed**, with no detected overflow, clipped checked headings/actions, broken visible images, server errors, or JavaScript errors. This included all eight pages at 1440, 1200, 768, 390, and 320px, plus 200% text at 1280 and 320px; 15 discovered detail/tracking destinations; filters and empty searches; observance views; and saved display preferences.
5. Additional browser review: **137 checks passed**, including 13 further published detail/referral destinations, long-title stress fixtures, real GET search/filter submissions, native required-field validation/focus, keyboard service selection, FAQs, display-panel focus/Escape, read-aloud/stop wiring, and Admin isolation. No application or verification POST was forwarded by the browser harness.
6. Public form layouts checked at 1440, 390, and 320px and 200% text: Association registration, PDAO registration, PDAO print preparation, private program tracking, and referral verification. Reference-number manual entry remains available.
7. Checked visible major text/control colors against their computed solid backgrounds: **no contrast failures detected**. Chromium visual zoom at 200% and 320px reflow equivalent to a 1280px desktop view at 400% were checked. This is a targeted evaluation against the [WCAG 2.2 criteria](https://www.w3.org/WAI/WCAG22/quickref/), not certification.
8. All eight desktop/mobile layouts were visually inspected. Final capture verified all eight actual navigation clicks, mobile Menu/Escape, and announcement search tab order, and saved **17 screenshots**.
9. Admin comparison: custom workspace and native Admin presentation fixtures, desktop 1440px and mobile 390px, were **pixel-identical in all four comparisons** to their pre-redesign renderings. Fixtures contained no private records and were rendered with database access prohibited.
10. `git diff --check`: **passed**.

Local inspection scripts and detailed JSON evidence are retained under ignored `.local/public-redesign/`. The full historical test suite and older UI harnesses were not run; some assert superseded presentation details. No existing test assertions were weakened or deleted.

## Files changed for this redesign

Modified:

- `core/resources.py`
- `templates/base.html`
- `templates/public/base.html`
- `templates/public/home.html`
- `templates/public/about.html`
- `templates/public/resources/index.html`
- `templates/announcements/public_board.html`
- `templates/events/public_list.html`
- `templates/programs/public_catalog.html`
- `templates/programs/public_detail.html`
- `templates/results/public_list.html`
- `templates/membership/guidelines.html`
- `templates/membership/registration/apply.html`
- `templates/membership/pdao/apply.html`

Added:

- `static/css/public-portal.css`
- `static/js/public-portal.js`
- `templates/public/icon.html`
- `templates/public/observance_list.html`
- The four photographs listed above under `static/images/community/`
- This validation note and 17 screenshots under `docs/public-portal-2026-10-27/`

Earlier logo changes in `templates/admin/base_site.html`, `templates/partials/workspace_header.html`, `templates/membership/registration/association_print.html`, `templates/partials/association_logo.html`, `static/css/branding.css`, and `static/images/association-logo.jpg` remain preserved. They were not introduced by this redesign. User-supplied `Assets/` files are unchanged.

## Specific limitations

- This preview retains fictional testing content. No verified phone number, office hours, or street address was available to add; the existing published Help Desk guidance remains.
- Verification and submission workflows were preserved, but no real membership, PDAO, program, or referral application was submitted during this UI review.
- Read-aloud button wiring was checked with speech output intercepted; audible quality depends on the device/browser voice. Screen-reader and physical-device user acceptance, browser-toolbar zoom, and a complete WCAG audit remain outside the performed checks.
- The administrator sign-in page already uses the public shell, so its header/footer follow the redesign. Authenticated Admin workspace layouts remain unchanged.
