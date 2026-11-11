# Public Programs design — 26 October 2026

The owner requested a clean, professional public Programs page using the supplied screenshot as inspiration. The change is limited to public browsing and its presentation; existing application, disability screening, evidence, scoring, selection and publication policies remain intact.

## Page changes

- Compact header with the existing Association identity, a muted green introductory area, and clearer heading hierarchy.
- Three application steps with the existing feature-gated tracking link. Detailed verification and selection guidance remains available in a disclosure section.
- Consistent program cards in a three-column desktop grid, two columns on tablets and one on narrow screens. Cards retain distinct open, upcoming, ended, cancelled and unavailable labels.
- Public search and category filters, status counts, six programs per page, numbered pagination, filter reset and clear empty states. Filters persist across pages; switching status resets pagination.
- Exact opening/closing times remain accessible through each card's expandable date range, including Philippine time. Existing detail/application routes are preserved.
- The catalog's stylesheet is scoped to this page. Keyboard focus, labels, high contrast, enlarged text and reduced-motion settings are retained. Responsive CSS is implemented; actual viewport rendering was not visually verified.

## Data and preservation

Search, categories and counts use only publicly visible programs. Draft, archived and future-publication records remain private. Open counts and cards use the existing application-readiness checks, including required EWAF configuration; no authorization is inferred. The older `period=current` bookmark and date-based past filters remain supported.

No model, migration, dependency, business record or global navigation change was required. The existing private `programs/catalog.py` helper remains unchanged; the new query/presentation helper is `programs/public_catalog.py`.

The new template is `templates/programs/public_catalog.html`. The earlier template is retained so an already-running process can continue rendering coherently until restarted. The development runtime's unrelated changes and private application guards were preserved; only its public-list handler and scoped catalog files/tests were updated.

## Checks

- A broader 97-test source run passed 95 tests. One new fixture supplied a duplicate authorization timestamp, and one historical pagination assertion expected ten items per page. Both test issues were corrected; no application code change was needed for those failures.
- The final focused source run passed **25 tests**, covering the full public catalog and availability suites plus the updated existing pagination regression.
- The same **25 tests passed against the retained development runtime**.
- Existing disability-screening and application-workflow tests passed in the broader run.
- All Django tests used fresh isolated MySQL instances with `DB_TEST_NAME=test_g12_disposable`, through the existing G12 launcher and `RegistrationIntakeTestRunner`. Test databases were destroyed afterward.
- Actual HTTP checks on the new development process passed: six-card listing, search/category combination, all status filters, legacy bookmark, numbered pagination, empty results, exact application schedules, tracking/guidance and the new stylesheet.
- Changed Python syntax and `git diff --check` passed. Django checks reported no configuration issues during tests.
- Browser visual QA/screenshots were unavailable because browser launching is restricted in this session. CSS breakpoint presence is not a claim of rendered desktop/mobile acceptance.

Evidence: `source-tests.log`, `runtime-tests.log`, `http-checks.json`, and `broad-test-summary.txt`.

## Local preview

The updated development preview is running at **http://127.0.0.1:8000/programs/** using the existing fictional development database. Verification consisted of public GET requests and did not submit or alter business records.

The normal port-8003 process must be restarted to load the new Python handler. Windows denied stopping that existing process earlier in this session. **Restart System.cmd** can be run manually to load the update at the usual address; the new port-8000 preview already serves the redesign.
