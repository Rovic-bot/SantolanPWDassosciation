# Production quality audit — 28 November 2026

## 1. Executive summary

**Recommendation: READY WITH CONDITIONS.** The Santolan PWD system handles public Association and PDAO applications, protected supporting documents, staff verification, member records, program applications, versioned EWAF assessment, explicit human selection, assistance receipts, public announcements and certificates.

This audit started from the actual deployed commit `d77159913f822487f916b332ab9d04c26da744ea`, in an isolated worktree. The development checkout is a different branch/repository with 1,370 pre-existing status entries; it is not identical to production and was preserved. No production application, member, selection or receipt was created for this audit, and no real email was sent.

Confirmed corrections include a PDAO-to-membership phone-format failure, missing-date report crashes, PostgreSQL duplicate handling, image upload restrictions and a vulnerable Pillow release pin, certificate resource limits, profile-review errors, audit invalidation errors, unnecessary database queries, accessibility failures and scanner layout shifts. Obsolete test fixtures were repaired separately from application defects. No database migration or published-weight rule was changed.

Current default-discovery result: **3121 PASS, 0 FAIL, 0 NOT RUN of 3121 unique cases**. This report is generated from case ledgers, not estimated coverage. Deployment status: **LOCAL VERIFICATION PASSED; production deployment pending**.

## 2. Project inventory

| Area | Actual system |
|---|---|
| Application | Django 5.2.17; Python 3.14; server-rendered HTML; vanilla JavaScript; Bootstrap; locally built Tailwind utilities |
| Production runtime | Render Docker web service, Python 3.14.5 Debian Bookworm, Gunicorn 26.2.0, one worker/three threads, Singapore, free plan |
| Database | Supabase PostgreSQL 17.11, private `santolan` schema, 142 tables; isolated PostgreSQL 18 for tests |
| Documents | Private Supabase S3-compatible storage; guarded Django downloads; JPEG/PNG portraits; local LibreOffice PDF conversion |
| OCR | Locally hosted Tesseract.js 6.0.1; browser-only image reading; reviewed fields before applying |
| Integrations | SMTP certificate/notice delivery, S3 storage, PRPWD review workflows, Render/GitHub deployment |
| Authorization | Public applicants; staff with granular Django permissions; technical superuser; server-side enforcement |
| Testing | Django TestCase/TransactionTestCase/StaticLiveServerTestCase, Playwright Chromium/Firefox/WebKit, axe-core 4.14.0, pip-audit, npm audit, loopback SMTP/Moto S3 |
| Deployment | `Rovic-bot/SantolanPWDassosciation`, `deployment/free-render-supabase`; automatic deploy off; `/healthz/`; build-time static collection and PDF check; startup deployment checks |

The application uses revision/audit records and explicit transactions for consequential decisions. Optional historical intake code is disabled in production; its separate evidence contract is tested only when explicitly installed/enabled. See [system profile](system-profile.json) and [audit plan](AUDIT_PLAN.md).

## 3. Defect register

Root causes and reproductions, exact changed files, associated test IDs and results are in [defects.json](defects.json). Test failures caused by stale fixtures are not counted as hundreds of product defects.

| ID | Severity | Component | Problem / root cause | Correction | Retest |
|---|---|---|---|---|---|
| AUD-01 | High | PDAO membership transfer | A saved +63 mobile number was rebound into a field requiring ten national digits, blocking consent-based transfer. | Normalize the server-owned initial phone before binding; retain the canonical saved number and immutable source. | PASS |
| AUD-02 | Medium | Reports | An unscheduled draft raised an exception while formatting report dates. | Display Not specified for absent dates while retaining Manila formatting for scheduled records. | PASS |
| AUD-03 | Medium | PostgreSQL duplicate handling | Duplicate-key recovery recognized MySQL only. | Recognize SQLSTATE 23505 and MySQL 1062; propagate unrelated integrity errors. | PASS |
| AUD-04 | Medium | Image validation | Portrait validation accepted a disguised GIF; decoder selection was broader than the allowed formats. | Limit portrait decoding to JPEG/PNG and announcement decoding to the declared allowed format; rewind streams. | PASS |
| AUD-05 | Medium | Certificate conversion | Concurrent requests could render and launch Office together; short cold-start budgets and suppressed error categories reduced reliability. | Reserve one conversion slot per worker before DOCX rendering; release it in finally; bounded 90 to 180 second budget and sanitized diagnostics. | PASS |
| AUD-06 | Low | Registration validation | The same validation message appeared multiple times. | Keep one copy of each identical message. | PASS |
| AUD-07 | Medium | Member information review | Document controls appeared in an information-only review; acknowledgement was treated as a profile edit and unchanged information could not be resolved. | Remove document-only controls, render optional sections safely and exclude acknowledgement from profile change detection. | PASS |
| AUD-08 | Medium | Assistance portfolio queries | Retained selections performed two queries for each program. | Batch first adoption witnesses and approval lookups without changing eligibility or audit scope. | PASS |
| AUD-09 | Medium | EWAF readiness queries | Repeated relationship fetches inflated readiness query counts. | Join required policy, application, previous review and document relationships; preserve all evidence checks. | PASS |
| AUD-10 | Medium | Audit invalidation | Linked-event form initialization mutated the previous-state object; unpublishing expected an archived audit action although the actual transition was draft. | Copy the prior event instance and match the actual draft audit transition. | PASS |
| AUD-11 | Low | Capacity metric | The numerator excluded retained finite-capacity non-EWAF programs while the denominator included them. | Count applicants consistently across programs with known capacity. | PASS |
| AUD-12 | Medium | Reference lookup and partial evidence | Case-sensitive reference matching could reject an otherwise exact identity; incomplete evidence presentation indexed a missing status. | Case-insensitive reference comparison with identity checks retained; safe missing-status lookup. | PASS |
| AUD-13 | Low | Public guidance | Published membership guidance was omitted; fallback EWAF copy incorrectly denied numerical ranks. | Render published guidance and accurately describe advisory numerical ranks and immutable history. | PASS |
| AUD-14 | Medium | Accessibility | Login and registration text contrast failures, an empty technical-admin title and a keyboard-inaccessible scrollable onsite guide. | Use palette-compatible contrast colors, add the admin title and make the scrollable guide focusable. | PASS: 23-route Chromium, Firefox and WebKit accessibility scans |
| AUD-15 | Medium | Initial layout stability | Deferred scanner/filter initialization shifted visible content. | Reserve the scanner geometry and match initial filter layouts before deferred initialization; retain no-script behavior. | PASS: six focused desktop/mobile layout-shift measurements and full Chromium sweep |
| AUD-16 | Medium | Optional intake laboratory | The separately enabled intake adapter did not connect its distinct evidence contract and eligibility requirements to current services. | Use an explicit installed-app/feature/contract gate; leave the production current workflow authoritative. | PASS |
| QA-01 | Medium | Test infrastructure | Many checked-in fixtures still used retired approval routes, missing current required data, old UI selectors or inconsistent synthetic timestamps. | Update synthetic setup and UI selectors, preserve arithmetic oracles and security assertions, align frozen model clocks, and retain published-weight locks. Pin LF checkout for four checksum-verified ranking fixtures; align frozen synthetic model timestamps; exercise historical migrations in separate disposable databases. | PASS |
| AUD-17 | High | Image dependency | Production requirements pinned Pillow 12.3.0; the advisory scan reported 42 known advisories. The local test environment was already on 13.0.0, masking the release-pin mismatch. | Pin Pillow 13.0.0; explicitly constrain image decoders; retest uploads and document generation. | PASS |

## 4. Test execution summary

The default suite is counted once per final discovered ID. Focused retests replace an earlier result only for that same case. Browser cases already in the default suite are not added again. Renamed historical tests and import placeholders remain visible in the raw run ledgers.

| Component | Planned | PASS | FAIL | NOT RUN |
|---|---:|---:|---:|---:|
| accounts | 72 | 72 | 0 | 0 |
| analytics | 27 | 27 | 0 | 0 |
| announcements | 157 | 157 | 0 | 0 |
| assistance | 147 | 147 | 0 | 0 |
| audit | 17 | 17 | 0 | 0 |
| core | 161 | 161 | 0 | 0 |
| documents | 62 | 62 | 0 | 0 |
| events | 157 | 157 | 0 | 0 |
| ewaf | 1311 | 1311 | 0 | 0 |
| main_testing | 9 | 9 | 0 | 0 |
| members | 102 | 102 | 0 | 0 |
| membership | 386 | 386 | 0 | 0 |
| program_intake | 45 | 45 | 0 | 0 |
| programs | 465 | 465 | 0 | 0 |
| reports | 3 | 3 | 0 | 0 |
| **Total** | **3121** | **3121** | **0** | **0** |

The untouched source baseline selected 3077 nonbrowser cases and has recorded 2737 results: 2127 PASS and 610 FAIL. Baseline runtime used the available local Python environment, including patched Pillow 13.0.0, rather than the old production Pillow pin. The separate manifest scan detects that dependency difference. Several baseline fixtures predate mandatory EWAF, current route contracts and newer migration leaves. Those fixture failures do not by themselves prove production workflow failures.

Additional, separately identified checks: 4 broad UI/layout Django audit cases; 16 synthetic OCR/camera-contract browser scenarios; 12 loopback S3/SMTP integration cases; static collection, syntax checks, schema drift, dependency manifests, provider metadata and recovery checks. Route/viewport assertions are subchecks, not additional default-suite tests. See [test-cases.json](test-cases.json), [test-summary.json](test-summary.json), [OCR](ocr.json) and [integration checks](local-integrations-final.json).

Reproduction: use `scripts/quality_postgres_launch.py --settings=config.intake_test_settings --testrunner=scripts.release_test_partition.ReleaseTestRunner --partitions=2 --partition=0` and partition 1; run `--browser-only` separately with Playwright and LibreOffice configured. The launcher creates a fresh authenticated loopback cluster, verifies its identity, runs real migrations, isolates media and mail, and blocks external Python sockets. Historical migration tests create additional disposable databases. No destructive migration rollback was attempted against production. Browser scripts independently prohibit external requests.

| Test category | Evidence / scope | Status |
|---|---|---|
| Static analysis/build | 991 Python files parsed; 91 application JS files syntax checked; production static collection; diff whitespace checks | PASS |
| Type checking | No configured project type checker; no fabricated type/coverage percentage | NOT RUN |
| Unit/integration/API | Actual Django assertions, positive/negative inputs and permissions | PASS for defined automated criteria |
| Database/migration/concurrency | Real PostgreSQL transactions, race tests, isolated historical graphs; no new model migration | PASS for defined automated criteria |
| Functional/E2E/regression | Discovered browser workflows plus synthetic registration, review, ranking, selection, publication and receipts | PASS for defined automated criteria |
| Responsive/accessibility | 23 routes per engine at eight widths; axe and defined keyboard checks | PASS for tested criteria |
| Error/recovery | Transaction rollback, duplicate requests, interrupted SMTP, private object restore and DB restore | PASS for documented checks |
| Installation/deployment | Local static build; Docker image build/OS scan unavailable locally | PARTIAL |
| Sustained load/real device/manual screen reader | No aggressive production load; physical mobile OS camera and assistive-technology sessions unavailable | NOT RUN |

## 5. ISO/IEC 25010 assessment

This is an engineering assessment using the nine product-quality characteristics in [ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html), not certification, a numerical score, or a declaration of full compliance. Each PASS is limited to its stated acceptance criterion. Browser access barriers and missing operational evidence remain explicit.

| Characteristic | Acceptance criterion / evidence | Initial status | Remediation | Final status / gap |
|---|---|---|---|---|
| Functional suitability | Required synthetic workflows and exact scoring/decision assertions complete; no unintended approval | FAIL | PDAO transfer, reports, profile-review and contract corrections | PASS for defined automated criteria; no live PII submissions |
| Performance efficiency | Retained selections <=2 queries for 12 programs; verified readiness <=45; targeted CLS <=0.1 | FAIL | Batched reads, related-object loading, prepaint scanner assets | PARTIAL: query/CLS criteria pass; field LCP/INP/capacity unmeasured |
| Compatibility | Chromium, Firefox, WebKit routes and forms; private S3/SMTP adapter contracts | PARTIAL | PostgreSQL duplicate support; decoder allowlists; refreshed fixture contracts | PARTIAL: tested engines pass; physical phones and PG17 full regression unavailable |
| Interaction capability | No tested axe A/AA violations or horizontal overflow; keyboard menu focus returns; reviewed OCR fields | FAIL | Contrast, title, scroll-region focus and scanner spacing fixes | PARTIAL: automated/defined keyboard checks pass; full manual WCAG review outstanding |
| Reliability | Failed actions roll back; duplicate/retry protections; DB/file recovery matches hashes | PARTIAL | Bounded certificate conversion and safe diagnostics | PARTIAL: tested rollback/recovery passes; hosted availability/PITR/real-mail receipt not established |
| Security | Guarded uploads/downloads; tested permissions; no known scanned package advisories; private bucket/runtime role | FAIL | Pillow 13.0.0, narrow image decoders, correct duplicate handling | PARTIAL: defined controls pass; OS image scan and independent penetration assessment unavailable |
| Maintainability | Reproducible complete discovery, targeted regression IDs, source traceability, no schema drift | FAIL | Current fixtures, isolated migration helper, audit scripts and this evidence bundle | PASS for defined automated criteria; broad legacy complexity remains |
| Flexibility | Fresh PostgreSQL test cluster; environment-driven production build; optional adapter gated | PARTIAL | PostgreSQL-aware error recovery; portable test-tool paths and LF fixture rules | PARTIAL: native tests pass; Docker local build excluded by operator |
| Safety | Human selection, claim/consent and published-weight locks preserved; no fabricated results or duplicate assistance | PARTIAL | Fail-closed validation, audited state transitions and preservation tests | PASS for defined automated criteria; administrative benefits system, not a medical device or safety-critical controller |

## 6. UI/UX and responsive design

The requested PDAO document upload fields and scanner layout/palette were already present in the starting deployed release. This audit preserves them, verifies online/onsite paths and corrects discovered issues. The scanner follows the site's warm neutral light/dark palette, with paired front/back cards and distinct Take photo/Choose file actions. Moving scanner styles into the document head prevents late insertion from shifting the form. Visual evidence: [desktop scanner](scanner-desktop.png), [mobile dark scanner](scanner-mobile-dark.png), both with clearly fictional test content.

Actual widths: **320, 375, 390, 430, 768, 1024, 1366 and 1440 px**. The latest sweeps test 23 public/staff routes in each of Chromium, Firefox and WebKit: **184 width assertions per engine**. They include online Association/PDAO and onsite PDAO forms, dashboard, programs, events, reviews, EWAF, assistance, reports, content and Django admin. These checks found no horizontal overflow or reported console/HTTP errors. They do not prove every content-dependent state fits at every intermediate width.

OCR scenarios cover four form variants, two-sided cards, rotated scans, receipt customer fields, existing-value preservation, explicit field review, cancellation, corrupt images, permission denial and the no-JavaScript form. Mobile emulation verifies native capture input selection and a separate file chooser with zero embedded stream requests. A real phone's camera launch still needs operator acceptance.

## 7. Accessibility

Initial axe failures: login/PDAO text contrast, missing meaningful admin title, and an onsite guidance scroll region without keyboard focus. These were corrected. Latest Chromium/Firefox/WebKit scans report zero violations for the selected WCAG 2 A/AA, 2.1 AA and 2.2 AA tags on their tested routes. Defined keyboard tests cover Display menu opening, focus placement, Escape dismissal and return; enlarged text and narrow reflow are checked. Dark/high-contrast checks cover the documented home/dashboard/scanner states.

See [Chromium evidence](chromium-ui.json), [Firefox](firefox-ui.json), [WebKit](webkit-ui.json). This is **not a claim of full [WCAG 2.2](https://www.w3.org/TR/WCAG22/) conformance**: manual screen-reader reading order, all dialog/error states, actual 200% browser zoom, low-vision/mobile assistive technology and every content variant were not fully evaluated. Reduced-motion was enabled during automated runs; that alone does not verify every animation.

## 8. Performance results

| Measurement | Before | After | Interpretation |
|---|---:|---:|---|
| Retained-selection reads, 12 programs | 24 queries | 2 queries | 91.7% fewer queries; identical authoritative projection |
| One verified applicant readiness | 61 queries | 42 queries | 31.1% fewer queries; validation preserved |
| Production static collection | 27.63 s | 28.108 s | Build validation, not evidence of a speed improvement |
| Native PDF batch, 3 synthetic documents | 45.046 s | 24.111 s | Both pass; warm caches/concurrent host work prevent attributing this difference to the patch |

| Lab route / viewport | Before CLS | After CLS |
|---|---:|---:|
| /dashboard/ / 1366 px | 0.0221 | 0.0221 |
| /ewaf/ / 1366 px | 0.2409 | 0.0000 |
| /membership/registration/pdao/onsite/ / 1366 px | 0.2699 | 0.0000 |
| /dashboard/ / 390 px | 0.0919 | 0.0000 |
| /ewaf/ / 390 px | 0.0216 | 0.0000 |
| /membership/registration/pdao/onsite/ / 390 px | 0.4907 | 0.0000 |

CLS tests are repeatable local browser measurements, not field data. Homepage mobile lab conditions are a 390x844 viewport, 4x CPU slowdown, 150 ms latency and approximately 500 kB/s. Across successive runs under heavy concurrent regression load, LCP varied from approximately 2.4 to 4.6 seconds; CLS was 0. There is insufficient comparable evidence to claim improved LCP or that the 2.5-second target is consistently met. The homepage sweep transferred approximately 1.31 MB across 55 requests before OCR is invoked; actual production compression/caching differs from Django's local static test server.

A successful initial production navigation measured homepage LCP **8.292 s**, TTFB **1.040 s**, CLS **0**, and **521,607 transferred bytes / 55 requests**. About measured LCP 0.784 s; Announcements 4.052 s. These are isolated desktop observations before the later Cloudflare barrier, not field percentiles or comparable before/after trials.

The synthetic 100-applicant integration produced all 100 scores and 400 traces correctly, with disjoint paginated results. Under concurrent local test load it took **37.671 s** to capture/calculate/persist and **14.692 s** to revalidate/render the first page. This exposes a capacity concern; the configured 2,000-applicant ceiling is **not a benchmarked capacity guarantee**. See [volume measurements](volume-measurements.json).

Field LCP/INP/CLS at the 75th percentile, INP <=200 ms, production throughput, sustained concurrency capacity, Lighthouse score and authenticated production API timings are **unmeasured**. [Core Web Vitals thresholds](https://web.dev/articles/vitals) are targets, not inferred passes. Supabase reports one informational unindexed foreign key and 217 unused-index notices; no measured workload justified schema changes or removing those indexes.

## 9. Security findings

The flattened 20-pin production requirements scan found 42 Pillow 12.3.0 advisories. Pinning 13.0.0 clears the scan; [Pillow's official release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html) document the fixes. This is a dependency exposure finding, not a claim that every advisory was exploitable through this application. The local Python environment scan and npm audit also report no known findings at scan time; they are not a security guarantee. See [dependency evidence](dependencies.json).

The source check found no recognized credential patterns in 3,999 tracked UTF-8 files <=2 MB and no tracked live `.env` file. This limited pattern scan is not an entropy scan or proof that all historical content is safe. Production metadata confirms 142/142 application tables with RLS, a runtime role without superuser/bypass-RLS, and a nonpublic document bucket. Supabase security/health advisors returned no notices; see [provider metadata](provider-checks.json).

Permission/ownership, CSRF, stale token, duplicate submission, private file and rollback tests are traced in the case ledger. No destructive exploit or load attack was run on production. Container OS CVEs, comprehensive malware inspection of uploads, independent penetration testing and a formal legal/privacy compliance assessment remain outside verified scope.

## 10. Code changes

[changed-files.json](changed-files.json) lists every changed application/test/tool file and links it to defects where applicable. Main corrections are in membership transfer/validation, image decoding, certificate conversion, reports, profile-review forms, EWAF invalidation/readiness, retained-selection queries, and small CSS/template changes. The test updates preserve the deployed consent/claim flow, exact scoring, explicit human decisions and frozen weights for published results.

There are **no migration files changed** and `makemigrations --check --dry-run` reports no model changes. Four hash-pinned ranking fixtures receive an LF checkout rule without changing their Git content. Audit artifacts contain test identifiers, aggregate results and fictional fixtures; backups, credentials, live rows and private documents remain outside the repository/image.

## 11. Remaining issues and blockers

| Item | Status | Required follow-up |
|---|---|---|
| Local Docker image build and OS vulnerability scan | BLOCKED by operator choice to continue without Docker | Run in CI or a Docker-enabled environment; Render's build only validates its build/runtime checks |
| Wide live-browser sweep | BLOCKED by Cloudflare challenge/rate response | Authorized staging/interactive verification; do not bypass protection or treat missing-style pages as accessibility evidence |
| Physical mobile camera and manual assistive technology | NOT RUN | Test Android/iOS native camera and real screen readers with representative PWD users |
| Real email delivery | NOT RUN | Confirm a designated test recipient and verify provider acceptance/inbox delivery; no mail sent by this audit |
| Field performance and realistic load | NOT RUN | Collect representative field metrics and use staging for capacity testing |
| Free Render availability | PARTIAL | Free services may spin down; agree on acceptable cold starts/availability before unrestricted operational use ([Render limits](https://render.com/docs/free)) |
| Scheduled offsite backup/PITR and full production disaster recovery | PARTIAL | DB and object restore drills passed locally; operational scheduling, retention, RPO/RTO and hosted restoration still require validation |
| PostgreSQL platform parity | PARTIAL | Local suite uses PG18; deployed PG17.11 metadata/recovery were checked, but full disposable PG17 testing was unavailable |

The report records a controlled scope, not a declaration that the site is bug-free. Complete any remaining NOT RUN default cases before treating this candidate as release-ready.

## 12. Deployment status

**LOCAL VERIFICATION PASSED; production deployment pending**. See [deployment.json](deployment.json) for provider-confirmed identifiers and postdeployment checks when available. Local tests/static collection are separate from a successful Render image build and from verified live behavior. Production environment variables and schema were not changed.

Rollback: redeploy the previous Render deployment/commit `d77159913f822487f916b332ab9d04c26da744ea` through the service dashboard. Automatic deployment is disabled. This patch has no migrations, so code rollback does not require a database rollback. Preserve new production writes; do not restore the database merely to roll back code. Encrypted database and object backup drills are documented in [database recovery](recovery-verification.json) and [object recovery](object-recovery.json).

## 13. Final readiness recommendation

**READY WITH CONDITIONS.** All current default-discovery cases have executed successfully after focused retests. Accept only within the tested scope and with the explicit operational/device/performance conditions above; provider-confirmed deployment and safe live smoke checks remain separate gates.

This is an evidence-based engineering assessment, not ISO certification or a blanket accessibility/security guarantee.
