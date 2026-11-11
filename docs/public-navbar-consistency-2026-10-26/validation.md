# Public navbar consistency — 26 October 2026

Subsequent owner feedback led to [shared navigation isolation and versioned assets](../public-navbar-isolation-2026-10-26/validation.md). That report records the latest implementation and the remaining port-8003 template restart requirement.

The owner reported that switching public tabs changed the navbar layout. Page styles were overriding header height, container width, Membership link borders and its arrow. Home also used a transparent overlay header, and scrolling changed header dimensions and horizontal margins.

The shared public stylesheet now provides the same opaque header, 96px desktop minimum navbar height (78px for the collapsed mobile layout), spacing, branding and Membership link treatment across public pages. Scrolling adds only a shadow. Page-specific container widths apply to content and footers rather than the header. A stable scrollbar gutter prevents horizontal movement between short and long pages. Home hero spacing accounts for the header now occupying normal document space.

Removed the obsolete header-height observer and the Home-only no-JavaScript header override. Existing navigation destinations, active-link semantics, mobile collapse, keyboard handling, accessibility preferences and receipt print behavior remain intact. No business logic, database records, models or migrations changed.

Validation performed:

- Two existing Django navigation tests passed on a fresh isolated native MySQL instance using `test_g12_disposable`. These cover the eight destinations and one active link on every page. Django reported no system-check issues.
- Public GET checks passed on all eight tabs in the refreshed port-8000 preview. Header markup is identical after removing only the active class and `aria-current` marker. Each page has exactly one current navigation link.
- Six linked changed CSS/JavaScript assets matched the updated source bytes over HTTP. The refreshed preview also serves the corrected no-JavaScript template. Evidence: [HTTP checks](http-checks.json).
- `node --check static/js/site.js` and `git diff --check` passed. The final scoped changes were reviewed against captured pre-task files.
- Chromium could not start: Playwright returned `spawn EPERM`. Rendered desktop/mobile layout, screenshots and browser interaction were not visually verified.

The test command used the existing `.local/dual-registration-20261024/run_tests.py` launcher, `config.intake_test_settings` and `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`, with these labels: `core.tests.test_public_portal.PublicPortalTests.test_primary_navigation_preserves_seven_then_appends_resources` and `core.tests.test_public_portal.PublicPortalTests.test_every_public_page_is_accessible_and_marks_only_current_link`. Isolated test logs are retained under `.local/dual-registration-20261024/temp/santolan-g12-tests-zdqfr2zl/`.

Eight scoped files were synchronized to the existing development runtime after checking baseline hashes. The runtime-only base-template content was preserved. Backups and hashes are under `.local/public-navbar-20261026/`. The agent-owned preview at http://127.0.0.1:8000/ was restarted successfully. The existing port-8003 process already serves the updated static styles; its cached base template needs `Restart System.cmd` to pick up the no-JavaScript correction. A hard refresh loads the revised CSS/JavaScript in an existing browser tab.

The owner's subsequent Results-navbar screenshot established the visual reference. A CSS-only follow-up replaced the initial compact white header with the reference's `#fafaf7` paper background, 96px desktop minimum height and 1rem vertical padding. Existing logo sizing, centered container, link spacing, outlined Membership button and active underline are shared across all tabs. The collapsed mobile layout keeps its 78px minimum height. These dimensions remain unchanged when scrolling or switching sections.

The follow-up stylesheet was synchronized after checking both baselines; backups are under `.local/public-navbar-reference-20261026/`. Repeated GET checks confirmed identical navigation markup apart from the active marker on all eight tabs at both local ports. Both ports returned the exact updated stylesheet bytes. See [reference checks](reference-http-checks.json). `git diff --check` passed again. Earlier Django checks are retained above; this cosmetic follow-up did not rerun them or claim rendered visual comparison. No restart is needed for this stylesheet-only update; hard-refresh the browser to replace its cached CSS.
