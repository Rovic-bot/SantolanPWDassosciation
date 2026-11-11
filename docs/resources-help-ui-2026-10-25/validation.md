# Resources & Help presentation — 2026-10-25

The owner requested a clean, professional Resources & Help page inspired by the supplied screenshot.

## Delivered layout

The public index now has a compact introduction, two primary action cards for program application tracking and referral requests, a three-column grid of six resource topics, and a compact accessibility/Help Desk strip. Topic cards display published excerpts and detail links. Unpublished topics show a short availability message; existing referral and membership guides remain directly accessible. Smaller layouts stack the cards and preserve readable text and keyboard focus.

The scoped stylesheet also simplifies the navigation treatment and footer on this page. Existing public navigation destinations, current-page indication, display controls, topic anchors, PDAO guidance link, program information, evaluation guidance and published results remain available. Published external verification links retain their reviewed source and explicit external-service boundary.

Tracking and referral buttons continue to respect their existing feature settings. Verification, referral intake, email delivery, private records and CMS publication rules are unchanged. Resource excerpts still come from published snapshots and remain escaped. The index collects no information and creates no form or account.

Changed files: `templates/public/resources/index.html`, new `static/css/resources-help.css`, and one existing UI heading assertion in `assistance/test_referrals.py`. No view, service, database model, migration or application data changed.

## Verification

**62 focused tests passed** in 4.047 seconds using disposable native MySQL with `.env` disabled:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test core.tests.test_resources core.tests.test_public_portal assistance.test_referrals programs.test_tracking --testrunner scripts.referral_test_runner.ReferralTestRunner --noinput --verbosity 1
```

Coverage includes published-only resource access, draft privacy, escaped content, reviewed external sources, public navigation, referral entry and secure application tracking with feature gates. No real requests were submitted or email sent during verification.

Synthetic page renders with database access prohibited checked empty, published and disabled-feature states: one main heading, six topic cards, unique IDs, valid local anchors, escaped content, no submitting forms, and correct entry links. The synchronized runtime passed Django's database configuration check. Git and changed-file whitespace checks passed.

Playwright/Chrome failed to launch with `spawn EPERM`. No screenshot comparison or responsive-browser pass is claimed. The synthetic previews, source/runtime backups, baseline hashes and render results remain under ignored `.local/resources-help-ui-20261025/`.

## Runtime

All three changed files were synchronized to `.local/dual-registration-20261024/runtime/` after both existing runtime files matched their recorded baselines. Resulting hashes were verified and other unfinished work was preserved.

The restart script verified the development website on port 8003, but Windows denied stopping its Python process. Run `Restart System.cmd` locally and refresh Resources & Help to load the cached template change. No migration, GitHub push or hosted deployment was performed for this change.
