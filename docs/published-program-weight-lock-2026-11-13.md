# EWAF weights locked by results publication — November 13, 2026

A program's weights remain adjustable through the Configuration Vault until its
**program results are published in Announcements**. Publishing the program itself,
publishing a linked program notice, or preparing a private results draft does not
lock its weights.

Once results are published, subsequent rankings use the exact approved weight
version used by the ranking behind those results. Later Vault approvals continue
to apply to other programs without published results. Ranking generation remains
available under the normal permissions and readiness requirements.

## Retained ranking basis

The lock is derived from the first audited `results_published` event, its immutable
result revision, and the append-only EWAF ranking and decision history. Withdrawing,
archiving, preparing a replacement, or republishing results cannot erase the lock.

For recorded selections, use the ranking attached to each selected decision at
that first publication. This can be an earlier ranking than the latest calculation
or Vault approval. The weight override in that saved ranking takes precedence over
the configuration's original weight version. Strict results publication retains
its validated current ranking.

Selections spanning different weight versions require review against a consistent
ranking before publication; the system does not silently choose one. An applicant
list explicitly published without a ranking retains the approved weight version
available at that publication time. Missing publication/weight history blocks
substitution of today's weights and requests review.

Both historical dataset bindings and current fixed-scoring bindings are supported.
The legacy configuration writer and policy rebinding also enforce the results lock.
The ranking page, selection panel, and Vault describe the same rule.

## Scope and verification

No model changes, migrations, seed records, or historical rewrites are required.
Public result payloads, saved calculations, selection decisions, and receipts are
preserved. AHP computation and scoring formulas are unchanged.

Regression coverage in `ewaf.test_publication_weights` includes program notices,
draft results, new programs, independent programs, selected older rankings,
bound weights without overrides, fixed-scoring HTTP ranking, strict and recorded
publication, repeated ranking, withdrawal/republication, permission enforcement,
rebinding rejection, mixed weight versions, and publication-audit rollback.

All 18 focused checks passed (15 results-weight regressions and 3 fixed-scoring
definition checks). Django's system check reported no issues and
`git diff --check` passed. Eight of nine existing selection-reason checks also
passed; the remaining baseline failure is described below.

Tests run against freshly initialized disposable PostgreSQL 18 clusters with
temporary media, blocked external network access, and in-memory email delivery.
The unchanged historical announcement test
`SelectionReasonTests.test_http_publication_saves_public_explanation_and_masks_names`
fails on the baseline deployment source as well: it expects explanation text
directly on the announcement list. Its assertion was not changed.

Deployment target is the existing `santolan-pwd-system` Render service, in the
user-confirmed **My workspace**, on `deployment/free-render-supabase`. Work uses an
isolated checkout and leaves the original unfinished local development work intact.
