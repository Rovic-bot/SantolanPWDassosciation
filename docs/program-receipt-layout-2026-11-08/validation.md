# Program application receipt layout — November 8, 2026

## Authorized change

The owner requested the program submission receipt shown in their reference image: a light gray canvas, green success mark, prominent confirmation heading and program name, reference card, numbered next steps, and a separate tracking/QR card. The existing public tracking implementation and session-bound receipt remain in use.

The receipt now uses two columns on larger screens and stacks on smaller screens. The reference has a keyboard-accessible copy control with live feedback and a text-selection fallback when clipboard access is unavailable. A print control opens the browser's print dialog; the receipt guidance expands for printing and restores its previous state afterward. Controls, public navigation and footer are omitted from print output. Without JavaScript, the selectable reference, browser printing instructions, QR and tracking link remain usable.

The office-visit instruction for changed or historical uncertain information, original reference, Results link, publication/eligibility guidance and privacy information are retained. No application submission, selection, release, reference allocation, tracking authorization or database schema logic changed.

## Verification

- `scripts/current_development.py check`: no issues.
- Existing public receipt and tracking tests: 27 passed in the initial focused run, covering session isolation, independent tracking/QR switches, private response headers and limited public tracking information.
- Four old information-change receipt tests initially failed before reaching the receipt: they uploaded an unlisted calendar photo and submitted the retired `uncertain` choice. Their fixtures now use the current form; a separate historical declaration still verifies the retained uncertain-information notice. The fixture supplies an existing member email so its unchanged-record assertion isolates the receipt instead of the current blank-email capture behavior.
- Final focused run: all 4 updated information-change receipt tests and the browser test passed (5 tests). Together with the unaffected 27 tests above, all 32 targeted tests passed across the focused runs.
- Headless Chrome checked 1440, 1024, 768, 390 and 320px: expected columns/stacking and no horizontal overflow. Desktop and mobile screenshots were visually reviewed.
- Browser checks passed for keyboard copying, clipboard-denied text selection, tracking popup with prefilled reference, real session-bound QR loading, print control, print guidance, and JavaScript-disabled fallback. No JavaScript errors. Synthetic application and member records remained unchanged.
- `git diff --check` and JavaScript syntax checks passed.

All tests used a newly initialized disposable MySQL instance with `.env` loading disabled and temporary private media. No real application was submitted or edited. No migration is required.

## Reproduction and evidence

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_public_receipt programs.test_change_receipt programs.test_tracking scripts.program_receipt_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Initial artifacts: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-2_mqi_ta`.

Final focused run: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-n3sgtjq2`.

Retained fictional screenshots: [desktop](receipt-1440.png), [mobile](receipt-390.png), [high contrast](receipt-contrast.png). [Browser results](results.json). All references and QR codes in these screenshots are disposable test fixtures.
