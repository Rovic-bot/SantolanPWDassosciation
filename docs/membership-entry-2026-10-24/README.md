# Public Membership registration entry

2026-10-24. The owner clarified that Public Portal > Membership must expose the kiosk-inspired application flow: form submission, application reference, retained receipt/form and authorized Help Desk retrieval. This changes discoverability, not the existing activation or institutional contracts. The accepted milestone remains 70%.

`templates/membership/guidelines.html` now places a clearly titled Online membership registration section before the requirements. It explains the four steps and that a pending reference is not an official member number. With the reviewed intake policy enabled, its single primary button opens the existing `/membership/registration/apply/` form. When disabled, the section remains visible with a truthful unavailable status and Help Desk alternative; it does not pretend that submission is enabled. The former duplicate sidebar button was removed. Existing requirements, onsite guidance, PDAO separation, navigation and styles remain unchanged.

`membership/test_registration_intake.py` strengthens the existing guidance test: visible section in both states; exactly one working form link when enabled; no active form link when disabled; pending-versus-approved wording; unchanged public order; and no intake/Member creation from guidance/form viewing.

Actual command:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.test_registration_intake membership.test_registration_finish core.tests.test_public_portal --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
```

**63 tests passed in 6.156s, exit 0**, in fresh verified disposable MySQL with synthetic data and separate private media. The focused tests include existing submission/reference/retry/private-access and Finish safeguards. `git diff --check` passed. All 267 protected files match the original Phase 1 baseline; Section 8 remains byte-identical. No new EWAF test run or browser/screen-reader acceptance is claimed for this wording/template change. Earlier regression results remain historical evidence.

The prior local startup attempt found exactly three pending non-EWAF migrations on `santolan_pwd` at `127.0.0.1:3307`: membership 0006, members 0006 and core 0002. Their read-only plans contained only the respective reviewed forward migration. The unchanged launcher refused startup; no migration was applied. The normal website is not running. The owner's separate working-database migration authorization remains pending.

Schema application alone will not open registration. Ordinary settings still omit `ASSOCIATION_REGISTRATION_POLICY`; actual privacy/retention, staff/onsite processing and session/request/upload security configuration need approved values and provenance. The existing tested form, AMR reference and receipt foundation are implemented, but real collection and membership handoff remain unavailable. No policy, credential, database, service gate, reference allocation, EWAF, migration or startup-guard code changed here. Nothing was committed, pushed or deployed.
