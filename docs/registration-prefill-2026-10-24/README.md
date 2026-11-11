# Full applicant form and reference-based Admin prefill

2026-10-24. **Technical extension implemented and tested; operational intake remains gated. Phase 2B remains Partial; accepted milestone remains 70%.** Owner clarification: Public Membership should collect the applicant information shown in Admin Onsite Member Registration, issue an application reference, appear in an Admin inbox and load that same submitted information when staff enters the reference.

## Delivered flow

1. Under the explicitly configured expanded field contract, Public Membership opens the pending form with Address, Personal, Disability and Additional Information sections, using the existing onsite profile fields/choices/validation. Contact remains optional under the retained pending-intake contract.
2. Existing atomic submission/retry services retain the applicant's information in a pending revision and issue the same non-identifying AMR-UUIDv4 reference design. Receipt/print output includes every collected applicant field and frozen selected labels. Original same-session receipt access and Finish protections remain unchanged.
3. Existing Members > Membership Reviews > Pending Association registrations shows applicant, reference, channel, received date and processing state. Existing exact search and filters remain available.
4. **Onsite Member Registration > Already applied online? > Load online application** accepts the full AMR reference and opens the same retained pending application. All submitted applicant fields are populated in a read-only form. Authorized correction uses the existing reasoned, versioned correction workflow; it does not create another legacy application or Member.
5. Documents retain separate permission-checked links. Browsers do not prefill file-upload controls with private stored files. Lookup never marks an attachment, identity, classification, registry result or socioeconomic information verified.

The expanded form excludes the staff/government control number, PRPWD findings, decisions, manually entered status and exact-source monthly-income fields. It reuses the existing declared personal-income category; it does not add Household Monthly Income or change any EWAF criterion. Applicant disability selections remain declarations in pending JSON, not accepted Member classifications. No matching, Member creation, score calculation or assistance release is triggered.

## Contract and history compatibility

This implements the owner's technical clarification of D01. It does not invent Association collection authority or replace earlier historical approvals. The new explicit profile version is `applicant_profile = 'onsite_applicant_v1'`, with a nonempty, actually approved `applicant_profile_reference` and the appropriate updated form/field/privacy contract. No ordinary setting was enabled or supplied with fictional policy values. Existing minimal submissions and their original receipts remain supported. A change between minimal and expanded correction contracts is refused rather than silently discarding fields or guessing split names.

The existing required operating policy still needs actual authority/privacy/retention/staff/upload/onsite references and approved session, request, file/count/body and collision limits. Full-form collection additionally needs the approved field-purpose/privacy contract covering the reused profile sections. Owner technical approval is not institutional acceptance. The separate membership handoff remains blocked at service and database boundaries; no control number or government result is fabricated.

## Files changed

| Files | Purpose |
| --- | --- |
| `membership/registration_profile.py` (new) | Reuses the onsite profile mixin/model field definitions strictly for validation, blocks save, serializes applicant-only pending data, freezes display labels and creates read-only prefilled forms. |
| `membership/registration_forms.py`, `membership/registration_policy.py` | Explicit expanded field contract, grouped form rendering, multiple-choice validation, retained minimal form support and safe payload serialization. |
| `membership/registration_services.py` | Refuses corrections across incompatible field contracts; existing submission/reference/retry/writer logic retained. |
| `membership/registration_views.py`, `membership/urls.py` | Private GET-only lookup, generic invalid/unavailable reference results, audited detail delivery with populated form, and guarded correction rendering. |
| `membership/views.py`, `templates/membership/encode.html` | Gated reference-loading entry and inbox link on the existing Onsite Member Registration page. |
| `templates/membership/registration/detail.html`, `fields.html`, `submitted_data.html` | Populated applicant controls, grouped public/staff forms and complete historical receipts/revisions. |
| `templates/membership/registration/field.html`, `reference_lookup.html`, `lookup.html` (new) | Shared accessible field/group rendering and staff-only lookup components. |
| `static/css/registration.css` | Scoped fieldset/control sizing and text wrapping to fix 200% mobile overflow. No sidebar/style redesign. |
| `membership/test_registration_prefill.py` (new) | Eight integrated security, receipt, same-record lookup, full-field validation, legacy compatibility, retained-choice, audit and correction tests. |
| `scripts/registration_prefill_browser.py`, `.cjs` (new) | Isolated synthetic end-to-end browser demonstration and responsive/keyboard evidence. |
| This report/evidence and the existing progress record | Current outcomes/remaining decisions; earlier evidence retained. |

No new migration, model change, dependency, staff grant, ordinary configuration, credential, working-database migration or protected writer modification. The already authorized local server was restarted through the unchanged startup guard to load the code. Current schema migrations applied in the previous authorized startup task were not rerun here.

## Actual validation

All database tests used fresh verified G12 MySQL instances, disabled `.env`, synthetic data and separate temporary private media.

| Log | Actual result |
| --- | --- |
| `final-tests.log` | **109 passed, 39.208s**: new extension, existing pending intake/Finish, inbox/migration lifecycle, ordinary membership workflows, public navigation and full browser journey. |
| `ewaf-regression.log` | **102 unchanged EWAF tests passed, 80.277s**: criterion histories/formulas, strict CR, normalization/scoring, operational/decision/release controls and existing membership/access writers. |
| `browser-final.log` | **1 passed, 14.350s**: repeated browser-only run for top-of-page evidence captures. Counts overlap the preceding run. |
| `targeted-tests.log` | Initial 108-test run: one error in the new test helper's duplicate keyword arguments. Fixture corrected; no engine assertion changed. |
| `validated-tests.log` | Next 109-test run: one actual browser layout failure at 200% text on a narrow screen. Scoped registration CSS corrected it; final assertions were retained. |

Commands:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.test_registration_prefill membership.test_registration_intake membership.test_registration_finish membership.test_registration_completion membership.tests core.tests.test_public_portal scripts.registration_prefill_browser --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_computation_reference ewaf.test_four_criterion_reference ewaf.test_ahp_validation ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_four_kernel ewaf.test_operational ewaf.test_delivery ewaf.test_membership_writers ewaf.test_access_writers --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test scripts.registration_prefill_browser --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
```

Browser evidence includes 16 responsive checks (four journeys at 320/390/768/1440px), keyboard submission/reference lookup, no duplicate element IDs, 200% Admin text reflow, denied anonymous reference lookup, and Finish revocation. Test assertions confirm one retained intake/revision and zero legacy MembershipApplications/Members. The private completed form cannot be retrieved by reference alone. No representative screen-reader, full contrast, institutional UAT or WCAG certification is claimed.

See [public applicant form](ui-final/public-full-form.png), [reference receipt](ui-final/reference-receipt.png), [Admin inbox](ui-final/admin-inbox.png), [prefilled Admin application](ui-final/admin-prefilled-form.png), [enlarged mobile view](ui-final/admin-prefilled-mobile.png) and [browser checks](ui-final/checks.json). All shown data and policy values are explicitly synthetic.

All 267 protected files and original/integrated Section 8 remain unchanged. Existing/new migration files retain their reviewed hashes; no model/schema change was required. The local homepage and Membership page return 200; disabled public submission returns 503, and anonymous new staff lookup redirects to login. These are limited read-only smoke checks, not real-member-data tests.

The benefit is preserving the applicant's entered information across receipt, monitoring and staff review without retyping or duplicate encoding. Risks/limits remain expanded sensitive-data collection if someone later enables it without authority, unverified declarations being mistaken for accepted evidence, and unresolved membership handoff. The default-off contracts and clearly separate review/history paths remain essential. No public tracking/recovery, PDAO processing, new accounts, notifications, deployment, commit, push or milestone increase was introduced.
