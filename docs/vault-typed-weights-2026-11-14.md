# Typed proposed weights in the Configuration Vault

The proposed percentage beside each weight slider is now a numeric field. Users can type up to two decimal places or move the slider; both use the existing priority-based allocation. Earlier priorities stay fixed, later priorities share the remaining allocation, and the final criterion remains an automatic, read-only remainder. Priority arrows make a different criterion directly adjustable.

Valid typing updates the slider, other proposed percentages, the exact 100% total and the existing AHP preview. A focused input retains the user's text until change/Enter, so intermediate input such as `5` while typing `50` does not replace the text. A stable allocation anchor prevents rounding drift while editing. Blank, malformed, overly precise and out-of-range entries remain visible with associated errors and block calculation and approval. Reset, slider changes and priority changes restore synchronized values. Late preview responses cannot restore approval after an invalid edit.

The AHP projection, limits, saved-version policy, authorization and server-side approval checks are unchanged. This release has no model changes, migrations, data imports or live configuration approvals. Asset versions are updated for all shared editor entry points.

## Validation

- `node scripts/ewaf_weight_slider_test.cjs`: 2,500 cascade/reorder cases and six exact SES examples passed.
- `node scripts/ewaf_weight_editor_dom_test.cjs`: shared editor, Vault cards and the legacy explicit-acceptance flow passed typing, synchronization, bounds, invalid-input recovery, priority, reset, approval and stale-response checks. Review caught and fixed a disabled Calculate button after resetting invalid input in the explicit-acceptance flow.
- `manage.py test ewaf.test_weight_input.WeightCompatibilityTests --noinput`: five AHP compatibility/provenance tests passed; Django checks reported no issues. This SimpleTestCase run used synthetic settings with no database connection.
- `node scripts/ewaf_weight_inputs_browser.cjs`: native Chrome passed character-by-character typing, 0.01% precision, slider/number keyboard controls, Enter/blur normalization without submitting, native field/form validity, invalid-input blocking, automatic remainder and priority changes. Six 1440/390/320px light/dark layouts passed; screenshots show the inputs fit. The existing calculated-results table scrolls within its container at 320px.
- Browser checks render the actual Django partial with production CSS/JavaScript and synthetic preview responses. They do not claim authenticated production interaction, backend AHP computation or approval persistence. Local evidence is in `.local/typed-weight-qa/`; no private records are used.
- JavaScript syntax and `git diff --check` passed.

## Release

Target: the existing `deployment/free-render-supabase` branch and `santolan-pwd-system` Render service. The implementation is prepared in an isolated worktree from the deployed repository; unrelated local development changes are excluded.

Commit `2e009d36dc3a59dc3b9065c9d37dc6d6461d4c33` reached **live** in deployment `dep-dbrtp5d6e07s7387u2m0` on November 14, 2026, at 04:00:31 UTC (12:00:31 PM Manila).

Six hosted HTTP checks passed: homepage and `/healthz/` returned 200; the anonymous Vault request retained its login redirect; the published editor JavaScript and both weight stylesheets returned 200 and matched the reviewed source after line-ending normalization. No application error logs appeared in the checked post-live interval. Authenticated production editing/approval was not exercised, and no live weights were saved. These results confirm delivery of the tested assets, not a new production AHP acceptance test.

The same scoped patch was applied to the original local development tree, preserving its other changes; all three local DOM scenarios passed. The release-evidence commit is documentation-only and does not require another deployment.
