# Separate Association and PDAO forms — 2026-10-24

Implemented in the repository and running in the existing populated **fictional-data** environment at **http://127.0.0.1:8003/**. The public entry is `/membership/register/`. `Start System.cmd` now resumes this updated local runtime through `scripts/run-current-development.ps1`. This does not authorize production applicant collection or change the accepted 70% milestone.

## Owner authorization and sources

The owner requested separate public Association membership and PDAO PWD ID forms, three channels (online, printed onsite, walk-in), required in-person verification, Association references, and printing for both. The later clarification explicitly says **“Use the PDF’s checklist and quantities too.”** This supersedes the older DEC-027 Association checklist for the new form contract; the old checklist, submitted payloads and snapshots remain retained for historical contracts.

The supplied originals remain byte-for-byte unchanged:

- `Santolan_PWD_Membership_Form_A4_Fixed.pdf`: SHA-256 `a7bc117e2bdfaee635a94dbf85d3150ebc228bcd5b2ce9ad7a45fa0123d7e78f`.
- `PWD ID Application Form (2024-2025) (New And Renewal).pdf`: SHA-256 `2d49372714d3b557619facebf7106ad1bfdb3aede82f3dccce25959437a415d2`.

Both PDFs were extracted and visually inspected with Poppler. Both supplied Adobe links remain accessible from the guidance page; the browsing tool could not read them, so field transcription uses the supplied local PDFs. Blank downloads serve only these two allowlisted files.

## Behavior

- Home has an Integrated Digital Services shortcut. The detailed Membership & Registration for PWD ID page explains both options, requirements, online/printed/walk-in channels, privacy, and verification.
- Association fields follow the supplied Membership Form: personal/address/contact details, family count, spouse/guardian contacts, 4Ps declaration, one disability classification, education and existing identifiers. Age is derived; signature, photograph and date registered are completed on paper/onsite. Missing optional data can be completed onsite. These declarations do not become verified Member attributes or EWAF inputs automatically.
- New Association submissions retain a versioned `association_pdf_v1` payload in the existing private pending-intake workflow, receive an immutable AMR reference, and support same-session printing. Existing staff access, audit rollback, retry/idempotency, Finish revocation and native approval controls remain in place. Public references alone cannot retrieve private information.
- Bring the completed Membership Form **plus** the PDF’s five checklist items: one long brown envelope; four PWD ID photocopies; two Voter’s Certificate photocopies; two Birth OR Marriage Certificate photocopies; four 2×2 photographs with white background. New PDF-contract onsite findings cover the completed form and all five items, including the PWD photocopies. No envelope upload or automatic scan requirement is introduced.
- PDAO collects the source form’s new/renewal, identity, address/contact, disability/cause, education/employment, organization/ID, family, preparer and emergency-contact fields. POST validates and returns a printable HTML copy containing the PDAO consent text, signature line and requirements. It creates no registration, reference, session payload, document file, Member or external PDAO submission. A new GET is blank. PDAO remains responsible for ID issuance/renewal and in-person verification.
- Both submitted forms support the browser’s Print / Save as PDF dialog. These are readable HTML print copies; the unchanged original blank PDFs are separately downloadable. The completed copies do not reproduce the original PDFs’ exact artwork or pagination.
- The existing internal Member model remains unchanged. Staff complete its separate onsite assessment and review the original source declarations alongside it. Family size is not mapped to dependents, 4Ps is not mapped to income, and the submitted PWD number is not assigned as an Association identifier. Earlier field contracts retain their historical receipt/review behavior; cross-contract corrections continue requiring the existing explicit reconciliation procedure.

## Validation actually completed

**155 focused Django tests passed** in fresh, isolated MySQL with `.env` disabled, synthetic records and separate private media. See `tests.log`. Coverage includes both field contracts, PDAO no-database behavior, validation, CSRF, escaping, source PDF downloads, reference retries and concurrency, private access, revocation, rollback, source retention, checklist completeness, onsite handoff, legacy membership and public/CMS guidance.

The existing isolated test launcher needed a Windows temporary-directory ACL compatibility wrapper, stored at `.local/dual-registration-20261024/run_tests.py`. It only changes creation of synthetic directories under this task’s temporary root to inherit the workspace ACL; database identity, grants, migration allowlists and production exclusions remain intact. The final command was:

```powershell
.venv\Scripts\python.exe -B .local\dual-registration-20261024\run_tests.py test membership.test_pdf_registration membership.test_registration_entry membership.test_registration_intake membership.test_registration_finish membership.test_registration_prefill membership.test_registration_handoff membership.test_reference_retrieval membership.test_confirmed_requirements membership.tests core.tests.test_public_portal --testrunner scripts.registration_handoff_test_runner.RegistrationHandoffTestRunner --noinput --verbosity 1
```

The running updated environment passes Django `check` and `makemigrations --check --dry-run` (no changes). JavaScript syntax and `git diff --check` pass. Live HTTP checks verify Home, guidance, both forms, exact PDF download hashes, real CSRF-protected PDAO print preparation/reset, Association submission/receipt, anonymous receipt denial and Finish revocation. See `live-checks.json` and `http-journey.json`. The HTTP journey adds one explicitly named fictional pending Association intake; it does not approve a Member.

**Browser verification is incomplete.** The browser harness was authored and syntax-checked, but its launch failed with `spawn EPERM`. Automatic approval review rejected the subsequent headless Chrome launch as “blocked by policy.” No new browser screenshots, responsive measurements, print-pagination verification, accessibility certification or browser-test pass is claimed. The harness is `scripts/dual_registration_browser.py` / `.cjs` for a later permitted run. Earlier test attempts and their failures remain under the ignored task artifacts; only the final 155-test result is reported as passing.

## Runtime and preservation

Port 8000’s existing process could not be stopped (`Access is denied`). Its runtime and policy were restored from exact pre-change backups; **all 851 pre-existing runtime files match**, and port 8000 still returns HTTP 200. The updated runtime is `.local/dual-registration-20261024/runtime/`, with separate session/CSRF cookie names and its own new form contract. It uses the same retained fictional database and private media through the existing verified connection manifest. The startup guard still checks database identity and pending migrations and never resets or falls back to ordinary `.env` data.

Twenty copied application/source files match the repository. Navigation/Home changes were applied separately to preserve the populated runtime’s pre-existing differences, including its EWAF integration and lack of the newer Resources module. See `preservation.json`. The root repository’s unfinished changes remain in place. No schema migration, real-data activation, government integration, scoring change, public tracking, commit, push or production deployment occurred.

## Follow-up: PDAO browser submission CSRF failure

The owner reported `Origin checking failed - null does not match any trusted origins` after submission. The PDAO view set `Referrer-Policy: no-referrer` on the entry form as well as its printable response. Native HTML form POSTs can therefore send `Origin: null`; see the [browser referrer-policy documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy). Earlier live HTTP smoke checks omitted Origin, so they did not exercise this browser behavior.

Changed the PDAO response policy to `same-origin`: internal submissions retain their origin/referrer, and external destinations receive no referrer. CSRF middleware, cookie/token validation, origin validation and trusted-origin settings remain unchanged. Null and foreign origins are still rejected. The updated port-8003 process was successfully restarted with this fix; reload the form page to replace an already loaded page’s old policy.

Six focused `membership.test_pdf_registration.PDAOPrintingTests` passed, including HTTP/HTTPS same-origin submissions with CSRF checks enabled, HTTPS Referer fallback, rejected null/foreign/different-port origins with valid tokens, and missing-token rejection. Database setup was explicitly skipped because these tests forbid database access. Actual HTTP requests against port 8003 confirmed the new GET header, successful CSRF-protected POST with browser-equivalent Origin/Referer, and rejected null/foreign origins. See `csrf-fix-validation.json`. JavaScript syntax and whitespace checks passed. The retained browser harness now checks the page policy and actual native POST Origin; it was not rerun because browser launch remains unavailable.
