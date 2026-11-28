# Deployed system audit plan

Audit the release running at `d771599`, with a separate candidate checkout. The main development tree and its 1,370 pre-existing changes remain intact.

1. Freeze the deployed source and record full baseline discovery and failures.
2. Reproduce report, PostgreSQL portability, upload validation, PDAO transfer and certificate defects; fix each with regression evidence.
3. Exercise all discovered tests on disposable PostgreSQL, retaining current production claim and published-weight locks.
4. Audit public and authenticated interfaces at 320, 375, 390, 430, 768, 1024, 1366 and 1440 pixels, with Chromium, Firefox and WebKit where available.
5. Measure database work and browser laboratory timings; run safe dependency and privacy checks.
6. Verify migration drift, static production build, failure recovery and release contents. Local Docker image build/scanning is blocked by the operator's choice to continue without Docker.
7. Review the patch, deploy only the validated candidate under the existing deployment authorization, and verify the live commit and health. Record any unresolved gate rather than asserting unconditional readiness.

The full 13-section report and case ledger will distinguish baseline failures, corrected fixtures, confirmed defects, retests, provider checks and unverified acceptance criteria. No ISO certification or full WCAG conformance is claimed.
