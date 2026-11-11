# Membership form print template — 2026-10-25

The owner's request authorizes using `Santolan_PWD_Membership_Form.docx` for membership registration printing. Its SHA-256 is `130e956120b8cead01f31522595ab65721314169dae68a650a24883ecfd73aab`. The original Word document and both existing blank PDFs remain unchanged.

## Implementation

The applicant's same-session receipt and the staff revision print page now include a shared print-only layout for `association_pdf_v1` submissions. It follows the Word document's letterhead, logos, checklist, personal/family information grid, disability and education choices, identification fields and signature area. Both logo assets are byte-for-byte extractions from the DOCX. The browser uses the existing Print / Save as PDF button. Print settings are A4, 100% scale, with browser headers/footers disabled.

The layout reads the retained revision directly. Dates display as MM/DD/YY; stored ages and explicit zero family counts are preserved. Only declared options are checked. The physical-requirements checklist, registration date, photograph and signature remain for onsite completion. The photo box is sized to 2 inches square. A small registration-reference/revision and pending-review notice accompanies the form. The existing accessible screen summary stays available, while printing hides navigation, receipt instructions and controls.

Household income, household-member count and employment status stay excluded from the print HTML. PDAO printing, earlier registration contracts, saved source data, permission checks, audit actions, Finish revocation, membership decisions and database schema are unchanged. No assessment or checklist-acceptance policy was changed by transcribing the supplied template.

## Verification

- 75 existing focused tests passed in a fresh disposable MySQL instance with `.env` disabled and separate synthetic media. Suites: `membership.test_pdf_registration`, `membership.test_registration_intake`, `membership.test_registration_finish`, and `membership.test_registration_prefill`, through the existing `RegistrationHandoffTestRunner`. Django system checks passed.
- Six synthetic HTML samples cover applicant and staff pages with ordinary values, long valid values and empty optional values. Additional checks cover date formatting, explicit zero, four selected options in the populated example, unmarked document requirements, reference retention, logo paths, digital-field exclusion, escaping and legacy fallback.
- The source logo bytes were compared with the extracted assets. Whitespace checks passed, including checks of the new untracked text files.
- The existing local website still responds on port 8003. HTTP responses for the new stylesheet and both logos exactly match the repository assets.

The DOCX was inspected through its XML, table structure and embedded images, and the existing matching blank PDF was rendered for a visual reference. Direct DOCX rendering was unavailable because LibreOffice is absent; Word automation produced no render. Browser launch also failed with Windows access errors, so **final browser rendering, pagination, long-value overflow and physical printing have not been visually verified**. No screenshot or browser-test pass is claimed.

## Development runtime

Only the five print templates, one stylesheet and two logo assets were copied to `.local/dual-registration-20261024/runtime/`. Existing templates were backed up under `.local/membership-print-20261025/runtime-before/`; synthetic samples and verification metadata are in that same ignored task directory.

The existing restart script verified the current development instance, but Windows denied stopping its Python process. The website remains running; run `Restart System.cmd` to reload the updated templates. No database mutation, migration, commit, push or deployment was performed.
