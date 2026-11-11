# G18-A reference computation fixture

`computation-reference-v1.json` transcribes Computation.docx table 2 by **both row
and column criterion names**. Source order is PA, SI, ES, ND, PR; G14 order is
SI, ES, PA, ND, PR. The fixture is a mathematical reference, not Association
approval, an applicant record, a seed, or a default configuration.

The ten G14 pairs use terminating decimal strings. G14 derives repeating
reciprocals internally under its unchanged 50-digit ROUND_HALF_EVEN profile.
The original fractions remain in `matrix_by_criterion`; rounded document
weights never become inputs. Full-matrix input of a 50-digit derived reciprocal
would exceed the existing 40-digit judgment parser; that parser is not relaxed.

Expected totals, normalized matrix, weights, WSV, CV, estimated lambda, CI and CR
were calculated independently from the named source fractions under a separate
50-digit Decimal calculation, then compared exactly with G14. Tests also derive
every stage using exact rational Fraction arithmetic and bound finite-profile
error below 1e-47. This is an arithmetic verification bound, not a business rule.
The fixture pins the small finite-context weight-sum residual instead of
silently renormalizing weights. The rational weights sum exactly to one.

The tests have no dependency on source binaries, local paths, applicant values,
or a database. Existing G12–G17, durable and migration-preservation regressions
run separately through the disposable MySQL harness. See the G18-A crosswalk
and validation report under `docs/` for source fingerprints and open decisions.
