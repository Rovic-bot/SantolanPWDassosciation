# Phase 4 checkpoint — CMS and public resources

2026-10-23. **Partial.** Resources & Help and its CMS lifecycle are implemented and isolated tests pass. Referral tickets, RSVP, live event audience-field integration and institution-reviewed content remain blocked or deferred. Accepted milestone stays 70%; nothing was deployed or published to the working database.

## Features and exact files

- `core/models.py`, `core/migrations/0002_resource_publication_metadata.py`: eight CMS keys (seven required resource topics plus separately reviewed external ID-verification link), optional provider/source/review-date metadata and archive flag. Migration adds four fields and expands key choices without changing its storage type. Dependency: core 0001 only. SHA-256 `25245202eb5c7af929aef66e2664779172c5f165ca2ddcd2d241b36dd4a52454`.
- `core/content.py`: existing draft/edit/publish/withdraw/history reused; resource publication requires HTTPS source without credentials, provider, actual review date and explicit source-review confirmation. Resource archiving withdraws the snapshot and retains history. Draft metadata never replaces published metadata. Fresh permission checks and audit failure rollback apply. Existing page editing remains supported. EWAF fallback wording no longer describes business ranks; generic membership fallback wording points to the maintained guide and onsite requirements. Existing published content is not rewritten automatically.
- `core/resources.py`, `core/urls.py`, `templates/public/resources/index.html`, `templates/public/resources/detail.html`: public resource topics and published detail snapshots; drafts/withdrawn/archived details return 404. Canonical Association/PDAO guides, program instructions, Results and Help Desk links avoid duplicate records. No personal-data form or membership check. External verification appears only after a distinct reviewed CMS publication and is labeled **PWD ID Verification — External Website**; no API, scraping, authenticity claim or applicant-data transmission is added.
- `core/context_processors.py`, `templates/public/base.html`, `templates/public/home.html`: Resources & Help appended after the seven existing destinations, current-page indication, Home shortcut and footer link. Eight Admin groups and existing minimalist sidebar/styles remain unchanged; content management stays in Announcements & CMS.
- `core/tests/test_resources.py`, `core/tests/test_public_portal.py`: eight new CMS/resource tests; the existing navigation assertion now preserves the original seven and expects the explicitly authorized eighth. No EWAF assertion changed.
- Reviewed test-runner allowlist, this directory's design/report/logs/evidence and progress record: schema and checkpoint evidence.

No dependency, configuration, permission assignment, historical migration or protected-file change. Sources are not fetched automatically and no legal claims, jobs, contact numbers, observance dates or entitlements are invented. Empty topics honestly say reviewed information is not yet published. This is a working CMS capability, not a claim that all content has been supplied/accepted.

## Actual tests

**102 CMS/navigation/event/result/migration tests passed in 27.517s.** A separate **102 unchanged EWAF tests passed in 81.333s.** Both exited 0 with no failures/errors/skips. These are separate actual runs, not historical counts. Logs and exact identities/hashes are in this directory and `verification.json`.

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations core --name resource_publication_metadata --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test core.tests.test_resources core.tests.test_content core.tests.test_public_portal core.tests.test_workspace_navigation scripts.remaining_schema_tests announcements.test_public_results events.tests events.test_observances --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_computation_reference ewaf.test_four_criterion_reference ewaf.test_ahp_validation ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_four_kernel ewaf.test_operational ewaf.test_delivery ewaf.test_membership_writers ewaf.test_access_writers --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
```

Fresh disposable MySQL, disabled `.env`, isolated grants and temporary private media were verified first. The exact three reviewed new migrations were reversed/reapplied on synthetic model-derived schema/history; no historical migration file executed and no working database accessed. Core metadata reversal was tested only with empty content tables; reversing after resource publication would lose metadata, so normal rollback is withdrawal/disable and retained history, not dropping fields. Faithful historical-baseline/backup/restore evidence remains limited and is addressed in Phase 5 readiness notes.

All 267 protected files and pre-existing migrations match baseline. Original/integrated Section 8 remains byte-identical, 8,384 bytes, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. Existing result masks/allowlists and decision/publication/release behavior passed selected unchanged regressions.

## Privacy, accessibility, blockers and next work

Public views expose only published text/source metadata. Output is escaped; private CMS routes, CSRF, separate publish permission, stale writes, revoked permission and audit rollback were tested. Invalid source URLs and future review dates are refused. No attachment or personal-record endpoint is added. The supplied content still needs a competent source/publisher review; an HTTPS link alone is not a truth guarantee or freshness expiry policy.

New pages use semantic headings, topic navigation, text alternatives, ordinary links, native labels and existing responsive/display/reduced-motion controls. Browser, contrast/zoom and accessibility-tree evidence is reserved for Phase 5; no representative screen-reader/UAT/WCAG claim is made here.

Referral record lifecycle/reference/access/minimal fields are unspecified in §§5.6/7.11; no fabricated Program or assistance record was created. Member verification, staff authority and privacy/retention still need approval. RSVP remains unavailable under IQ-11. New event admission/audience fields would need a compatible binding to protected program terms/source invalidation; that dependency is deferred rather than creating unlocked parallel admission rules. Existing scheduled events, restricted attendance and annual-observance controls remain unchanged.

Public numerical ranks, eligible lists, expanded identifiers, Household Monthly Income, PDAO collection/forwarding and all unapproved private lookup/recovery remain unavailable. Client review of source content, operation ownership (IQ-16), and target-specific migration/activation remain outstanding. The benefit is one maintainable public guidance destination with reviewable publication history; known risks are stale or inaccurate later-authored content and the still-unmigrated working schema.

Phase 5 may independently run available integrated regressions, synthetic UI/security tests and prepare handover/UAT/recovery instructions. It cannot turn these blocked features into operational services or claim institutional acceptance.
