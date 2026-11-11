# Admin newly published program filter

November 10, 2026. The owner requested the same one-hour New filter in the admin Program portfolio's Status dropdown.

## Behavior

- Status now includes **New (last hour)** at `/admin/programs?status=new&sort=newest`. The existing management-route aliases expose the same portfolio.
- Admin and public browsing share `publication_recency.newly_published_condition`: currently published, publication time no later than now and strictly later than one hour ago. Exactly one-hour-old programs leave New on the next filter request or reload. Creation and editing dates do not restart the window.
- The default `newest` sort uses publication time while New is selected and is labeled **Newest published first**. Other statuses retain **Newest created first**. The label updates during in-place filtering; explicit alphabetical/date sorts remain usable.
- New combines with search, category, registration period, with-applications and pagination. An empty result explains the one-hour window.
- New is a browsing filter, not a stored program status. Cards retain Published, and publication, eligibility, ranking, selection, capacity and permission rules are unchanged.
- The addition is enabled for the Program portfolio; unrelated shared admin program selectors retain their existing choices. Public New behavior is unchanged apart from using the shared window helper.
- No model/schema migration, periodic task, real publication or application-data update was needed.

## Verification

Seventeen distinct focused tests passed across the main and targeted rerun, using fresh disposable MySQL instances through `g12_test_runner.py` and `RegistrationIntakeTestRunner`:

- Seven new admin tests cover publication ordering, exact boundaries, agreement with public New, hidden/future/cancelled records, expiration, combined filters, pagination, unchanged other statuses and admin/capacity permissions.
- All six public New regressions passed after extracting the shared condition.
- Three existing portfolio filter, pagination and permission tests passed.
- One read-only browser test exercised the real protected admin view with synthetic data: selecting New, in-place results, current Published labels, dynamic sort labels, alternate sorting, search, empty results, reset and a no-JavaScript GET form.

The initial run passed 16 tests. Its expiry test advanced the clock by one hour, which correctly also expired the synthetic staff session. The test was corrected to reauthenticate before checking the filter; the targeted rerun passed. No production session rule was changed.

Browser checks covered light, dark and high contrast at 1440px and 390px without horizontal overflow. Desktop light and mobile dark screenshots were visually inspected. The browser recorded no JavaScript errors or write requests. All created records and sessions were confined to disposable test data, and both test databases were destroyed afterward.

JavaScript syntax checks, Django system checks and `git diff --check` passed. The retained local app was restarted. Evidence is included as backend logs, `results.json` and theme screenshots.
