# Program receipt popup and image downloads — November 8, 2026

## Implemented

After a successful program application, the existing AJAX flow now opens the session-bound receipt in a modal over the completed application page. The submitted form is replaced by a confirmation with View receipt and a full-page fallback link. Closing and reopening the popup does not resubmit the application. Direct receipt URLs also open the popup; without JavaScript, the server-rendered receipt remains readable with the existing tracking/print instructions.

Save as PNG and Save as JPEG generate a 2400px-wide receipt locally in the browser. The export includes the program, original reference, numbered steps, existing QR code and tracking address, eligibility disclaimer, and any required office-visit notice. Text wraps and the image expands for longer titles/notices. Navigation, popup controls and private submitted answers are excluded. No screenshot provider, new dependency, upload, server-side image storage, database model or migration is involved.

The popup retains reference copying, tracking, Print receipt, accessible labels, focus containment, Escape/close and focus restoration. About this receipt remains reachable by keyboard. Receipt contents and their listeners are removed on close. Loading failures offer a GET retry or the existing receipt page; successful submission is not reported as failed and the form is not submitted again. Image failures retain print access and permit retry.

## Validation

- The existing public-receipt, information-change receipt and tracking modules passed all 31 tests in the initial run. Session isolation, flags, original references and private response headers remain unchanged.
- The final `scripts.program_receipt_browser_qa` run passed both browser tests. These cover ordinary receipt access and a real synthetic public submission, including an intentionally failed first receipt fetch. Exactly one application POST and one stored application were confirmed after retry and reopening.
- Download events produced actual PNG and JPEG files with the original reference in their filenames. File signatures and Pillow decoding verified their formats and 2400px widths. Both exports and the longer office-visit export were visually reviewed.
- Chrome checks passed at 1440, 1024, 768, 390 and 320px with no horizontal overflow, plus keyboard opening of the guidance, nested tracking, copying/clipboard fallback, printing, image-failure recovery, close/reopen and JavaScript-disabled fallback. No browser errors. Member records remained unchanged.
- The final targeted result is 33 distinct passing tests across the initial 31-test coverage and the two final browser checks.
- The older combined `scripts.program_application_browser_qa` reached and passed its application retry, receipt popup, anonymous tracking and admin review portions. Its existing schedule and registration-tab assertions were aligned with the current UI, but it still fails later on unrelated EWAF readiness-label expectations. That broad historical harness is not claimed as fully passing; no EWAF implementation changed here.
- Django system check, JavaScript syntax checks and `git diff --check` passed.

All fixtures used fresh disposable MySQL with `.env` disabled. No live application, membership decision or assistance release was created or changed.

## Reproduction and evidence

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_public_receipt programs.test_change_receipt programs.test_tracking scripts.program_receipt_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Initial coverage: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-g9h33_kr`.

Final browser artifacts: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-cwspqkno`.

Evidence uses fictional applications and disposable QR destinations: [desktop popup](receipt-1440.png), [mobile popup](receipt-390.png), [PNG export](receipt-export.png), [JPEG export](receipt-export.jpeg), [office-visit export](changed-information.png), [browser results](results.json), [submission results](submission-results.json).
