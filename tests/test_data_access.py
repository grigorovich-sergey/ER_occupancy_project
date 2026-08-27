from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from er_occupancy.data_access import (
    COUNT_COLUMNS,
    SOURCE_TO_INTERNAL,
    STANDARDIZED_COLUMNS,
    DataAccessValidationError,
    ParserOptions,
    SourceFileSpec,
    SubsetFilter,
    load_processed_ed_file,
    load_processed_ed_files,
    normalize_processed_table,
    run_configured_access,
)
from er_occupancy.foundations import UnknownConfigKeyError, resolve_config


FIXTURE = Path("tests/fixtures/processed_ed_smoke.csv")


@pytest.fixture
def parser() -> ParserOptions:
    return ParserOptions(
        encoding="utf-8",
        delimiter=",",
        date_format="%Y-%m-%d",
        hour_format="%H:%M",
        decimal_mark=".",
        missing_values=("",),
        timezone="America/Toronto",
        chunk_size=2,
    )


def read_fixture() -> pd.DataFrame:
    return pd.read_csv(
        FIXTURE, dtype="string", keep_default_na=False, na_filter=False
    )


def test_exact_source_mapping_and_nullable_dtypes(parser: ParserOptions) -> None:
    table = normalize_processed_table(read_fixture(), parser=parser)

    assert tuple(table.columns) == STANDARDIZED_COLUMNS
    assert set(SOURCE_TO_INTERNAL.values()).issubset(table.columns)
    assert all(str(table[column].dtype) == "Int64" for column in COUNT_COLUMNS)
    assert str(table["occupancy_rate_pct"].dtype) == "Float64"
    assert table.loc[1, "occupancy_rate_pct"] is pd.NA


def test_installation_ids_remain_strings_and_local_hours_are_exact(
    parser: ParserOptions,
) -> None:
    table = normalize_processed_table(read_fixture(), parser=parser)

    assert table.loc[0, "installation_id"] == "00123"
    assert table.loc[0, "local_time"] == pd.Timestamp("2024-01-01 00:00")
    assert table["local_time"].dt.tz is None
    assert table["timezone"].unique().tolist() == ["America/Toronto"]


def test_unexpected_numeric_text_fails_visibly(parser: ParserOptions) -> None:
    source = read_fixture()
    source.loc[0, "Nbre patients présents"] = "unknown"

    with pytest.raises(DataAccessValidationError, match="Unexpected nonnumeric text"):
        normalize_processed_table(source, parser=parser)


def test_missing_required_source_column_fails(parser: ParserOptions) -> None:
    source = read_fixture().drop(columns=["tauxocc"])

    with pytest.raises(DataAccessValidationError, match="missing required columns"):
        normalize_processed_table(source, parser=parser)


def test_nonintegral_count_fails(parser: ParserOptions) -> None:
    source = read_fixture()
    source.loc[0, "Nbre patients présents"] = "14.5"

    with pytest.raises(DataAccessValidationError, match="Non-integral count"):
        normalize_processed_table(source, parser=parser)


def test_exact_datetime_format_and_hour_alignment_fail(parser: ParserOptions) -> None:
    source = read_fixture()
    source.loc[0, "heure"] = "00:30"

    with pytest.raises(DataAccessValidationError):
        normalize_processed_table(source, parser=parser)


def test_duplicate_installation_hour_keys_fail(parser: ParserOptions) -> None:
    source = read_fixture()
    source.loc[1, "heure"] = "00:00"

    with pytest.raises(DataAccessValidationError, match="Duplicate"):
        normalize_processed_table(source, parser=parser)


def test_subset_is_inclusive_and_ordering_is_deterministic(
    parser: ParserOptions,
) -> None:
    subset = SubsetFilter(
        installation_ids=("00123",),
        start_local_time=pd.Timestamp("2024-01-01 00:00"),
        end_local_time=pd.Timestamp("2024-01-01 01:00"),
    )
    loaded = load_processed_ed_file(
        SourceFileSpec(FIXTURE), parser=parser, subset=subset
    )

    assert loaded.table["installation_id"].tolist() == ["00123", "00123"]
    assert loaded.table["local_time"].tolist() == sorted(
        loaded.table["local_time"].tolist()
    )
    manifest = loaded.manifests[0]
    assert manifest.input_rows == 3
    assert manifest.selected_rows == 2
    assert manifest.installation_count == 2
    assert len(manifest.sha256) == 64
    assert manifest.observed_start == "2024-01-01T00:00"
    assert manifest.observed_end == "2024-01-01T01:00"
    assert loaded.manifest_dict()["schema"] == "er_occupancy.data_access.v1"


def test_empty_subset_retains_explicit_timezone_metadata(
    parser: ParserOptions,
) -> None:
    subset = SubsetFilter(installation_ids=("does-not-exist",))
    loaded = load_processed_ed_file(
        SourceFileSpec(FIXTURE), parser=parser, subset=subset
    )

    assert loaded.table.empty
    assert loaded.table.attrs["timezone"] == "America/Toronto"


def test_duplicate_keys_across_files_fail(
    parser: ParserOptions, tmp_path: Path
) -> None:
    copied = tmp_path / "copy.csv"
    copied.write_bytes(FIXTURE.read_bytes())

    with pytest.raises(DataAccessValidationError, match="Duplicate"):
        load_processed_ed_files(
            [SourceFileSpec(FIXTURE), SourceFileSpec(copied)], parser=parser
        )


def test_strict_config_override_and_unknown_key_rejection(tmp_path: Path) -> None:
    resolved = resolve_config(
        "configs/data_access_default.yaml",
        "configs/data_access_smoke_override.yaml",
    )
    assert resolved["parser"]["timezone"] == "America/Toronto"
    assert resolved["output"]["manifest_json"] is None

    override = tmp_path / "unknown.yaml"
    override.write_text("parser:\n  guessed_timezone: true\n", encoding="utf-8")
    with pytest.raises(UnknownConfigKeyError, match="parser.guessed_timezone"):
        resolve_config("configs/data_access_default.yaml", override)


def test_source_descriptor_rejects_unknown_metadata() -> None:
    with pytest.raises(ValueError, match="Unknown source descriptor"):
        SourceFileSpec.from_mapping({"path": "x.csv", "fuzzy_name_match": True})


def test_export_persists_table_manifest_and_resolved_config(tmp_path: Path) -> None:
    config = deepcopy(
        resolve_config(
            "configs/data_access_default.yaml",
            "configs/data_access_smoke_override.yaml",
        )
    )
    config["output"] = {
        "standardized_csv": str(tmp_path / "standardized.csv"),
        "manifest_json": str(tmp_path / "manifest.json"),
        "resolved_config": str(tmp_path / "resolved.yaml"),
    }

    loaded = run_configured_access(config)

    assert len(loaded.table) == 2
    assert (tmp_path / "standardized.csv").is_file()
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))[
        "standardized_rows"
    ] == 2
    assert "America/Toronto" in (tmp_path / "resolved.yaml").read_text(
        encoding="utf-8"
    )
