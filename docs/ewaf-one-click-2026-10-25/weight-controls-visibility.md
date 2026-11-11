# Configuration Vault weight control placement

The existing weight editor was below the large Criterion data sources panel, outside the area shown in the owner's screenshot. The editor now appears first, under **Adjust criterion weights**, with the source table below it. Its script URL includes a new version parameter to refresh a cached earlier script.

Only `templates/ewaf/vault.html` and its local development-runtime copy changed. The removed policy fields remain absent. No weighting algorithm, scoring policy, permission, configuration, calculation, or database record changed. The proposed independent controls and HM-remainder policy remain governed by the separate adjustable-weight clarification; this layout fix does not implement or activate that proposal.

A fresh-process runtime render returned 200 and verified the editor precedes the source table, the editor and script are included, and the removed policy fields remain absent. Source/runtime templates match; whitespace and `git diff --check` pass. This does not claim browser visual verification.

The current development server uses `--noreload`; its process changed after the user's earlier restart. The new placement requires another manual restart using `Restart System.cmd`. On the already running layout, the existing editor is below the source table. No agent restart was attempted after the earlier automatic approval rejection.
