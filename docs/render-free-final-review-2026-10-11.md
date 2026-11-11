# Final Render Free deployment source review — 2026-10-11

The owner authorized review, testing, explicit staging, commit and ordinary push to private `Rovic-bot/capstone`, branch `feature/events`. This does not authorize creating Render resources or executing hosted migrations. Development remains **70%**. The [runbook](render-free-aiven-supabase.md) contains the exact environment names, build/start commands, CA secret-file path and external migration procedure.

## Review scope and findings

Starting HEAD: `6af644a3aa6ff0062d158a3f480a92169eead8cb`. All 11 previously prepared tracked/untracked files were inspected, together with the ignored review patch, production settings, tests and existing storage access callers. No prepared work was discarded. This review adds this note and updates deployment documentation; application code is unchanged from the tested preparation.

Private evidence still passes through existing Django authorization, review and audit services. Production requires explicit storage/database inputs, validates the CA path, forces MySQL TLS identity verification and refuses a filesystem fallback. The adapter requires verified private-bucket metadata and blocks public URLs. Provider failures are sanitized; missing files retain their established behavior. CMS images retain publication gates and a neutral filename. Temporary spools close with responses. Historical/shared evidence is not automatically deleted. No runtime filesystem-only access dependency was found.

Local `config.settings` retains native MySQL and FileSystemStorage. No UI, navigation, permission, model, domain-service, migration, development `.env` or normal database changes were made. OQ-27 and unfinished EWAF/reporting policies are not resolved by deployment work.

## Fresh validation for this review

To honor the instruction against using an exposed password, this run **did not open the owner's `.env` or database credential files**. An ignored operator harness initialized an independent native MySQL 8.4.11 instance in a new private workspace directory, bound it to loopback on an unused port, assigned a freshly generated password held in memory, and injected synthetic settings with dotenv disabled. The owner's MySQL instance was never connected to. Django created/destroyed only `test_render_review` in the new instance. The temporary MySQL process was shut down afterward.

Executed with `.\.venv\Scripts\python.exe`:

```powershell
manage.py check
manage.py test documents.test_storage core.tests.test_deployment --noinput --verbosity 1
manage.py test membership members documents core accounts programs announcements assistance events --noinput --verbosity 1
manage.py check --deploy --settings=config.settings_production
-m pip check
```

- System check: **no issues**.
- Focused storage/deployment: **72 passed, 0 failed, 0 skipped**, 9.400 seconds.
- Affected application regressions: **383 passed, 0 failed, 0 skipped**, 89.026 seconds. Includes focused coverage; do not add the counts as unique tests.
- Production-like check: **0 errors, 2 warnings**, `security.W005` and `security.W021`, unchanged HSTS subdomain/preload decisions. It used separate generated placeholder credentials, invalid hosted addresses and a temporary CA-path fixture; no external connectivity occurred.
- Dependency check: **no broken requirements**.
- Existing health/static tests collect assets in a temporary directory and verify private-media rejection. Browser checks were not rerun because UI files are unchanged.

Coverage includes remote-adapter membership intake/approval, manual PRPWD review, document restrictions, validation limits, application/photo/reference history, storage failure and rollback, image replacement/deletion/publication, accounts/RBAC, public Results masking, eight Admin and seven Public navigation destinations, DEC-025 and DEC-027 regressions.

## Publication controls

Authenticated GitHub metadata verified that `Rovic-bot/capstone` is private and existing credentials have push permission. Remote `feature/events` matched starting HEAD; `main` was `c827575293620c5dbbb032ce7aefbbdc04891527`. Only `feature/events` is a push target; no force push or history overwrite is permitted.

The pre-publication scan inspected tracked/current source and all 392 reachable historical blobs for private-key/token signatures, credential-bearing database URLs and forbidden private paths. No findings were detected. This is a targeted scan and file review, not a guarantee that arbitrary secrets are detectable. It deliberately does not retrieve an old password for comparison. Existing `.env.example` uses placeholders; synthetic test credentials are not live accounts. Real `.env`, certificates, DB dumps/data, private uploads, virtual environments, `.local` QA artifacts and review diffs stay ignored and outside the explicit staging manifest.

The publication set comprises these 12 paths:

1. `announcements/views.py`
2. `config/settings_production.py`
3. `config/storage_configuration.py`
4. `core/tests/test_deployment.py`
5. `documents/storage.py`
6. `documents/test_storage.py`
7. `requirements-production.txt`
8. `scripts/render-build.sh`
9. `docs/render-deployment-preparation.md`
10. `docs/render-free-aiven-supabase.md`
11. `docs/render-free-storage-validation-2026-10-11.md`
12. `docs/render-free-final-review-2026-10-11.md`

Staged contents must match the reviewed working files after Git line-ending normalization. Run `git diff --cached --check` and inspect the staged diff before committing. Verify the final commit against `git ls-remote origin refs/heads/feature/events`, and confirm `main` is unchanged. The final operator report supplies the resulting commit hash; this source note does not predict a push outcome.

## Runtime blockers and operator handoff

**Freshly rotated hosted credentials are mandatory before actual connectivity.** Neither the old exposed password nor new real credentials were requested/read/used during validation.

Still unvalidated: Linux mysqlclient compilation and Gunicorn startup; CA availability in Render build/runtime; real Aiven TLS/hostname validation; Supabase API/S3 credentials and bucket/RLS restrictions; hosted migration review/execution; synthetic restart durability; memory/latency under Render Free limits; backup/restore and free-service quota/inactivity behavior. HSTS flags await domain review. Cloud/MySQL transactions are not atomic together: private orphan cleanup needs careful historical/shared-reference review.

Next, the owner can rotate credentials, prepare the free Aiven/Supabase resources and approved CA, and use a trusted external operator session to review the hosted migration plan. Only after those prerequisites should the owner create the Render Free Python Web Service from the reviewed `feature/events` commit, populate the runbook settings, use `/healthz/`, keep automatic deploys off initially, and validate synthetic workflows. Render Free offers no shell/one-off jobs; do not place migrations in the build/start commands.

**Schema changes: NONE. New migrations: NONE. Owner development data changes: NONE. Hosted migrations: NONE. Render resources/paid services: NONE. Approved Admin UI: UNCHANGED. Baseline: 70%.**
