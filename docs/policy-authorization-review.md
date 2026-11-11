# Program policy authorization review — 2026-10-07

The owner requested review of the Announcements message “Authorize the program selection policy first.” The gate correctly requires an approved selection method, but the recovery instructions were incomplete: already-published legacy programs without recorded authorization could not choose Published again, forcing an unnecessary withdraw/republish sequence.

## Fix and Admin procedure

Announcements now links to the program review page and explains the missing step. Open **Programs → Review program → Edit program**, enter the Association-approved **Selection method** and **Calendar-photo instructions**, and save. In **Publication controls**, select **Authorize program policy**, record a reason, confirm and apply. This action appears only for already-published programs without recorded policy authorization; draft programs authorize their policies through normal publication.

Authorization keeps the existing program visibility and publication date. Existing publication permission, optimistic version, complete policies and atomic actor/time/reason/audit checks apply. It records no participant selection, bypasses no photo/eligibility/EWAF gate and cannot authorize an already-authorized policy again. The program version advances, so existing eligibility may require renewed review before final results. No institutional policy was invented, entered or authorized in actual records by this task.

## Observed validation

**89 program/announcement tests passed in 26.184 seconds**, including five new recovery/action tests covering the HTTP workflow, current version, missing fields/confirmation, unauthorized access, repeat attempts, audit rollback and announcement recovery links. Existing publication, application and masked-result regressions passed. `manage.py check --database default`, migration-drift checks and `git diff --check` passed. No migration was required; no actual program/member data was modified. The final selection-method help text was clarified after the passing run; it changes only explanatory wording.

Command: `.\.venv\Scripts\python.exe manage.py test programs announcements --noinput`. Synthetic records/uploads used the disposable test database. Private scoped backup/logs are under vault `.local/policy-review-20261007/`. This targeted verification supplements the earlier 272-test integration/browser record; it does not claim another full-suite/browser run.

## Files updated

- `programs/services.py`, `programs/views.py`, `programs/forms.py`: explicit authorization action, permissions/version/required-policy checks and clearer explanation.
- `announcements/results.py`: actionable validation message.
- `templates/programs/manage_detail.html`, `templates/announcements/result_draft.html`: recovery instructions and direct program link.
- `programs/test_policy_authorization.py`: five meaningful regression tests.
- Obsidian Guide, API/workflow contracts, User Manual, Development Progress and Documentation Changelog: authorization recovery and acceptance evidence.
- This current review note records the cause, procedure, changes and limits.
