# Rotated National ID scan correction — November 14, 2026

The owner reported that a sideways Philippine National ID screenshot produced no usable scan results in the deployed application. This correction extends the optional transcription feature recorded in [the original implementation and activation record](document-ocr-autofill-2026-11-14.md). The deployment baseline is `16056a5a9779ecebfcdf8d1cbca1948edaf44099`; the currently deployed feature before this fix was code commit `9dfb5e3be51808abe8e69d9616ee1b6760625080`.

## Cause and correction

The original reader treated the whole image as an upright text block. A phone screenshot can instead contain a sideways card, small bilingual labels, a portrait, a QR graphic and app controls. Even after rotation, plain OCR reading order can place unrelated graphic fragments between a label and its value.

The reader now checks the four right-angle orientations, enlarges small text within a 3,400-pixel edge limit and uses sparse-text recognition for ID cards. It stops early when the labelled first name, last name and birth date are available. Receipt mode retains block recognition and its customer-only field rules. Progress messages show orientation passes; the image preview turns to the chosen direction automatically.

The parser pairs recognized labels with nearby aligned text using Tesseract's bounding boxes. It handles bilingual labels with missing slashes/spaces, retains a complete known label when an individual Filipino word has a weak confidence score, and filters weak graphic fragments from values. Missing values are not borrowed from the next labelled field. A detected National ID address is re-read in a small crop with its pale security background suppressed. Address components use the recognized comma-separated National ID layout; the implementation contains no person-specific text or fixed screenshot coordinates.

Suggestions remain editable and require the user's selection before insertion. A National ID number is not put into the PWD-number field. No image or raw OCR text is uploaded by the scanner. The existing cancellation, timeout, camera cleanup, overwrite protection and manual-entry behavior remain in place. This change adds no migrations and changes no application submission, evidence, identity verification or approval rules.

## Local validation

- Fifteen parser tests pass, including geometry, merged bilingual labels, low-confidence label words, missing-value boundaries, graphics/initials, date validation, identifiers and receipt customer details.
- Two database-free Django template checks pass for all four actual public/staff forms. No database was initialized or accessed by these checks.
- Thirteen Chrome browser scenarios pass using the actual rendered forms and real Tesseract. The suite now includes fictional National ID-style phone screenshots rotated 90 and 180 degrees, checking nine extracted personal fields. Existing reviewed autofill, replacement/undo, later manual edits, receipt handling, responsive layouts, synthetic camera release, denied camera, corrupt input, cancellation, failed downloads and no-JavaScript fallback checks pass. No JavaScript errors, form submissions or external OCR downloads occurred.
- The owner's supplied image was tested only on this computer. The reader matched all nine checked personal/address fields. On the actual rendered forms, all nine available Association fields and all eight available PDAO fields matched, the PWD-number field stayed empty, and acknowledgements remained unchecked. No application was submitted. The supplied image, personal text, diagnostic OCR output and private comparison scripts are excluded from the repository and published evidence.
- JavaScript syntax and `git diff --check` pass. The mobile review screenshot was visually inspected.

Public regression evidence uses fictional data only: [browser checks](document-ocr-rotation-fix-2026-11-14/local-validation.json) and [rotated-card review](document-ocr-rotation-fix-2026-11-14/fictional-rotated-card.png). Use the reproduction commands in the original implementation record; `scripts/document_ocr_card_fixture.cjs` generates the new fictional artwork.

This validates the supplied example and the documented regression cases. Unreadable or absent information still needs manual entry; OCR suggestions must be reviewed before submission.

## Hosted activation

Render deploy `dep-dbs1adbbc2fs73aa208g` reached **live** at 08:02:24 UTC on November 14, 2026, running code commit `0ef357b60a11bea6a1c6413b2c2bbed0172cad62`. The existing service configuration and database were retained. The health endpoint returned HTTP 200 with `status: ok`.

Eleven hosted Chrome scenarios passed against the public Association and PDAO application pages, including real Tesseract recognition, reviewed autofill, both rotated fictional card cases and the existing fallback/cleanup checks. There were no JavaScript errors, POST requests or external OCR downloads. Render returned no application error logs between activation and the 08:03:40 UTC check. The hosted mobile review screenshot was inspected. No real application was submitted and no member email was sent.

Hosted evidence contains fictional data only: [browser checks](document-ocr-rotation-fix-2026-11-14/hosted-validation.json) and [rotated-card review](document-ocr-rotation-fix-2026-11-14/hosted-fictional-rotated-card.png). Task-generated private OCR diagnostics and comparison scripts were removed after local validation; the owner's supplied source image was not modified. This activation record is a documentation-only follow-up to the deployed code.
