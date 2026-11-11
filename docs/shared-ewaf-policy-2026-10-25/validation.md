# Shared EWAF policy draft validation

25 October 2026. Scope: prepare one review-only shared policy for the **new** HI/SI/ES/PA/HM dataset engine, with synthetic demonstrations and unchanged operational safeguards.

## Delivered

- [Reviewable scoring-policy draft](SCORING_POLICY_DRAFT.md), `HI-SI-ES-PA-HM-DRAFT-001`.
- [Machine-readable retained draft](../../ewaf/revised/policies/shared-v1-draft-1.json), with source provenance, five proposed choices, 15 open decisions, two separate readiness contracts and immutable-version/program-binding requirements.
- [Source extraction](source-extraction.txt) from the original DOCX, including equation text, 156 body paragraph positions and 19 XML tables (16 numbered captions). Original SHA-256 remains `b8b2af991278a19f2a42bce7e84100d06ae86541f691372cc715415c0002d6eb`.
- [Synthetic demonstration](synthetic-demonstration.json) and [separate readiness evidence](readiness.json). The demonstration reproduces 83.90, 62.81 and 12.22 from the unchanged document-example weights and assumed SI values; no evidence-to-SI mapping or weight authorization is claimed.
- `ewaf/revised/policy.py` provides immutable review snapshots, predecessor-linked proposed revisions, content checks, evaluation-time synthetic data readiness and exact snapshot replay. The retained catalog uses explicit revision lookup; it does not provide a mutable latest-policy binding.
- The existing revised official-readiness service retains all its prior blockers and additionally names the required immutable approved program-policy binding. It remains blocked for every official request.

## Executed checks

**85 tests passed across the final two runs.**

1. **41 pure synthetic tests passed**, 0.114 seconds: `ewaf.test_revised_policy` (17) and the existing `ewaf.test_revised_math` (24). This final run followed the additional document-rule digest check. An earlier run of the same 41 cases also passed.
2. **44 disposable MySQL tests passed**, 53.969 seconds: `ewaf.test_revised_policy_guards` (3), existing revised preview tests, and existing operational EWAF tests. Database identity was verified by the established fresh-instance launcher with `.env` disabled, isolated test-only grants/media and the separate `test_g12_disposable` schema. No application database was targeted. Log: `.local/dual-registration-20261024/temp/santolan-g12-tests-p6_j1usg/django.log`.
3. Python AST and scoped whitespace checks passed. `git diff --check` passed. Django system checks passed inside the disposable suite. No model or migration changes.

Commands:

```powershell
.venv/Scripts/python.exe -B -m unittest ewaf.test_revised_policy ewaf.test_revised_math -q
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test ewaf.test_revised_policy_guards ewaf.test_revised_preview ewaf.test_operational --testrunner scripts.revised_ewaf_test_runner.RevisedEWAFTestRunner --noinput --verbosity 1
git diff --check
```

Coverage includes exact source mapping/directions/scores; numerical bounds absent before evaluation; separate blocked policy and successful synthetic-data states; recalculated bounds after an accepted-pool change; constant columns and single-person pools; missing/stale/disputed/unlisted inputs; incomplete PA history; filtered and unresolved pools; exact capacity-boundary ties; immutable draft/history replay; stale and tampered revisions; forged approval metadata; and rejection of real-data claims by the synthetic adapter. Database tests verify no draft-driven approvals, weight reapproval, program mutations or operational records, and unchanged retained calculation/program tokens after revising a shared proposal. Existing preview permissions, audits, concurrency and operational regressions remain covered by their retained suites.

## Preservation

[Preservation evidence](preservation.json) compares all **1,278 pre-existing repository files**. **1,277 are byte-identical.** The sole existing-file edit is `ewaf/revised/services.py`, adding the program-policy-binding blocker without removing or changing any existing blocker. All historical mathematics, engines, configurations, tests, migrations, selection/publication/release services and unrelated unfinished work are unchanged. The original source DOCX is unchanged.

The source policy file has SHA-256 `cbb94d36ed7d779292a5b7b090b21e19b05c4dc8e220b56e9ecb6cc810af5fb7` using LF line endings. The canonical draft snapshot digest is `61267e5466d925a47435b9cad97c301d4f00228203aa190c1f53473e2da80a21`. The original source/weight-only Vault remains untouched.

## Remaining boundaries

This delivery is a **policy-review draft and synthetic contract**, not an approved configuration or an operational activation. It does not provide an approval writer, persist an approved policy/binding, capture accepted real-member inputs, authorize classifications, assign a policy to a program, or unblock publication. Persistent immutable approved-version binding and accepted-evidence integration remain prerequisites for a later authorized operational implementation. The document states the required contract explicitly; no in-memory demonstration reference is represented as a production database binding.

No working database was accessed, migrated, approved or changed. No code was installed into the running development runtime, no server restart was attempted, and no deployment, commit or remote push was performed. Browser testing was not required for this artifact/service change and was not performed. The DOCX was inspected structurally; no source layout/rendering claim is made.
