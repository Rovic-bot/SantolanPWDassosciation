# Program Details: remove three sections — November 2, 2026

Removed the Draft/Published lifecycle tracker, Publication Readiness card, and Beneficiary Selection/EWAF summary card requested in the screenshots. The remaining publication action spans the available width on smaller screens. Existing `#publication-setup` links now point to that action card.

No program data, publication guards, EWAF rules, or unrelated page designs changed.

Changed files:
- `templates/programs/manage_detail.html`
- `templates/programs/profile/operations.html`
- `static/css/program-detail.css`
- `programs/test_detail_workspace.py` (existing expectations updated)
- `scripts/program_detail_browser_qa.cjs` (existing expectations updated)

Verification:
- Seven focused Django tests and the existing browser harness passed on a disposable MySQL instance.
- Fourteen browser layouts passed: 320–1600 px, dark/light themes. Synthetic publication, withdrawal, blocked EWAF publication, history, keyboard interaction, and responsive layout checks passed.
- All 14 retained program profiles rendered read-only without the three sections; the existing publication anchor remained present.
- System/database check, JavaScript syntax check, and `git diff --check` passed.
- Production asset collection passed: 205 static files into `.local/program-details-minimal-static-build`.
- Browser artifacts: temporary directory `santolan-g12-tests-2bt5p0ly/program-detail-browser`.

[Updated dark desktop](program-detail-dark-1600.png) · [Updated light desktop](program-detail-light-1600.png)
