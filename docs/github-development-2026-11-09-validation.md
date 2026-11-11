# Current port-8013 source publication - November 9, 2026

The owner requested pushing the exact system running at `http://127.0.0.1:8013/`, including all frontend and backend features. The listening Python process was verified to use this repository and `scripts/ewaf_twelve_demo.py`; the retained instance health check passed. The existing private repository is `Rovic-bot/capstone`, branch `dev-local-8013-2026-11-06`, initially at `dfd20eb`. The branch was synchronized with its upstream before publication.

## Included source

This snapshot includes every changed/new application module, model and migration; all templates, CSS, JavaScript and deployable images; the existing certificate template; configuration and startup scripts; changed/new tests and browser harnesses; and text validation notes. It preserves the working application rather than substituting an older deployment branch or changing business rules during publication.

The accumulated changes cover public pages and accessibility, Admin/dashboard layouts, Association membership invitation/verification/approval emails, saved PDAO applications and review/claim notices, member filtering and document previews, program drafts/schedules/reviews/receipts, announcements and incremental certificate publication, assistance-release controls, and EWAF readiness/selection/reranking behavior. The dated domain validations remain the detailed implementation evidence.

The repository's established publication scope excludes `.env`, `.local`, credentials, database files/backups, private uploads, generated browser screenshots/JSON/PDF evidence, unused original `Assets/`, design-reference screenshots in `new pages/`, and local certificate previews. Required public images are included under `static/`, and the deployed certificate source remains `announcements/certificate_templates/assistance.docx`. No required frontend or backend application file is excluded by this artifact filtering.

## Current runtime configuration

The retained local launcher loads `config.current_development_settings`, then applies its existing private `registration-policy.json`. It does not use the ordinary `.env`. The settings below were read from that configuration without exposing credentials:

| Setting | Port 8013 |
| --- | --- |
| `EWAF_VAULT_ENABLED` | `True` |
| `EWAF_DATASET_POLICY_ENABLED` | `True` |
| `EWAF_DATASET_SCORING_ENABLED` | `True` |
| `PROGRAM_APPLICATION_WORKFLOW_ENABLED` | `True` |
| `PDAO_ENFORCEMENT_ENABLED` | `False` |
| `PROGRAM_TRACKING_ENABLED` | `True` |
| `PROGRAM_TRACKING_QR_ENABLED` | `True` |
| `ONLINE_MEMBERSHIP_ENABLED` | `False`; public Association registration is enabled by the launcher policy below |
| `PDAO_REGISTRATION_ENABLED` | `True` |
| `SHORT_REFERENCES_ENABLED` | `False` |
| `REFERRAL_ENABLED` | `True` |
| `EWAF_FICTIONAL_DEMO` | `False` |
| `CERTIFICATE_EMAIL_PROVIDER` | `gmail` |
| `CERTIFICATE_EMAIL_BACKGROUND` | `True` |
| Default Django email backend | `django.core.mail.backends.filebased.EmailBackend` |

The active Association policy uses version `owner-online-20261109-v1`, form `association-word-20261109-v1`, privacy notice `association-online-20261109-v1`, and applicant profile `association_pdf_v1`. Public, staff, onsite, correction and handoff flags are enabled in that local policy. Its retained onsite method is a synthetic development fixture; it is not a newly approved production verification method. `config/registration_workflow.py` contains the current source-controlled online policy, including the office invitation and final approval wording. The separate local policy and institution-specific settings must be reviewed when provisioning another environment; copying a boolean alone does not reproduce its full configuration.

Association Gmail sender credentials and configured membership/PRPWD settings are stored separately in the database. The file-based Django default does not mean every business email uses that backend; the application includes its existing explicit Gmail delivery paths. Certificate generation requires LibreOffice (`CERTIFICATE_OFFICE_EXECUTABLE` or `soffice` on PATH); its configured local executable was present.

Fresh installations must use their own MySQL database, private storage, secrets, sender connection and configuration. Local launchers intentionally require the retained runtime manifest and preserve its model-synchronized database. Do not copy its disabled migration map into a normal deployment or run blanket historical migrations against that retained database. This push neither migrates application data nor deploys a public website.

## Verification

- Django's retained-database configuration check passed.
- Migration drift check with the normal migration map: no changes detected. This check made no schema changes.
- Syntax checks passed for all 145 changed/new Python files and 66 JavaScript files inventoried before the publication documentation update.
- Secret-pattern scanning of the complete source selection found only three existing synthetic test fixtures. No credential or private-runtime path was selected.
- Git whitespace checks passed after removing one extra trailing blank line from a new test file. No running application behavior was edited for this publication.
- The 57 changed/new domain test modules ran **630 tests: 591 passed, six failed assertions and 33 errors**, in 242.678 seconds. The broader run is not a passing regression gate; its unresolved cases are listed below. The earlier focused member-print/shared-dialog run passed all 23 checks, as recorded in [its validation](member-registration-preview-2026-11-09/validation.md).
- Before the commit, all frontend/backend source changes were staged, and no application source remained untracked. The source inventory confirmed that publication preparation changed only this documentation, the README and the trailing blank line in that test.

All regression tests use the verified fresh-instance G12 launcher with disposable native MySQL and synthetic data, never the retained application database. This is a source publication record, not a claim of production acceptance or a physical-printer test.

### Unresolved broader regression results

| Count | Suite / assertion | Observed result |
| --- | --- | --- |
| 7 errors | `membership.test_registration_inbox.RegistrationInboxTests` setup | The current membership approval guard requires a successfully sent office invitation; these fixture approvals were rejected. |
| 26 errors | EWAF applicant-panel, delivery and rolling-pool fixture setup | The current actual-receipt guard requires publication of the selected member first; these fixture releases were rejected. |
| 2 failures | `announcements.test_public_results.PublicResultsTests` | Assertions expected a direct result URL and a separate Results active-navigation label. |
| 1 failure | `core.tests.test_home_featured_event.HomeFeaturedEventTests` | The expected `#application-information` link was absent from the rendered response. |
| 1 failure | `core.tests.test_public_portal.PublicPortalTests` | The old registration-closed assertion expected no form; the response contained a form. |
| 1 failure | `events.tests.EventWorkflowTests` | The expected event name was absent from member-history output. |
| 1 failure | `membership.test_review_inbox_refresh.PDAOInboxStatusTests` | The expected tab-count dictionary omitted the current `needs_info` state. |

These failures are retained and disclosed instead of changing the running workflow as part of a source-backup request. They need a separate regression-alignment review; no assertion was weakened or failing test skipped. The private full run log is in the disposable `santolan-g12-tests-jkbwd7rq` artifact directory. Application data was not used for the tests.
