# Quebec ER Occupancy Forecasting

Research software for province-wide, short-horizon forecasting of Quebec
emergency-department conditions. The repository is organized as narrow,
contract-compatible subsystems so that scientific alternatives can be changed
through configuration rather than pipeline rewrites.

The implemented layers are:

- `er_occupancy.foundations`: shared identities, provenance vocabulary, and
  strict canonical-default plus partial-override YAML configuration;
- `er_occupancy.data_access`: canonical loading, normalization, structural
  validation, deterministic subsetting, and file-level provenance for approved
  processed hourly ED files.

See [`docs/instance_01_foundations.md`](docs/instance_01_foundations.md) for the
foundation API and [`docs/instance_02_data_access.md`](docs/instance_02_data_access.md)
for the standardized ED-state table contract.

## Development setup

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
python scripts/smoke_foundations.py
python scripts/smoke_data_access.py
```

The smoke paths use synthetic values/files only; they do not access real ER data.

## Current architecture

```text
src/er_occupancy/foundations/  shared contracts and config mechanism
src/er_occupancy/data_access/  processed-file access and standardized ED table
configs/                       canonical examples and partial overrides
scripts/                       thin executable entry points
tests/                         focused subsystem tests
docs/                          subsystem documentation and handoffs
```

Temporal preparation, targets, features, models, evaluation, and experiment
orchestration will be implemented by later owned subsystems.
