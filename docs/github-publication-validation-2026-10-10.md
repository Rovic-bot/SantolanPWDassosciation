# GitHub publication and Render preparation validation — 2026-10-10

The reviewed destination is `https://github.com/Rovic-bot/capstone.git`, branch **feature/events**. The owner supplied this URL and requested private visibility before pushing. Authenticated GitHub metadata subsequently confirmed **private=true**, push permission and a non-archived repository. No repository visibility was changed by Codex.

**Publication successful.** The validated implementation and deployment-preparation commit is [4740eab5ae5a3feeb228cedbb9953dece9a04166](https://github.com/Rovic-bot/capstone/commit/4740eab5ae5a3feeb228cedbb9953dece9a04166). `git ls-remote` independently confirmed that hash on `refs/heads/feature/events`, and that remote `main` remained `c827575293620c5dbbb032ce7aefbbdc04891527`. The branch now tracks `origin/feature/events`; the working tree was clean. This final documentation-only follow-up records the verified outcome; its final remote hash is reported by Codex and saved in ignored local verification artifacts.

GitHub's `main` has a separate initial README commit. The local project has three existing commits and no shared ancestor with that README history. Publication uses the existing local branch, preserving remote `main`, other local branches and history. No force push, reset, clean, branch switch, vault-note publication or Render resource creation is authorized or performed by this preparation.

## Starting Git audit

Executed `git status --short`, `git remote -v`, `git branch --show-current`, `git diff --stat`, `git ls-files -u`, upstream inspection and commit inspection. There was initially no remote, no upstream and no merge conflict. The validated work was uncommitted: 41 tracked modified files plus existing untracked implementation files. Those files were inspected/preserved rather than discarded. The owner-supplied GitHub URL was added as `origin`, and its existing history was fetched read-only.

## Secret and private-file audit

All publishable current files and the complete reachable local/remote history were checked for forbidden paths, private keys, known GitHub/AWS/Render token signatures and credential-bearing database URLs. The exact current local `SECRET_KEY` and `DB_PASSWORD` were compared in memory against content without printing or writing their values. Initial local history: **3 commits, 152 unique blob/path pairs**. After fetching: **4 local/remote commits, 153 unique blob/path pairs**. No credential matches were found.

`.env.example` contains placeholders, not operational secrets. Existing test-only password literals are scoped to synthetic users created in disposable test databases; they are not live Admin credentials. Browser credentials are generated at runtime. The audit does not include owner database rows, which are never exported for publication.

The original ignore rules exclude `.env`, virtual environments, private media, `.local`, cache files and collected static output. Nine existing private-media files and more than 1,200 local QA/backup files were excluded by those rules; their contents/names are not published. Additional ignore rules exclude database dumps, local database files, keys/certificates, archives, private upload directories and tooling output. No binary, spreadsheet, Word, CSV/data-export or private-upload file is included in the reviewed publication set. No secret values are included in this report.

Staging uses an explicit reviewed file manifest, not `git add .` or `git add -A`. Staged blobs are rechecked before commit; both their paths and their exact content must match the reviewed working files after Git's declared line-ending normalization. The cached diff is saved for review in ignored local audit artifacts. The complete publication file list and changed/new file lists are captured there.

## Files changed by this preparation

- [.gitignore](../.gitignore): additional secret/private/export/tooling exclusions.
- [README.md](../README.md): correct stale current-navigation statements, link validated work and deployment instructions.
- [.python-version](../.python-version): match the validated Python 3.14.5 runtime.
- [requirements-production.txt](../requirements-production.txt): isolated production dependency additions; local requirements unchanged.
- [config/settings_production.py](../config/settings_production.py): explicit environment-only HTTPS/MySQL TLS/private storage/static configuration.
- [config/urls_production.py](../config/urls_production.py): minimal production-only health wiring; existing application routing unchanged.
- [core/tests/test_deployment.py](../core/tests/test_deployment.py): synthetic settings guards, health/proxy/static/private-media checks.
- [scripts/render-build.sh](../scripts/render-build.sh): install/check/static build with no migration or seeding.
- [programs/test_workflow_alignment.py](../programs/test_workflow_alignment.py): remove one pre-existing extra blank line at EOF discovered by the first cached-diff check. Its Python syntax tree and test behavior are unchanged.
- [docs/render-deployment-preparation.md](render-deployment-preparation.md): full Render handoff, environment names and pending approvals.
- This validation note.

Earlier validated implementation files are also included in the publication commit because they were uncommitted at task start. A starting hash manifest of **352 repository files** confirms that **349 existing files remain byte-identical**; only README, .gitignore and the single test EOF whitespace correction changed. In particular, approved Admin/public templates, styles, navigation, membership guidance, permissions, application services, models and existing migrations remain intact. New production configuration is opt-in; ordinary local commands still use `config.settings`.

## Actual validation

Executed with the existing project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-production.txt
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test core.tests.test_deployment --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test membership members documents core accounts programs announcements assistance events ewaf --noinput --verbosity 1
$env:NODE_PATH = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
.\.venv\Scripts\python.exe manage.py test scripts.admin_ui_browser_qa scripts.admin_navigation_browser_qa scripts.public_navigation_browser_qa scripts.announcements_members_browser_qa scripts.revised70_browser_qa scripts.membership_browser_qa --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py check --deploy --settings=config.settings_production
git diff --check
git diff --cached --check
git diff --cached --stat
```

The production deployment check was executed in a subprocess with temporary synthetic environment variables and a temporary CA-path fixture. It made no hosted/development database connection. Its first attempt was blocked by sandbox temporary-directory permissions; the approved rerun executed successfully.

- Local Django system check: **no issues**.
- Final deployment-specific tests: **9 passed, 0 failures, 0 skips** (2.423 seconds), after tightening explicit host/origin and source/static upload-path checks.
- Affected-app regressions: **326 passed, 0 failures, 0 skips** (72.930 seconds). These include the nine deployment cases; counts are not additive unique coverage. Final production guard refinements were separately rerun in the nine-case suite.
- Fresh Chrome workflows: **6 passed, 0 failures, 0 skips** (110.158 seconds), covering 14 populated Admin pages plus navigation, Results/publication, revised applications and onsite membership. The five viewport widths were 320, 390, 768, 1024 and 1440px.
- Normal Chrome operation: **zero captured JavaScript/console errors**. Restricted staff, direct protected access, keyboard navigation, expansion/scroll persistence, seven public sections and eight Admin groups passed. The known native Django filter error under deliberate total session-storage denial remains separately identified; no vendor fix is claimed.
- Production-like `check --deploy`: **0 errors, 2 warnings**, security.W005 and security.W021, for HSTS subdomains/preload remaining off pending domain-policy approval. No warning is silenced; this is not an unconditional production-readiness pass.
- WhiteNoise installation succeeded. Gunicorn's platform marker correctly excludes Windows; a Linux/Gunicorn/Render build was not executed.

The HTTP tests collect the real approved static assets into a temporary directory, verify successful static delivery, and verify that a private synthetic media file cannot be downloaded from `/media/`. They also check HTTPS redirect/proxy behavior and database-independent GET/HEAD health responses. Configuration tests cannot establish actual hosted database TLS or persistent-disk durability; those remain deployment acceptance requirements.

## Preservation and deployment status

Fresh regressions preserve Phase 1 public Results/receipt behavior; Phase 2 eight-group RBAC navigation; DEC-025 authorized non-EWAF masked publication and withdrawal/freshness; DEC-027 Association/PDAO guidance, onsite intake, private attachments, manual PRPWD review and approval safeguards. No EWAF, reports, selection policy, issued reference, membership evidence rule or workflow was changed.

**Owner-defined development baseline: 70%, unchanged. New migrations: NONE. Schema changes: NONE. Development records modified: NONE.** Only disposable test database/media were used; no live Render service, paid infrastructure or real-person deployment was created. OQ-27 still governs incomplete evidence-handling enforcement; visible guidance is not full verification implementation.

The [Render handoff](render-deployment-preparation.md) records outstanding MySQL hosting/TLS, private persistent storage, costs/access, domain/HSTS, Linux build and synthetic hosted acceptance requirements. Publication is conditional on the verified private destination and staged security review. The final commit and remote hash verification are reported by Codex and retained in ignored `.local/github-render-preparation/` artifacts, avoiding a self-referential commit hash in this file.
