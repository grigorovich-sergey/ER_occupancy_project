# Quebec ER Occupancy Forecasting

Research software for province-wide, short-horizon forecasting of Quebec
emergency-department conditions. The repository is organized as narrow,
contract-compatible subsystems so that scientific alternatives can be changed
through configuration rather than pipeline rewrites.

The first implemented layer is the shared foundation package:

- strict canonical-default plus partial-override YAML configuration;
- local clock-hour, sample, target, and prediction identities;
- reconstruction/DST provenance and eligibility vocabulary;
- deterministic synthetic smoke checks.

See [`docs/instance_01_foundations.md`](docs/instance_01_foundations.md) for the
public API and downstream integration guidance.

## Development setup

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
python scripts/smoke_foundations.py
```

The smoke path uses synthetic values only; it does not access ER data.

## Current architecture

```text
src/er_occupancy/foundations/  shared contracts and config mechanism
configs/                       canonical examples and partial overrides
scripts/                       thin executable entry points
tests/                         focused subsystem tests
docs/                          subsystem documentation and handoffs
```

Scientific data preparation, targets, features, models, evaluation, and
experiment orchestration will be implemented by later owned subsystems.
