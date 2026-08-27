# Instance 1 Foundations Handoff

## Implemented

A minimal `er_occupancy.foundations` package now supplies strict partial config
resolution, stable local-clock/sample/target/prediction contracts, explicit
provenance and eligibility vocabulary, flat serialization, synthetic smoke
execution, and focused tests. It contains no scientific pipeline implementation.

## Owned files

- `pyproject.toml`
- `README.md`
- `src/er_occupancy/__init__.py`
- `src/er_occupancy/foundations/__init__.py`
- `src/er_occupancy/foundations/config.py`
- `src/er_occupancy/foundations/contracts.py`
- `src/er_occupancy/foundations/provenance.py`
- `src/er_occupancy/foundations/smoke.py`
- `configs/foundations_smoke_default.yaml`
- `configs/foundations_smoke_override.yaml`
- `scripts/smoke_foundations.py`
- `tests/test_config.py`
- `tests/test_contracts.py`
- `tests/test_smoke.py`
- `docs/instance_01_foundations.md`
- `docs/handoffs/instance_01_foundations.md`

## Public API

Import from `er_occupancy.foundations`:

- Config: `load_yaml_mapping`, `merge_strict`, `resolve_config`,
  `save_resolved_config`, `ConfigError`, `UnknownConfigKeyError`,
  `ConfigStructureError`.
- Identity/contracts: `InstallationIdentity`, `LocalClockHour`,
  `HourlyEDStateIdentity`, `HistoryWindow`, `ForecastHorizon`, `SampleIdentity`,
  `TargetRecord`, `PredictionRecord`, `ContractValidationError`.
- State vocabulary: `ValueProvenance`, `EligibilityStatus`, `Eligibility`.
- Smoke callable: `er_occupancy.foundations.smoke.run_foundations_smoke`.

## Config behavior

```python
from er_occupancy.foundations import resolve_config, save_resolved_config

resolved = resolve_config("subsystem_default.yaml", "scenario_override.yaml")
save_resolved_config(resolved, "run/resolved_config.yaml")
```

Nested mappings merge; scalar/list values replace; unknown keys and mapping-shape
changes fail. Each downstream subsystem owns value validation and its canonical
default. Result-producing runs must save `resolved`.

## Contracts

- `LocalClockHour`: naive exact clock hour plus explicit IANA timezone metadata.
- `HistoryWindow`: N observations including origin (`t-N+1` through `t`).
- `ForecastHorizon`: positive normalized local-clock hours.
- `SampleIdentity`: installation/origin/window/horizon/target time/open target type.
- `TargetRecord`: directly observed finite scalar target; no target logic.
- `PredictionRecord`: finite scalar output plus run ID/open output type; no model logic.
- `ValueProvenance`: observed, reconstructed short gap, synthetic spring DST.
- `Eligibility`: decision container with an open reason code; no eligibility rules.

All `to_record()` outputs are flat and JSON/table friendly.

## Smoke check

```bash
python -m pip install -e '.[dev]'
python scripts/smoke_foundations.py
```

Expected: JSON containing `"status": "ok"`,
`"resolved_forecast_horizon_hours": 2`, and
`"unknown_key_rejected": true`.

## Tests

```bash
pytest
```

Coverage focuses on recursive strict merging, unknown-key and shape rejection,
YAML round-trip persistence, time/window/horizon validation, normalized spring
clock representation, target provenance, stable equality, eligibility vocabulary,
flat JSON serialization, and the smoke path.

## Downstream guidance

Instance 2 and later instances should import these identities and config helpers
rather than recreate them. Temporal preparation owns row normalization,
reconstruction, DST synthesis, and eligibility decisions. Target construction
owns target values/types; model code emits `PredictionRecord`; artifact-producing
runs persist their resolved config.

## Open issues

- Absolute occupancy and surge semantics remain unresolved and are not encoded.
- Facility-specific IANA timezone assignment remains upstream work.
- Scalar multi-output representation should be revisited only when a concrete
  approved model requires it.
- A source-data/run manifest remains deferred until artifact producers establish
  a shared requirement.

## Git

- Branch: `instance-01-foundations`
- Implementation commit: `a7bffa4` (`Establish shared foundations and contracts`)
- Draft PR: [#1 — Establish shared foundations and contracts](https://github.com/grigorovich-sergey/ER_occupancy_project/pull/1)
- Status: open for user review; not merged.
