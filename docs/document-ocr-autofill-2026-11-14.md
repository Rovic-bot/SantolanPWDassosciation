# ID and receipt autofill — November 14, 2026

The owner requested scan/upload autofill in the deployed PDAO and Association applications using Tesseract. This change is based on the actual deployed branch `deployment/free-render-supabase`, baseline `c76e5d046c1cd50fa6aed0299643579fc6bd4d67`. The October 10 requirements, development guide, confirmed membership/PDAO amendment, DEC-027, Open Decisions, implementation-impact note, current deployment record and later intake validation were checked. This request authorizes optional transcription on the existing application forms; it does not change their submission or decision rules.

## Behavior

Both public application forms and both onsite staff intake forms offer **Fill from an ID or receipt**. Users can choose a JPG/PNG/WebP image up to 12 MB or capture a photo with a permitted camera. Camera denial/unavailability offers an image/phone-camera fallback. Users can rotate, clear or cancel the scan. Images exceeding 40 million decoded pixels are rejected and accepted images are reduced to a maximum 2,400-pixel edge before recognition.

Tesseract runs on the user's device through the pinned Tesseract.js worker and WebAssembly engine. The page downloads the engine and English integer language model only when reading is requested. All assets are hosted by the application. No scan image, filename or raw extracted text is uploaded, attached, persisted to local storage/IndexedDB, or logged by the feature. The worker is terminated on completion, error, cancellation, a 90-second timeout and navigation. Camera tracks stop after capture, closing, hiding or leaving the page.

The review panel offers editable suggestions for supported, explicitly labelled personal fields. It recognizes English and selected Filipino labels, clear dates, address components, contact details and specifically labelled existing ID numbers. Receipt mode requires applicant/customer labels, so a store address/phone or payment reference is not substituted for applicant information. National-ID/receipt numbers are never assumed to be PWD numbers. Conflicting labels, ambiguous numeric dates, uncertain ID characters and unclear address/name divisions require manual review. Raw extracted text remains available on the page for completing other fields. The feature cannot recover information that is absent or unreadable.

Only checked suggestions are copied. Existing values begin unchecked; fields changed after scanning are kept and unchecked again, requiring a deliberate selection before replacement. Undo restores only values that have not subsequently been edited. Acknowledgements, supporting attachments, household assessment data and processing decisions are outside the autofill allowlist. Existing Django validation, privacy confirmation, permissions, evidence handling and audit/decision services continue to apply on submission. Forms remain usable without JavaScript or OCR. No models, migrations, permissions, records, approval emails or government integrations are changed.

## Validation

- Ten Node parser tests pass, covering PWD and bilingual National-ID labels, leading zeroes, customer-only receipts, rejected ambiguous/invalid dates and identifiers, conflicting labels, missing information, family-name boundaries and unrelated issue dates.
- Two Django `SimpleTestCase` checks pass, rendering all four actual application templates and verifying the optional scanner adds no named, required or submit controls. The test launcher disables `.env` and uses Django's dummy database backend. No application or test database is accessed.
- Eleven Chrome browser journeys pass on the actual rendered forms, including real Tesseract extraction from fictional ID/receipt images, reviewed autofill, explicit replacement/undo, later manual-edit protection, original form-field parity, acknowledgement preservation, 1440/390/320-pixel layouts, synthetic camera capture and track release, camera denial, corrupt images, cancellation during initialization, failed language downloads and no-JavaScript fallback. No JavaScript errors, form submissions or external OCR downloads occurred. Desktop/mobile/light/dark screenshots were inspected.
- JavaScript syntax and whitespace checks passed. The vendored versions, licenses and SHA-256 manifest are retained under `static/vendor/tesseract/6.0.1/`.

Fictional-document screenshots: [Association desktop](document-ocr-autofill-2026-11-14/association-desktop.png), [PDAO mobile](document-ocr-autofill-2026-11-14/pdao-mobile.png), [dark mobile](document-ocr-autofill-2026-11-14/dark-mobile.png).

Reproduction from the intended checkout, using the project virtualenv Python:

```powershell
node --test scripts/document_ocr_parser_test.cjs
$env:OCR_ARTIFACT_DIR = Join-Path (Get-Location) '.local/ocr-fixtures'
python scripts/document_ocr_checks.py
$env:OCR_FIXTURES = $env:OCR_ARTIFACT_DIR
$env:OCR_ARTIFACT_DIR = Join-Path (Get-Location) '.local/ocr-browser'
node scripts/document_ocr_browser.cjs
git diff --check
```

The browser harness uses the existing Playwright/Chrome installation or the `PLAYWRIGHT_MODULE` / `CHROME_EXECUTABLE` overrides. It blocks application submissions. Setting `OCR_URL` selects the two public routes for a hosted smoke test using fictional documents, without submitting an application.

OCR accuracy varies with document layout, resolution, lighting and handwriting. PDF/HEIC input requires conversion to a supported image. These checks establish the tested functionality, not universal ID-layout coverage, physical camera quality, full mobile-device compatibility, WCAG certification or automatic identity verification.
