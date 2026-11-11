# G16 source fixtures, revision 1

These invented mathematical examples are development fixtures, not Association
weights, evidence definitions, directions, bounds, admission or capacity rules.
The `SYN-G16-*` identities have no application/member/release relationship. No
fixture loader resolves an identity through a database.

- `high-first-v1.json`: exact endpoint and equal-score examples; illustrative
  capacity crosses an equality group without selecting anybody.
- `low-first-v1.json`: explicitly reversed comparison scenario, same arithmetic.
- `precision-v1.json`: nonuniform reference judgments and two distinct 50-digit
  G15 results that collapse under float conversion or low-precision negation.
- `incomplete-v1.json`: missing values prevent comparison of the entire pool.

The source registry in `ewaf/ranking_fixtures.py` pins the complete file bytes with
SHA-256. Each fixture additionally binds its common contract, complete manifest,
individual inputs and calculations using the G16 digest domain. Loading an
allowlisted name checks the byte checksum; comparison independently replays G14
and G15 and verifies all mathematical evidence. A content hash is not policy
authority. Source modifications require review and a new version/pin; the runner
does not write or update these files.

Run from the repository root:

```
.venv/Scripts/python.exe -B scripts/g16_synthetic_diagnostics.py high-first-v1
```

Only registered names are accepted, never a file path or arbitrary scores.
Exit status 0 means a complete synthetic comparison; status 2 includes an
incomplete diagnostic. Neither authorizes operational use. The runner does not
initialize Django settings, open a database, or load `.env`.

Group spans are diagnostic positions, not operational rank numbers. Synthetic IDs
only stabilize presentation inside exact equal-score groups. All source text and
G14/G15 traces remain full precision; no display rounding or epsilon is applied.
Source-proposal references, actual applicants and their score-free readiness
records never feed these numerical fixtures.
