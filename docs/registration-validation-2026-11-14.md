# Registration validation — November 14, 2026

The owner requested matching, searchable Philippine addresses and stronger required-field rules on the deployed public Association, public PDAO, onsite Association and onsite PDAO intake forms. This release starts from deployment branch baseline `51eb82e` (live application code `0ef357b`). The October 10 target, development guide, membership amendment, DEC-027, Open Decisions, implementation-impact note and later intake/deployment evidence were reviewed. The current request authorizes these scoped changes to the existing deployed intake.

## Behavior

- City/municipality, region, province where present, and barangay have typeable native dropdown suggestions. Selecting a city fills its region/province; changing the city clears the previous barangay. Server validation rejects unknown places and incompatible combinations, including Manila with Region III. Repeated city names include their province. NCR uses an explicit no-province option. House/street remains typed. Association ZIP codes require four digits; ZIP-to-street delivery coverage is not inferred from PSGC.
- The application hosts a pinned June 2026 PSGC catalogue: 18 regions, 1,642 cities/municipalities and 42,010 barangays. Source attribution appears with the city field. Geographic names/codes are from [PSA PSGC](https://psa.gov.ph/classification/psgc), transcribed by [Tenasia/ph-psgc 2026-Q2](https://github.com/Tenasia/ph-psgc/tree/2026-Q2), commit `3d7528b6625e4e7990ac1b96d89505a6bab157ec`. Only names/codes are included. The index is loaded once and barangays load by selected city. No applicant information goes to an external address API. Later geographic changes need a reviewed catalogue update.
- All four forms require house/street, city, region, barangay, mobile, email, birth date, civil status, education, employment status and disability type. Association additionally requires ZIP, nationality, gender, family count and a Yes/No 4Ps answer. PDAO additionally requires its province/no-province choice, sex, disability cause and emergency contact name/relationship/mobile.
- Association spouse name/mobile are required when Married. Parent/guardian name/mobile are required under 18, or together when either is supplied. PDAO renewal requires the existing PWD number; employment category/nature/occupation are required for Employed, occupation for Self employed, and a description for Other occupation. Association education includes None / Not yet in school for young applicants.
- Mobile fields show a fixed +63 prefix and accept ten national digits starting with 9. The domestic leading zero is omitted, while zeros inside a number remain valid. Saved values use +639xxxxxxxxx. Recognized complete domestic/international clipboard and OCR numbers are normalized into the ten-digit input; letters and excess digits cannot be typed. OCR suggestions remain reviewed before application.
- Applicants must be at least five on the application date, checked on the server and through the date input maximum. Age displays still calculate actual age rather than incorrectly using the five-year cutoff as today.
- New PDAO application dates are disabled on the page and set from server-side Philippine local time, ignoring posted overrides. A form submitted after midnight receives the current date. Same-token retries keep the first saved date, age, reference and record, while changed applicant details remain rejected.

Middle names/suffixes, absent landlines, optional identifiers/organization information and non-applicable cause details remain optional. Existing attachment/physical-document handling and acknowledgements remain intact. These rules validate declared address relationships, not residence or identity authenticity. Existing review/correction forms and historical data retain their previous contracts and dates.

## Validation

- **69 focused Django tests passed** on fresh disposable loopback MySQL with separate `test_g12_disposable`, fictional data/media and project .env disabled. Coverage includes all four form contracts, matching geography, repeated names, mobile validation, fifth-birthday/leap-day boundaries, married/minor/renewal/employment conditions, server-fixed dates, same-token retry across midnight, permissions, CSRF, audit rollback, original record preservation, correction history, same-request concurrency and approval handoff.
- **13 database-free tests passed**, including all four actual template renders and full catalogue totals/unique city labels.
- **6 Chrome scenarios passed** across the four rendered forms at 1440/390/320 px, including address changes/mismatch rejection, mobile typing/OCR normalization, age, conditional required fields, PDAO locked date, failed catalogue download and no-JavaScript fallback. No JavaScript errors or application POSTs. Screenshots were inspected and the mobile country-code layout corrected.
- **15 OCR parser tests and 13 real Tesseract browser scenarios passed**, preserving reviewed autofill, replacement/undo, rotated fictional IDs, fallback and cleanup.
- Django checks, JavaScript syntax, `makemigrations --check --dry-run` and `git diff --check` pass. No model/migration change.

The first broader test selection included an outdated historical migration rehearsal whose missing later dependent tables corrupted that disposable test schema. The final run uses the applicable application/concurrency classes on a fresh schema and excludes that rehearsal because this release has no migrations. Fixtures were updated for current mandatory intake and retained UI/review contracts; application permission and audit controls were not relaxed.

Reproduce from the release checkout with the project virtualenv Python:

```powershell
$env:OCR_ARTIFACT_DIR = '<private synthetic fixture directory>'
python scripts/registration_validation_checks.py
$env:INTAKE_FIXTURES = $env:OCR_ARTIFACT_DIR
node scripts/registration_validation_browser.cjs
node --test scripts/document_ocr_parser_test.cjs
```

The database suite uses the existing fresh-instance `g12_test_runner.py` with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`; select `membership.test_pdao_registration.PDAORegistrationTests` and `PDAOConcurrencyTests` rather than its historical migration class. This validates tested Chrome flows and synthetic workflow behavior, not full device/accessibility certification.

## Deployment

No database migration, data import, application submission, notification send or service-plan change is part of this release. Hosted activation evidence will be recorded after Render reports live and the public forms pass the read-only browser checks.
