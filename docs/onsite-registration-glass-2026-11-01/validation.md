# Guided onsite registration — 1 November 2026

The onsite intake now uses the existing admin theme and sidebar with a dedicated registration workspace: centered two-column field cards, an application guide, reference lookup, status feedback, sticky actions, and a keyboard-accessible review dialog. Smaller screens use a single field column. Both themes reuse the shared admin preference and color tokens.

Following the owner's layout adjustments, the Application Sections navigation and its progress indicator are removed at all screen sizes. The form remains wide, with the Application Guide and help card in a sticky column on its right at desktop widths. The guide stays below the top bar while scrolling and can scroll internally on short screens or with enlarged text. Tablet and mobile layouts place it below the form. The related navigation/progress JavaScript and CSS have also been removed; draft, validation, review, and submission behavior are retained.

The actual application is Django. `/admin/members/registration` and its trailing-slash variant redirect to the existing, permission-checked `/membership/applications/new/` route. The walk-in registration entry point uses the same presentation. Native `/admin/` tools, the analytics dashboard, public pages, printed registration, and existing correction screens retain their presentation and workflows.

## Compact header follow-up — 2 November 2026

Removed the new-application eyebrow, large introductory heading, and supporting paragraph at the owner's request. A visually hidden page heading remains for accessibility. The status card stays above the lookup with reduced header spacing and full width on mobile. All form fields, the application guide, and registration actions remain in place. Updated the stylesheet cache version and the existing browser harness's page-ready locator.

Verification: rendered the full onsite template with the existing synthetic Association form under a read-only database guard; confirmed the removed copy is absent, all 30 fields and seven sections remain, and the status, lookup, draft/review controls, and guide remain. Django database/system checks and `collectstatic` passed (1 copied, 211 unmodified). JavaScript syntax and `git diff --check` passed. No workflow or data changes.

## Preserved behavior

- All 30 current Association form fields, required flags, choices, validators, and submitted values are retained. The existing onsite PWD-number requirement is unchanged.
- Only configured upload fields are rendered. The current Association policy uses onsite document presentation; it does not enable the generic prompt's medical-certificate/government-ID uploads or additional unsupported applicant fields.
- The lookup submits the existing AMR reference to the existing retrieval view. It opens the original record rather than creating another application.
- Review validates the form and displays its values before the existing authenticated, CSRF-protected POST. Saving creates the existing pending intake. Membership approval remains a separate staff action.
- “Save as draft” is a recoverable snapshot in page memory only, including selected files. Its status explicitly explains that it lasts while the page stays open. No applicant details are stored in localStorage or sessionStorage. The snapshot is cleared when leaving the page.
- Optional “present onsite” checkboxes are temporary planning aids. They do not mark documents received or verified and are not posted as new backend fields.
- Without JavaScript, all fields and the original submit action remain available.

No dependencies, migrations, new persistence, or business-rule changes were introduced. Earlier unfinished dashboard/admin work remains intact.

## Files changed in this registration task

- `templates/membership/onsite/{base,intake,topbar,workspace,section,field}.html`: scoped layout, reusable fields/sections, guide, lookup, and review dialog.
- `templates/membership/encode.html`: historical onsite entry point uses the same workspace while retaining its own field contract.
- `core/templatetags/onsite_registration.py`: presentation grouping and local widget hints; does not alter form validation.
- `static/css/onsite-registration.css`: registration-only glass surfaces, layout, controls, themes, responsive rules, and accessibility adaptations.
- `static/js/onsite-registration.js`: memory-only drafts, upload feedback, validation, review, and original submission.
- `membership/registration_views.py`: selects the new template for walk-in intake only.
- `config/urls.py`: requested registration URL alias.
- `templates/partials/workspace_header.html`: selects the registration breadcrumb/header only when requested by the onsite template.
- `membership/test_onsite_registration_alignment.py`: retained field/permission/workflow assertions plus alias and page-isolation checks.
- `scripts/onsite_registration_browser_qa.py` and `.cjs`: synthetic end-to-end validation and screenshots.
- `scripts/admin_theme_fixtures.py` and `scripts/admin_theme_browser.cjs`: accommodate this page's requested Dashboard header link in the shared regression harness.

## Verification

- Sticky-guide follow-up: 16 read-only layout/scroll checks passed in both themes at 1600, 1280, 1100, 1024, 768, 390, and 320 pixels, plus short-screen/largest-text checks. Desktop scrolling keeps the guide beneath the top bar; the form and guide do not overlap. No page overflow or JavaScript errors. Static collection updated the stylesheet. [Scroll evidence](guide-scroll-results.json), [dark](guide-dark.png), [light](guide-light.png).
- Centered-layout follow-up: the existing browser workflow passed again with the Application Sections panel absent, including both themes, all 25 responsive checks, draft/review actions, and the original submission/approval flow. System and JavaScript checks passed; static collection updated the two changed assets.
- Django application/database system check: passed, zero issues.
- Final focused run: **10 tests passed**, covering field parity, required PWD number, permissions, aliases, unrelated-page isolation, legacy onsite approval behavior, and the complete browser workflow.
- Earlier focused field/alignment/prefill checks: **21 tests passed**. The initial browser run identified a dialog keyboard-cycle issue; the final run confirms the fix.
- Browser: **25 responsive checks** across 1600, 1280, 768, 390, and 320 pixels. These cover the public form, onsite form in both themes, existing pending review, and approval. No page overflow, duplicate IDs, or JavaScript errors were found.
- Browser interactions: draft save/change/restore; no applicant values in browser storage; validation summary; dialog focus containment, Escape and focus return; mobile review; configured file selection, onsite planning, restore, remove and invalid-type feedback; civil-document selection consistency; largest text, high contrast, reduced motion, forced colors; JavaScript-disabled fallback; alias and retained-reference lookup.
- Synthetic browser submission preserved all applicant values and required explicit approval before creating a member. All database tests ran in verified disposable MySQL instances, not the retained application database.
- JavaScript syntax checks and `git diff --check`: passed.
- Production asset collection: **191 files collected** with `collectstatic --noinput` into isolated `.local/onsite-registration-static-build`.
- Local web process refreshed after validation. The requested alias responds through the existing login guard. The retained MySQL process and database stayed running.

The broader `PendingRegistrationTests` run had **35 passing tests and one unrelated existing failure**: `test_guidance_reflects_gate_with_resources_appended_to_public_navigation` expects “Start online membership registration.” The unchanged public template already says “Start membership application” in HEAD. Neither that public template nor the historical copy assertion was changed in this scoped task.

Final focused command:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test membership.test_onsite_registration_alignment scripts.onsite_registration_browser_qa membership.tests.MembershipTests.test_ordinary_staff_complete_onsite_review_with_legacy_public_intake_closed --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

## Synthetic visual evidence

- [Desktop dark](registration-dark.png) · [Desktop light](registration-light.png)
- [Mobile dark](registration-mobile-dark.png) · [Mobile light](registration-mobile-light.png)
- [Review dark](review-dark.png) · [Review light](review-light.png)
- [Browser results](browser-results.json)

Screenshots contain fictional test data only. Full-page captures show the sticky action bar at its viewport position while the remaining document extends below it.
