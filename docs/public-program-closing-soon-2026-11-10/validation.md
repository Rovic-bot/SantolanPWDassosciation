# Public program registration closing notice

November 10, 2026. The owner requested a small “Closing soon” note on public program cards and program details during the final hour of registration.

## Behavior

The shared notice appears when applications are open and the registration deadline is at most one hour away. It includes the exact closing date and time in Philippine time. The start of the final hour is inclusive; the closing instant is exclusive. Program duration dates do not determine this notice.

Existing publication, eligibility-policy authorization and EWAF application-readiness checks still determine whether applications are open. Upcoming, closed, cancelled and unavailable programs do not show the notice. No application rules, saved program dates, models or migrations changed.

An open program whose deadline is more than one hour away receives a hidden notice. A small script reveals it when the final hour starts and hides it when registration closes, including after in-place catalog filtering and when returning to the page. Timing uses the server timestamp plus elapsed browser time, avoiding dependence on an incorrect device clock. Without JavaScript, the server renders the appropriate state at page load. This script only changes notice visibility; existing server checks continue to enforce application deadlines.

The notice uses the current public cream/charcoal palette, wraps on mobile and includes explicit high-contrast and forced-colors styling.

## Verification

The following command passed all **18 tests** using a fresh disposable MySQL database:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_public_deadlines programs.test_new_public_programs programs.test_public_requirements scripts.public_program_deadlines_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Coverage includes both pages at the one-hour boundary and deadline, registration versus program dates, unavailable states, EWAF readiness and midnight in Philippine time. Existing New-filter and published-requirement checks also passed.

Chrome checks passed on both pages at 1440px and 390px in light, dark and high contrast. Text contrast was at least 11.38:1, with no clipped notes or horizontal overflow. Browser-clock checks confirmed automatic appearance and expiry on both pages with a deliberately incorrect device date. In-place catalog filtering and no-JavaScript rendering passed. There were no JavaScript errors or write requests. Desktop light and mobile dark screenshots were visually inspected.

The local app was restarted. Read-only checks against `/programs/` and `/programs/ebc30248-516e-4ad4-a445-4972ec141fdf/` confirmed successful responses, loaded assets and the correct initial notice states. No application data was changed to make a notice appear. JavaScript syntax checks and `git diff --check` passed.

Evidence: `backend-tests.log`, `results.json`, `live-results.json` and the synthetic theme screenshots in this directory. The test database was destroyed after the run.
