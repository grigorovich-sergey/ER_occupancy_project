# Instance 1 — Foundations / Shared Contracts

## Responsibility and boundary

`er_occupancy.foundations` is the small shared layer used to exchange stable
identities and resolve strict configuration overrides. It contains no source
data reconstruction, interpolation, DST-row creation, target construction,
feature engineering, modeling, evaluation, or experiment orchestration.

The foundation validates structural invariants that are already project rules.
The scientific subsystem that creates a record remains responsible for deciding
eligibility, computing values, and documenting its open-vocabulary reason and
type codes.

## File map

| Path | Purpose |
|---|---|
| `src/er_occupancy/foundations/config.py` | Strict YAML loading, merging, and resolved-config persistence |
| `src/er_occupancy/foundations/contracts.py` | Immutable time, state, sample, target, and prediction contracts |
| `src/er_occupancy/foundations/provenance.py` | Shared provenance enum and eligibility representation |
| `src/er_occupancy/foundations/smoke.py` | Reusable synthetic smoke function and CLI |
| `configs/foundations_smoke_*.yaml` | Mechanism-only default and partial-override examples |
| `scripts/smoke_foundations.py` | Thin repository smoke runner |
| `tests/` | Focused foundation tests |

All stable imports are re-exported from `er_occupancy.foundations`.

## Canonical contracts

### Time and installation identity

- `InstallationIdentity`: stable string ID plus an optional display name. The
  name is metadata and is not part of modeling sample identity.
- `LocalClockHour`: an exact, timezone-naive `datetime` plus a separate,
  validated IANA timezone name. Naive time is deliberate: the normalized local
  clock sequence can contain the synthetic spring `02:00` and only one autumn
  `01:00`.
- `HourlyEDStateIdentity`: installation ID plus `LocalClockHour`.

Do not convert `LocalClockHour` to UTC to determine project hour order. The
temporal-preparation subsystem owns normalization of source rows. Once the
normalized sequence exists, local clock arithmetic applies:

- spring `02:00` is present, flagged `synthetic_spring_dst`, and never a target;
- the single autumn `01:00` is ordinary, and the overwritten physical hour is
  intentionally ignored.

### Window, horizon, and sample identity

- `HistoryWindow(hours=N)` means exactly `N` hourly observations ending at and
  including forecast origin `t`: `t-N+1, ..., t`.
- `ForecastHorizon(hours=H)` means `H` normalized local clock hours after `t`.
- `SampleIdentity` joins installation ID, forecast origin, history window,
  horizon, target time, and an open validated `target_type` string.

`SampleIdentity.from_origin(...)` derives the target time. Direct construction
validates that a supplied target time agrees with the horizon. This identifies a
candidate sample only; it does not make a synthetic spring target eligible.

### Target and prediction records

- `TargetRecord` links a finite numeric/boolean value to `SampleIdentity` and
  enforces the established rule that targets are directly observed.
- `PredictionRecord` links a finite scalar prediction and `model_run_id` to the
  same identity. Its open validated `output_type` distinguishes point estimates,
  probabilities, or future approved scalar outputs without fixing model logic.

These records deliberately do not define absolute-occupancy column semantics,
surge, model parameters, feature values, metrics, or scientific thresholds.

Every contract has `to_record()`, producing a flat dictionary of ordinary
string, integer, float, boolean, or null values suitable for JSON or tabular
construction. Large datasets should use these flat fields directly rather than
store millions of nested Python contract objects.

## Provenance and eligibility

`ValueProvenance` is a closed vocabulary because all three states are established
project rules:

- `observed`
- `reconstructed_short_gap`
- `synthetic_spring_dst`

The enum communicates provenance; it performs no interpolation.

`Eligibility` contains `EligibilityStatus.ELIGIBLE` or `.INELIGIBLE` and an
optional open `reason_code`. Reason codes use lowercase identifiers such as
`missing_target`; each scientific subsystem owns and documents the codes for
rules it applies. The foundation does not decide eligibility.

## Strict configuration API

Each downstream subsystem should own one canonical default YAML file and expose
an optional partial override:

```python
from er_occupancy.foundations import resolve_config, save_resolved_config

config = resolve_config(
    "configs/targets_default.yaml",
    "configs/scenarios/occupancy_horizon_4h.yaml",
)
save_resolved_config(config, "artifacts/run_001/resolved_config.yaml")
```

The behavior is:

1. YAML roots must be mappings.
2. Nested mappings merge recursively.
3. Scalars and lists replace the canonical value in full.
4. Unknown keys fail with their full dotted path.
5. A mapping cannot be replaced by a non-mapping or vice versa.
6. Inputs are not mutated.

The generic mechanism intentionally does not validate subsystem-specific value
types or scientific combinations. The owning subsystem should validate its
resolved section after calling `resolve_config`. Every result-producing run
must save the fully resolved configuration alongside its artifacts.

Never edit canonical defaults to express an experiment. Add a partial override.

## Smoke execution

After installing the package in editable mode:

```bash
python -m pip install -e '.[dev]'
python scripts/smoke_foundations.py
```

Equivalent reusable call:

```python
from er_occupancy.foundations.smoke import run_foundations_smoke

result = run_foundations_smoke(
    "configs/foundations_smoke_default.yaml",
    "configs/foundations_smoke_override.yaml",
)
assert result["status"] == "ok"
```

Expected output is JSON with `status: "ok"`, a resolved two-hour horizon, flat
sample/target/prediction records, the three provenance values, an eligible
status, and `unknown_key_rejected: true`.

## Compatibility and extension guidance

- Depend on the public exports from `er_occupancy.foundations` rather than
  copying identity, provenance, or config logic.
- Keep target types, prediction output types, and ineligibility reasons as
  documented lowercase codes owned by their scientific subsystem.
- Propose a foundation change through a handoff before adding a shared enum or
  contract field. Do not add speculative fields for a single implementation.
- Add columns to large tables using the names emitted by `to_record()`.
- Source-data version/checksum and resolved run configuration belong in run or
  dataset artifact metadata; they are not part of sample equality.

## Open issues

- Exact absolute-occupancy target semantics and surge target types remain owned
  by target construction.
- Prediction outputs are currently scalar. A later approved multi-output model
  may require either one record per named output or a minimal contract extension.
- Facility-specific timezone assignment is an upstream data/identity decision;
  the foundation requires an explicit IANA value and supplies no provincial
  default.
- A shared source-data/run manifest should be introduced only when artifact
  producers establish its concrete requirements.
