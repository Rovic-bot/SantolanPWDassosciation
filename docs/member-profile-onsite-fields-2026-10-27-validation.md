# Member profile editor aligned with onsite registration

Date: October 27, 2026. Branch: `EWAF-testing`. Local implementation only.

## Authorized change

The owner requested that member-information editing use the same fields as Admin onsite member registration. The current onsite route is `/membership/applications/new/`, backed by `OnsiteRegistrationForm` and `AssociationPDFForm`; the older `ApplicationForm` is not the current field contract.

`/members/<id>/edit/` now uses the same applicant field definitions, labels, choices, required states, groups, numeric ID/contact behavior and calculated age as current onsite intake:

- Personal information.
- Address and contact information.
- Family information.
- Disability and education.
- Existing identification, including the onsite-required PWD number.
- Household income, household size and employment status.

The member editor retains its staff update-reason field and existing additive private-document controls. It does not request another applicant acknowledgement. Historical choice labels and numeric-string exceptions may remain visible for a member who already has those recorded values; newly changed values follow the current contract.

## Files and preservation

- `members/registration_form.py`: current field contract, prefilled values and projection into the existing Member columns/JSON. No guessing how to split older names/addresses or deriving household size from dependents.
- `members/views.py`: select the aligned editor; existing permission and response handling retained.
- `members/services.py`: save through the existing locked, versioned transaction and audit writer. Reload persisted JSON/decimals before auditing so independent source-writer checks see exactly the same values.
- `members/profile.py`: include current registration declarations and household fields in the private change snapshot.
- `templates/members/edit.html`: reuse onsite field sections and numeric/age script in the existing Admin layout. Earlier recorded information is available in a disclosure.
- `members/test_registration_edit.py`: ten focused tests for the current form and source-writer integration.

Original approved applications, registration revisions and original printed registrations remain unchanged. Existing individual income, dependents, suffixes and older fields remain stored. A family/contact-only edit retains existing disability classifications; an explicitly changed disability declaration uses the already-existing exact-label projection, without inferring alternative classifications. An audit event retains previous values.

Older already-open forms and existing service callers without the new form marker retain the legacy parser. Existing permissions, archived-record restrictions, optimistic versions, upload protection, rollback and program-source invalidation remain in place. No schema, migration, credentials, EWAF formula, approval or selection changes.

## Verification

The final focused run passed **57 tests**, using a new loopback MySQL 8.4 instance, disposable schema and private synthetic media. The running preview database was not a test target. Historical migrations were not executed.

```powershell
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test members.test_registration_edit members.tests members.test_registration_print membership.test_onsite_registration_alignment ewaf.test_member_writers --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Result: `Ran 57 tests in 29.130s — OK`. Artifacts: temporary directory `santolan-g12-tests-nk9dckz6`.

Coverage includes field parity and prefills; family-only updates; household and common columns; original-application preservation; required reason, dates and number validation; duplicate formatted IDs; permission denial; stale versions; archived records; no-op rejection; audit failure rollback; retained suffixes/choices/classifications; and the existing source invalidation/audit/concurrency suite. A new integration check verifies that current-form JSON/household changes pass the existing source writer and invalidate the retained program generation.

An earlier broader run of 49 tests had 48 passes and one unrelated legacy expectation failure: `membership.test_onsite_profile.OnsiteProfileTests.test_name_suffix_choices_dependents_and_managed_disabilities_validate` expects `employment_status='unemployed'` to be invalid. Current registration supports that choice. That test and its form/choice definitions are unchanged by this task; this historical expectation was left untouched.

Browser checks used Chrome/Playwright with unsaved fictional records rendered through the actual templates. SQL writes and browser POST requests were prohibited. Five scenarios passed: desktop 1440px, tablet 768px, mobile 390px and 320px, and 1280px with 200% CSS zoom. The checks compared every applicant field against onsite registration, verified prefills and leading zeroes, calculated age, keyboard traversal/disclosures, numeric filtering, native validation, server-error links and retained inputs. No horizontal overflow, clipped form controls or JavaScript errors were found. Desktop and mobile screenshots were visually reviewed.

- [Desktop editor](member-profile-2026-10-27/edit-desktop.png)
- [Mobile editor](member-profile-2026-10-27/edit-mobile.png)

Read-only Django/database system checks passed, no model changes were detected, pending migrations were zero, and `git diff --check` passed. The local development server was restarted after the final changes.

## Preview and limits

Open `http://127.0.0.1:8000/members/`, sign in with an authorized staff account, select a member, and choose **Edit member**. The editor is `/members/<id>/edit/`.

Browser review used fictional presentation fixtures; persistence, protected history and authorization were tested in disposable MySQL through Django HTTP/service tests. No real member was edited for verification. Older records that lack separated names/addresses or household fields require staff to supply the current required details; the editor presents retained information rather than inventing missing data. The full project test suite was not run. No push, merge or deployment was performed.
