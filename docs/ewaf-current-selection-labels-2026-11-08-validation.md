# EWAF current selection labels — November 8, 2026

## Authorized correction

The owner reported that already eligible applicants appeared as “Not selected · Previous ranking.” The workspace was combining the latest historical selection outcome with the current ranking's status. Eligibility, ranking, beneficiary selection, and confirmed assistance remain distinct.

For an eligible application with no decision on the displayed ranking, the decision column and applicant panel now show **Eligible · Awaiting selection**. An application that is no longer eligible receives the neutral **Awaiting selection** label; it is not described as eligible. Current-ranking decisions and confirmed assistance retain their existing labels. The awaiting-selection filter includes rows whose decisions belong to an older ranking. The redundant previous-ranking filter is removed.

The latest earlier decision remains available in a collapsed **Previous selection decision** section, with its ranking revision and date. Its revision continues to be used for optimistic concurrency. No score, rank, decision, release, capacity rule, permission, or readiness requirement was changed.

## Validation

- Four focused Django integration tests passed in a disposable native MySQL database, in 17.394 seconds. Coverage includes new rankings with earlier selected/not-selected decisions, current decision replacement, filters, unchanged decision/run records after GET, stale submissions, excluded applicants, and selection/unselection behavior.
- Test command: `.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_applicant_panel.ApplicantPanelTests.test_new_ranking_shows_eligible_applicants_awaiting_selection_and_retains_prior_decisions ewaf.test_applicant_panel.ApplicantPanelTests.test_selection_post_keeps_applicant_errors_and_success_in_panel ewaf.test_applicant_panel.ApplicantPanelTests.test_filters_empty_state_and_excluded_applicant_do_not_show_another_selection ewaf.test_unselect_assistance.UnselectAssistanceTests.test_button_replaces_selected_review_and_undo_restores_selection_and_capacity --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput`.
- Disposable database log: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-g35tvhvp\django.log`.
- A read-only render of the retained HM Focus workspace returned HTTP 200 with eight eligible/awaiting-selection labels and two assistance-received labels. An SQL guard rejected mutation statements; no business writes occurred.
- After restarting the retained local server, browser verification confirmed the same ten ranked rows, readable collapsed history, and no browser errors. Browser requests prohibited business mutations; login was the only permitted POST. The separate unranked-applicant table was excluded from the ranked-row count.
- `.venv\Scripts\python.exe -B scripts/current_development.py check` and `git -c core.safecrlf=false diff --check` passed.

Evidence: [browser results](ewaf-current-selection-labels-2026-11-08/browser-results.json), [ranking](ewaf-current-selection-labels-2026-11-08/ranking.png), [applicant panel](ewaf-current-selection-labels-2026-11-08/applicant-panel.png).

The separate stale ineligible outcome documented in [eligible readiness validation](ewaf-eligible-readiness-2026-11-08-validation.md) remains unresolved; this presentation correction does not bypass that program-level gate or automatically select beneficiaries.
