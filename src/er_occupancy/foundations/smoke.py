"""Deterministic synthetic smoke check for the shared foundation layer."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .config import UnknownConfigKeyError, merge_strict, resolve_config
from .contracts import (
    ForecastHorizon,
    HistoryWindow,
    LocalClockHour,
    PredictionRecord,
    SampleIdentity,
    TargetRecord,
)
from .provenance import Eligibility, ValueProvenance


def run_foundations_smoke(
    default_config: str | Path,
    override_config: str | Path | None = None,
) -> dict[str, Any]:
    """Exercise config resolution, strictness, contracts, and serialization."""

    config = resolve_config(default_config, override_config)
    smoke_config = config["foundations_smoke"]

    origin = LocalClockHour(
        datetime.fromisoformat(smoke_config["forecast_origin"]),
        smoke_config["timezone"],
    )
    sample = SampleIdentity.from_origin(
        installation_id=smoke_config["installation_id"],
        forecast_origin=origin,
        history_window=HistoryWindow(smoke_config["history_window_hours"]),
        forecast_horizon=ForecastHorizon(smoke_config["forecast_horizon_hours"]),
        target_type=smoke_config["target_type"],
    )
    target = TargetRecord(sample, 42)
    prediction = PredictionRecord(sample, 41.5, model_run_id="synthetic_smoke_run")

    unknown_key_rejected = False
    try:
        merge_strict(config, {"foundations_smoke": {"misspelled_option": True}})
    except UnknownConfigKeyError:
        unknown_key_rejected = True

    return {
        "status": "ok",
        "resolved_forecast_horizon_hours": sample.forecast_horizon.hours,
        "sample": sample.to_record(),
        "target": target.to_record(),
        "prediction": prediction.to_record(),
        "provenance_values": [item.value for item in ValueProvenance],
        "eligibility": Eligibility.eligible().to_record(),
        "unknown_key_rejected": unknown_key_rejected,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("default_config", type=Path)
    parser.add_argument("--override", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    print(
        json.dumps(
            run_foundations_smoke(args.default_config, args.override),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
