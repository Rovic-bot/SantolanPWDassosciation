# Public portal layout continuation — November 4–5, 2026

Continued the existing redesign after the owner supplied the published Figma Make reference and authorized inspection in Brave. The running preview remains [127.0.0.1:8013](http://127.0.0.1:8013/).

The reference was inspected in the owner's open Brave tab. Its original Make export is retained in `../Public Portal Figma Make Redesign/make-export/code/src/` outside this repository. Figma connector access to file `FputU7qT4hymHRt0MPOT2e` was denied, so the existing exported `App.tsx` and `index.css`, together with the published reference, supplied the layout evidence. The published reference's photographs were broken during this inspection; the implementation keeps working local images. SHA-256 comparisons confirmed the Home gathering, community walk, and assistance supplies JPEGs exactly match the exported originals.

## Changes

- `static/css/public-make.css`: locally served Manrope, light large headings, matching content widths and section proportions, compact navigation, responsive hero, service strip, overlapping image panels, underlined listing tabs, squared cards, Resources sidebar, and four-column footer. An arrow target keeps a full 44px grid track to prevent narrow-screen overflow.
- `templates/public/base.html`: reference brand treatment and footer grouping, with the real staff sign-in and existing conditional tracking link retained.
- `templates/public/about.html`: reference heading text.
- `templates/public/resources/index.html`: existing task cards alongside the archive photograph and Help Desk information; existing FAQs, downloads, referral actions, resource links and CMS content retained.
- `templates/events/public_list.html`: text-led introduction matching the Make Events page; individual published event images remain dynamic.
- `static/fonts/manrope/`: five Google Fonts font files, source attribution, and SIL Open Font License. No external font request is needed when browsing the portal.

This continuation changes presentation only. No database fields, migrations, forms, services, eligibility rules, references, publication controls, uploads, or staff layout files were changed. Existing unfinished Git work was preserved. Pre-continuation versions are in ignored `.local/public-make-continuation-20261104/before/`.

## Validation

- **114 focused Django tests passed**, using the existing G12 runner and a freshly provisioned disposable MySQL instance with `.env` disabled and separate database grants. Test execution reported 8.807 seconds, excluding database setup. The suites cover public pages, Home program availability, resident/staff layout boundaries, registration/PDAO, PDF forms, program catalogs, tracking, receipts, and referrals.
- **48 public HTML views, 5 image URLs and 2 blank PDFs passed** the existing read-only HTTP check. The updated `http-checks.json` records this continuation's run. Staff sign-in remained outside the public Make theme. No application was submitted through the live preview.
- All five local font URLs returned byte-identical files over HTTP; see `continuation-font-checks.json`.
- Django system checks and Git whitespace checks passed. Static files were collected and the retained local web server restarted without migrations.
- Native Brave inspection checked desktop Home, About, Resources, Programs and its live cards, Announcements, Events, Results, and Membership. Home and Resources were inspected at 320 CSS pixels; Resources was also inspected at 390px. Home was inspected at a tablet-sized window before its overflowing arrow target was corrected. Mobile navigation exposed all eight destinations. Largest text, high contrast, keyboard focus, Escape dismissal, and preference reset were exercised at 320px.
- [Native full-page Home screenshot at 320 CSS pixels, DPR 2](continuation-home-320.png).

The live application retains its own published records, complete forms, guidance anchors, filter options, and service availability. Those differ intentionally from the Make prototype's sample data and simplified forms. These checks do not establish complete WCAG conformance or a production deployment. Earlier documented historical test limitations remain outside this layout task.
