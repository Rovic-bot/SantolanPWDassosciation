# Membership registration printing — 2026-10-26

The owner requested the local `Santolan_PWD_Membership_Form.docx` as the printing template and explicitly selected both registration submissions and approved member records. The original DOCX is unchanged, with SHA-256 `130e956120b8cead01f31522595ab65721314169dae68a650a24883ecfd73aab`. Its document XML, table rows, A4 dimensions, margins, and embedded logos were inspected. The accompanying blank PDF supplied the visual comparison; direct Word rendering was not performed.

## Behavior

- Applicant receipts retain their existing **Print / Save as PDF** action and the shared Word-form layout.
- Staff **View / print submitted form** now shows the actual paper-layout preview before printing.
- Approved member records include **Print registration form**, opening a private preview at `/members/<id>/registration/print/` with the same template. This uses the original application retained at approval, rather than silently replacing it with later member-profile edits.
- The printout retains the letterhead, exact extracted logos, paper checklist, 2-inch photo placeholder, field grid, declared selections, identification fields, and signature area. Current approved registration copies show the assigned member number and approval date below the form. Earlier revisions are not relabeled as the approved copy.
- Unknown fields remain blank. Older registrations retain unsplit names/addresses and unsupported choice labels as recorded; dependents are not treated as family size, generic College is not treated as graduation, and missing IDs are not invented. Household income, household size, and employment assessment fields remain excluded.

The paper checklist is reproduced from the supplied template. This change does not adopt its checklist as a new registration eligibility rule, alter required uploads, infer a PDAO-ID prerequisite, or change membership decisions, source data, historical references, EWAF rules, or the accepted milestone. The original Word file and blank PDFs are unchanged. No migration is required.

## Access and preservation

The member print route requires active staff dashboard access plus member-view and original-membership-application permissions. Registrations linked to online intake additionally retain the existing registration permission/policy checks and access audit. An audit failure prevents private delivery. Responses use `no-store`; anonymous requests redirect to login, and mutation requests are rejected. Existing registration receipt session binding and Finish revocation remain unchanged.

No real registration or member was created or modified for validation. The earlier test-runner portability fix and local-update validation notes remain preserved as separate unfinished work.

## Validation

The first focused run passed **42 tests** in a fresh disposable MySQL instance with `.env` disabled and isolated synthetic media:

```powershell
.venv\Scripts\python.exe -B scripts\g12_test_runner.py test members.test_registration_print membership.test_pdf_registration membership.test_registration_finish --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Two follow-up tests check that the current approved revision is labeled correctly and an earlier corrected revision is not; the current-revision test overlaps the initial run. These are focused checks, not a full-system acceptance run.

Headless Chrome rendered nine synthetic samples: applicant receipt, staff preview, and approved-member preview, each with ordinary values, empty optional fields, and long valid values. All print buttons called the print action, both logos loaded, and no populated field overflowed horizontally. PDF inspection and visual review confirmed A4 output and readable form fields. Ordinary and empty samples used one page; long samples continued to a second page without clipping. The 2-inch photo placeholder was 192 by 192 CSS pixels. Physical printer output was not tested.

Synthetic PDFs, screenshots, browser metrics, and extracted PDF text are retained under ignored `.local/membership-print-20261026/`. Examples are `member-ordinary.pdf`, `member-ordinary-screen.png`, `member-ordinary-page-1.png`, and `applicant-long-page-2.png`. These contain fictional information only.

Django database checks, the missing-migration check, and Git whitespace checks passed. The existing local server reloaded the changes. Home, login, and the updated stylesheet returned HTTP 200; the private member print route redirected an unauthenticated request to login. No public deployment, commit, or push was performed.

## Operator steps

For a pending registration, open its review and select **View / print submitted form**. For an approved member, use **Members → Member record → Print registration form**. Choose **A4**, **100% scale**, and disable browser headers/footers. Complete unrecorded onsite fields, the physical photo, and the signature on paper.
