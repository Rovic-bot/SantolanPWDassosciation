# Current development system on port 8000

2026-10-24 — **Completed for the requested local fictional-data startup.** The owner explicitly selected **“Use fictional data at port 8000.”** This does not authorize operational Association intake or change the accepted 70% milestone. Phases 2B–5 remain Partial as previously recorded.

The current repository application is running at **http://127.0.0.1:8000/**. Membership registration: `/membership/register/`; direct form: `/membership/registration/apply/`; staff inbox: `/membership/registrations/`. The existing `demo_staff` demonstration login is retained. Credentials are only in the ignored local runtime folder, not this report.

The exact former port-8000 web process and its Python launcher were checked and stopped. Its saved working database was not connected to, migrated, reset, copied or rewritten. Its MySQL service was not stopped. The port-8001/8002 demonstrations were left alone. Port 8000 now uses a fresh, explicitly fictional MySQL instance and separate media/cookies, with a visible fictional-data banner. It runs the current checkout, not the older frozen main-testing code.

## Changes and startup

- `Start System.cmd` now invokes the new `scripts/run-current-development.ps1`.
- That script invokes the ignored `.local/main-registration-development-20261024/start.py`. Missing local setup fails closed; it does not fall back to the normal `.env` database.
- Initial provisioning reused the reviewed schema-only/history-metadata restoration and exact four extension migrations: membership/0006, members/0006, core/0002, membership/0007. Each target/dependency/hash was verified before application to the fresh disposable MySQL instance. No historical migration was executed or changed.
- The retained runtime manifest pins the synthetic database name, port, datadir, server UUID, media directory and configuration hash. The startup helper resumes that same instance and records; it does not reseed, reset, reassign permissions, change credentials or automatically migrate on restart. Existing correct port-8000 startup is idempotent; a different listener is refused.
- The existing `runlocal` migration guard remains mandatory and unchanged. Only the previously approved Events deferral remains pending in this synthetic environment. Ordinary `config/settings.py`, `.env`, `scripts/run.ps1` and the old main-testing launcher remain unchanged.

Initial and resumed process/connection metadata and private credentials are stored under the ignored local runtime folder. The database and private media are retained under its verified `santolan-g12-tests-*` directory. This is local development storage, not a production durability guarantee: if that retained directory is removed, startup refuses instead of creating a silent replacement. Do not delete the runtime files or data directory when retaining fictional work.

## Checks actually performed

1. A real headless-Chrome journey on port 8000 passed: public form submission; AMR receipt and office instruction; Admin onsite reference lookup with filled fields; beginning review; five-item onsite observations; acceptance/assessment preparation; synthetic manual verification; approval; official Member; anonymous denial; Finish revocation. Mobile overflow was checked and no JavaScript errors were recorded. Screenshots and checks are in `ui/`.
2. The first browser run stopped on an ambiguous test selector that matched both Sign out and Save onsite observations. The test selector was corrected; application code was not changed. Its failed log is retained as `browser.log`; `browser-final.log` passed. The aborted fictional intake remains retained, rather than deleted to hide the failure.
3. `run-current-development.ps1` correctly detected the already running instance without reseeding.
4. A controlled stop/resume through the new launcher retained the same server UUID and exact synthetic business-row, migration-history and permission fingerprints. Evidence: `restart-verification.json`. Two pending-intake records/revisions remain (one from the aborted browser test), one linked membership application and one approved fictional Member. No EWAF snapshot/operational run or assistance release was created.
5. After restart, Home, Membership guidance, the active form and login returned HTTP 200 with the expected instance marker and fictional-data banner. `verification.json` records these results.
6. All **267 protected files** match the Phase 1 manifest. Original/integrated Section 8 remain byte-identical, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. `.env`, normal settings and startup guard match this task's initial hashes. Launcher diff whitespace check passed (Git reported only its Windows line-ending notice).

No application behavior or schema file was changed in this startup task. No new full regression or EWAF suite was run; the previous approval report retains its actual 188-test pass and the separate older guidance-assertion failures. No real-member testing, production deployment, commit, push or merge occurred.

## Continuing work

Use **Start System.cmd** for this selected current-code fictional environment. Use **Members → Membership Reviews → Pending Association registrations** to retrieve and review submissions. The confirmed Association checklist and existing manual verification/decision workflow remain enforced by the application; synthetic configuration is not Association/PDAO approval.

Real collection still needs the institutional procedures, privacy/retention/security settings, staff assignments, acceptance and separately authorized working-database migration described in the [approval report](../registration-approval-2026-10-24/README.md). PDAO, public tracking/recovery and other deferred functions remain unavailable. No real institution policy was inferred from the owner's port-8000 choice.
