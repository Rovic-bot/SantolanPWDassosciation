# Public Portal Make implementation — November 4, 2026

Implemented on the retained development application at http://127.0.0.1:8013/ following the owner's instruction to apply the design to the system.

Design source: [Santolan PWD — Public Portal Redesign](https://www.figma.com/make/FputU7qT4hymHRt0MPOT2e/). The actual Make source was exported through the authorized browser session and inspected outside the application repository. The Django implementation adapts its photographic Home composition, navy/blue/violet palette, horizontal navigation, editorial sections, and responsive styling. It retains the application's complete public functions where the Make draft used simplified sample states.

## Scope

The new stylesheet is opted into by resolved public endpoint through `public_redesign_enabled`. Staff login, internal dashboards, staff reviews, and shared staff print/error views do not receive it. No models, migrations, forms, service rules, private documents, issued references, or application records were changed by this implementation. Existing unfinished Git changes were preserved.

Implementation files in this phase:

- `core/context_processors.py`: public theme opt-in using the existing resident route set.
- `templates/public/base.html`, `resident_base.html`, and `section_hero.html`: scoped styling and shared presentation.
- `templates/public/home.html`: Make-inspired Home with real published content and existing guidance anchors.
- `templates/public/about.html`, `resources/index.html`: image-led layouts with existing information and actions.
- `static/css/public-make.css`: public-only responsive theme, opaque forms, contrast and print safeguards.
- `core/tests/test_resident_layout_boundary.py`: theme boundary assertions.
- `scripts/public_make_http_qa.py`: reproducible read-only local smoke check.
- `scripts/public_make_baseline_runner.py`: diagnostic comparison with saved pre-change templates.

The current registration contract remains authoritative: the October 24 dual-registration/PDF checklist is retained; no older requirements were substituted. Association membership and PDAO applications remain distinct.

## Page and component coverage

| Public page | Retained functions and new presentation | Verification |
|---|---|---|
| Home `/` | Photographic hero, service shortcuts, published announcements, current events, program availability, CMS guidance, Help Desk and disclosure anchors | Desktop and mobile visual review; Home tests; HTTP |
| About `/about/` | Community photograph and overlapping services panel; background/mission/objectives disclosures; separate PDAO guidance | Desktop, tablet, mobile visual review; HTTP |
| Announcements `/announcements/` | Compact introduction, horizontal topics, search/filter controls, dates, editorial rows, pagination, detail links and attachments | Desktop visual review; public tests; HTTP including empty search |
| Events `/events/` | Community image, category/schedule filters, date-led rows, details, participation restrictions, annual observance list/month controls | Desktop visual review; public tests; HTTP including past events and observance details |
| Programs `/programs/` | Photograph, current filters/search/periods, responsive program grid, eligibility/deadline/status information, details and application entry | Desktop visual review; catalog/receipt/tracking tests; HTTP including empty search and page 2 |
| Results `/results/` | Publication register, result details and existing permitted downloads, private follow-up guidance | Desktop visual review; publication tests; HTTP |
| Membership & PWD ID `/membership/register/` | Separate service tabs, current checklists, downloadable forms, full actual Association and PDAO forms, existing uploads/validation/receipts/printing | Mobile service switching; desktop/mobile actual Association form review; registration/PDAO tests; HTTP and both blank PDFs |
| Resources & Help `/resources/` | Task directory, approved supplies photo, contact/referral entry, private verification, FAQs, downloads, external verification links and resource details | Desktop visual review; referral tests; HTTP |
| Shared public components | Official logo, all eight navigation destinations, mobile menu, breadcrumbs, footer, display controls, form section links, empty/unavailable states | Mobile menu and visible focus; Largest text + High contrast + Reset + Escape; route boundary tests; HTTP |

Existing backend-dependent success/error/receipt states are retained through their actual templates and covered by focused tests. They were not exercised by submitting real applications during this visual review.

## Verification results

- **114 focused tests passed**, using `scripts/g12_test_runner.py` and its separate disposable MySQL database. See `focused-tests.log`.
- **48 public HTML views passed** the read-only local HTTP check, including the eight main pages, linked details, public forms, verification entries, filters, empty searches, and pagination. All received the new theme.
- **6 image URLs and 2 blank PDF downloads passed**. See `http-checks.json` for routes, statuses, form field names, and PDF hashes.
- **Staff sign-in remained outside the new theme**, checked in live HTML and tests. Shared staff print/unavailable templates also passed theme boundary assertions.
- `current_development.py check` and `git diff --check` passed.
- Static assets were collected and the retained local server restarted. No migration was run.
- Visual review used Brave at desktop widths 1440/1536, tablet width 768, and mobile width 390. The mobile menu, PDAO service switch, display preferences, enlarged text, high contrast, reset, and Escape dismissal were checked in the running application. No visible overlap or horizontal clipping was found in the inspected layouts.

Focused test command:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test core.tests.test_public_portal core.tests.test_home_program_availability core.tests.test_resident_layout_boundary membership.test_pdf_registration membership.test_registration_entry membership.test_pdao_registration programs.test_public_catalog programs.test_tracking programs.test_public_receipt assistance.test_referrals --noinput --verbosity 1
```

### Historical suite limitation

The separate eight-test `membership.test_confirmed_requirements` suite has four existing failures: two expect an Association checklist in older staff markup, and two expect earlier wording/checklist structure. The same four failures were reproduced using the preserved pre-redesign public templates through `BaselineTemplateRunner` (4 passed, 2 failures, 2 errors). They are not resolved by this visual change; older assertions must be reconciled separately with the current dual-registration contract. No business rules or staff templates were altered to satisfy those assertions.

This was a focused functional and visual review, not a full accessibility certification or production email-delivery test. Live form submissions and external messages were not sent.

## Previews and images

- [Desktop Home, 1440 CSS pixels](home-desktop.png)
- [Mobile Home, 390 CSS pixels](home-mobile.png)

| Approved local image | Placement |
|---|---|
| `static/images/association-logo.png` | Header and footer; unchanged official mark |
| `static/images/community/gathering.jpg` and existing WebP derivative | Home hero; blurred faces retained |
| `static/images/community/community-walk.jpg` and existing WebP derivatives | About community section |
| `static/images/community/activities.jpg` and existing WebP derivatives | Existing Events introductory image |
| `static/images/community/assistance-supplies.jpg` and existing WebP derivatives | Home membership section, Programs, Resources & Help |

The photographs remain association archive images with their existing privacy edits. Historical supplies imagery is labelled as archival and not a current offer. No stock imagery, private member record, submitted medical document, or reference screenshot was added as website content.
