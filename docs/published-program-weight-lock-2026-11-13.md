# Published program weight lock — November 13, 2026

The owner requires publication to freeze a program's EWAF criterion weights.
Administrators can continue creating programs and approving weights for unpublished
programs. Published programs can continue generating rankings using their retained
approved weights. Unpublishing does not reopen the weights.

## Implementation

- Composite ranking weight selection uses the program configuration's retained
  `weight_version` after publication instead of the current global Vault approval.
- An unpublished fixed-scoring draft binds the latest approved composite weights
  at its first publication. Configuration revisions remain append-only.
- Completing an already-published weights-only intake preserves its original Vault
  revision. Global approvals cannot replace a published program's weight version
  through inheritance, shared-policy binding, or the legacy configuration writer.
- The ranking page and program selection panel explain the lock. The Vault remains
  editable and explains that new approvals serve unpublished programs.
- Historical runs retain their saved snapshots, including older runs that used a
  later global weight override. Their calculations are not rewritten. A new ranking
  uses the program's retained publication weights and the usual current inputs.
- Ranking permissions, eligibility, human selection, assistance release, and audit
  requirements continue to apply.

No model changes, schema migrations, seed data, or operational data updates are
required. The scoring formula and AHP weight calculation are unchanged.

## Verification

The final focused run passed all 14 tests: 11 in
`ewaf.test_publication_weights` and 3 in `ewaf.test_fixed_scoring`. Django's system
check reported no issues. `git diff --check` passed.

The regression tests cover later weight approvals, unchanged weights and scores,
repeated ranking generation, fixed-scoring HTTP ranking generation, new programs,
draft refresh at publication, unpublish/republish, legacy intake completion,
permission rejection, direct rebinding rejection, audit rollback, and historical
run replay. Fictional fixtures run in a newly initialized loopback PostgreSQL 18
cluster with a disposable database and temporary media; external sockets and email
delivery are disabled during the tests.

A broader run of the initial 10 regressions plus `ewaf.test_fixed_scoring`,
`programs.test_one_click_publication`, and `programs.test_mandatory_ewaf` completed
41 tests: 30 passed and 11 test methods failed. The same 11 methods failed in an
unchanged checkout of `ea37b6574e2322e1f20c2a6a0d8108989258b3a1` (20 passed,
11 failed). Those older fixtures expect superseded publication/configuration
behavior or omit the required results-selection reason. They were not changed to
make this fix pass; the complete historical suite is not claimed green.

## Deployment scope

Target: the existing `santolan-pwd-system` Render service in the user-confirmed
**My workspace**, using `deployment/free-render-supabase`. Work was prepared in an
isolated checkout, preserving the original local development work. The service's
startup performs checks and static collection; it does not run migrations or seed
records. Production verification uses deployment status and read-only requests.
