"""Deterministic smoke execution for the real data-access code path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from er_occupancy.foundations import UnknownConfigKeyError, merge_strict, resolve_config

from .loader import ParserOptions, load_configured_subset, normalize_processed_table
from .schema import DataAccessValidationError, STANDARDIZED_COLUMNS


def run_data_access_smoke(
    default_config_path: str | Path = "configs/data_access_default.yaml",
    override_config_path: str | Path = "configs/data_access_smoke_override.yaml",
    malformed_fixture_path: str | Path = (
        "tests/fixtures/processed_ed_smoke_malformed.csv"
    ),
) -> dict[str, Any]:
    """Exercise parsing, strict config, subsetting, provenance, and rejection."""

    config = resolve_config(default_config_path, override_config_path)
    loaded = load_configured_subset(config)

    malformed_rejected = False
    malformed = pd.read_csv(
        malformed_fixture_path,
        dtype="string",
        keep_default_na=False,
        na_filter=False,
    )
    try:
        normalize_processed_table(
            malformed,
            parser=ParserOptions.from_mapping(config["parser"]),
        )
    except DataAccessValidationError:
        malformed_rejected = True

    unknown_key_rejected = False
    try:
        merge_strict(config, {"parser": {"invented_option": True}})
    except UnknownConfigKeyError:
        unknown_key_rejected = True

    table = loaded.table
    assert len(table) == 2
    assert table["installation_id"].tolist() == ["00123", "00123"]
    assert table["occupancy_rate_pct"].isna().sum() == 1
    assert tuple(table.columns) == STANDARDIZED_COLUMNS
    assert malformed_rejected
    assert unknown_key_rejected

    return {
        "status": "ok",
        "rows": len(table),
        "installation_ids": table["installation_id"].unique().tolist(),
        "time_bounds": [
            table["local_time"].min().isoformat(timespec="minutes"),
            table["local_time"].max().isoformat(timespec="minutes"),
        ],
        "timezone": table["timezone"].iloc[0],
        "standardized_columns": list(table.columns),
        "missing_occupancy_rate_values": int(
            table["occupancy_rate_pct"].isna().sum()
        ),
        "source_sha256": loaded.manifests[0].sha256,
        "malformed_fixture_rejected": malformed_rejected,
        "unknown_key_rejected": unknown_key_rejected,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--default-config", default="configs/data_access_default.yaml"
    )
    parser.add_argument(
        "--override-config", default="configs/data_access_smoke_override.yaml"
    )
    parser.add_argument(
        "--malformed-fixture",
        default="tests/fixtures/processed_ed_smoke_malformed.csv",
    )
    args = parser.parse_args(argv)
    result = run_data_access_smoke(
        args.default_config,
        args.override_config,
        args.malformed_fixture,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
