# Administration changes layout and Inspect popup — November 10, 2026

The owner requested the supplied dashboard layout: four summary cards, a compact activity stream with tabs/search, filters on the right, and Inspect opening a popup.

## Implemented

- Four live summary counts: recorded actions, approvals, document/print access, and publications. Counts reflect the current filters and permitted sources; no sample totals, growth percentages, or pending-review counts were introduced.
- Category tabs, search, action badges/icons, administrator initials, record identifiers, Philippine timestamps, and a compact scrollable list with existing 30-record pagination.
- Right filter panel with all-time/today/7/30/90-day/custom ranges, system section, action category, exact action, and administrator. On small screens Filters reveals the panel; the summary cards become two columns.
- Shared presentation categories drive the badges, category filters, tabs, and counts. Existing exact readable action labels remain unchanged. Approval/selection/publication/release distinctions and original source histories are preserved.
- Inspect fetches a permission-checked, read-only HTML fragment into a native dialog. It shows the saved action, record, administrator, timestamp, section, and escaped notes. Closing with the close control, Escape, or backdrop restores focus to the original entry without changing the page URL or filters.
- Loading/error/retry states are supported. Normal detail links and GET filter submission remain usable without JavaScript.
- The existing admin palette and navigation remain in both themes. No schema, migration, stored audit, or decision workflow changes.

## Validation

**15 tests passed** in disposable native MySQL, including historical audit behavior, permissions, escaping, read-only endpoints, summary/category consistency, combined filters, inclusive local date presets, existing custom dates, and protected popup fragments. The permission-limited reader also receives permission-limited summary counts.

Browser verification passed at **1440, 768, 390, and 320px in light and dark themes**, including all eight popup layouts. Checked no horizontal overflow, unchanged list URL on Inspect, focus containment/restoration, Escape/close/backdrop dismissal, fetch failure/retry, filter counts, exact action filtering, pagination, search, mobile filter controls, and no-JavaScript filters/detail fallback. No JavaScript errors or browser mutation requests were recorded. Original fixture audit records were unchanged.

Screenshots and `results.json` use fictional disposable records only. Visually inspected the dark desktop stream and light mobile layout plus the dark mobile popup.

```powershell
.venv/Scripts/python.exe scripts/g12_test_runner.py test audit scripts.admin_activity_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Passing test artifacts: `santolan-g12-tests-gn52eey5`. A read-only render against retained development data returned HTTP 200 in **0.763 seconds using 8 queries**, with no writes; this is a local observation, not a production benchmark.

Application/database configuration, JavaScript/Python syntax, and `git diff --check` passed. The local web process was refreshed after verification. Existing unfinished work and retained data/uploads remain preserved.
