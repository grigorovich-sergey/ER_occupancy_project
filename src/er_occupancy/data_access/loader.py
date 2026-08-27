"""Load approved processed ED files into the canonical observed-state table."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from er_occupancy.foundations import save_resolved_config

from .provenance import SourceFileManifest, SourceFileSpec
from .schema import (
    CONTINUOUS_COLUMNS,
    COUNT_COLUMNS,
    KEY_COLUMNS,
    SOURCE_DATE_COLUMN,
    SOURCE_HOUR_COLUMN,
    SOURCE_TO_INTERNAL,
    STANDARDIZED_COLUMNS,
    DataAccessValidationError,
    validate_source_columns,
    validate_standardized_table,
)


@dataclass(frozen=True, slots=True)
class ParserOptions:
    """Explicit parsing choices that the processed source files must establish."""

    encoding: str
    delimiter: str
    date_format: str
    hour_format: str
    decimal_mark: str
    missing_values: tuple[str, ...]
    timezone: str
    chunk_size: int | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ParserOptions":
        required = {
            "encoding",
            "delimiter",
            "date_format",
            "hour_format",
            "decimal_mark",
            "missing_values",
            "timezone",
            "chunk_size",
        }
        _require_exact_keys(value, required, "parser")
        nonempty_fields = (
            "encoding",
            "delimiter",
            "date_format",
            "hour_format",
            "decimal_mark",
            "timezone",
        )
        for field_name in nonempty_fields:
            field_value = value[field_name]
            if not isinstance(field_value, str) or not field_value:
                raise DataAccessValidationError(
                    f"parser.{field_name} must be an explicit nonempty string"
                )
        if len(value["delimiter"]) != 1:
            raise DataAccessValidationError("parser.delimiter must be one character")
        if value["decimal_mark"] not in {".", ","}:
            raise DataAccessValidationError("parser.decimal_mark must be '.' or ','")
        missing_values = value["missing_values"]
        if not isinstance(missing_values, list) or not all(
            isinstance(item, str) for item in missing_values
        ):
            raise DataAccessValidationError(
                "parser.missing_values must be a list of exact source strings"
            )
        chunk_size = value["chunk_size"]
        if chunk_size is not None and (
            not isinstance(chunk_size, int)
            or isinstance(chunk_size, bool)
            or chunk_size < 1
        ):
            raise DataAccessValidationError(
                "parser.chunk_size must be null or a positive integer"
            )
        return cls(
            encoding=value["encoding"],
            delimiter=value["delimiter"],
            date_format=value["date_format"],
            hour_format=value["hour_format"],
            decimal_mark=value["decimal_mark"],
            missing_values=tuple(missing_values),
            timezone=value["timezone"],
            chunk_size=chunk_size,
        )


@dataclass(frozen=True, slots=True)
class SubsetFilter:
    """Deterministic installation and inclusive local-clock subset."""

    installation_ids: tuple[str, ...] = ()
    start_local_time: pd.Timestamp | None = None
    end_local_time: pd.Timestamp | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SubsetFilter":
        _require_exact_keys(
            value,
            {"installation_ids", "start_local_time", "end_local_time"},
            "subset",
        )
        ids = value["installation_ids"]
        if not isinstance(ids, list) or not all(
            isinstance(item, str) and item.strip() for item in ids
        ):
            raise DataAccessValidationError(
                "subset.installation_ids must be a list of nonempty strings"
            )
        if len(ids) != len(set(ids)):
            raise DataAccessValidationError(
                "subset.installation_ids must not contain duplicates"
            )
        start = _parse_filter_time(value["start_local_time"], "start_local_time")
        end = _parse_filter_time(value["end_local_time"], "end_local_time")
        if start is not None and end is not None and start > end:
            raise DataAccessValidationError(
                "subset.start_local_time must not be after end_local_time"
            )
        return cls(tuple(ids), start, end)

    def apply(self, table: pd.DataFrame) -> pd.DataFrame:
        mask = pd.Series(True, index=table.index)
        if self.installation_ids:
            mask &= table["installation_id"].isin(self.installation_ids)
        if self.start_local_time is not None:
            mask &= table["local_time"] >= self.start_local_time
        if self.end_local_time is not None:
            mask &= table["local_time"] <= self.end_local_time
        return table.loc[mask].copy()


@dataclass(slots=True)
class LoadedEDData:
    """Standardized rows plus file-level provenance kept outside the dataframe."""

    table: pd.DataFrame
    manifests: list[SourceFileManifest]

    def manifest_dict(self) -> dict[str, Any]:
        return {
            "schema": "er_occupancy.data_access.v1",
            "key": list(KEY_COLUMNS),
            "ordering": list(KEY_COLUMNS),
            "standardized_rows": len(self.table),
            "installation_count": int(self.table["installation_id"].nunique()),
            "files": [item.to_dict() for item in self.manifests],
        }


def normalize_processed_table(
    source: pd.DataFrame,
    *,
    parser: ParserOptions,
) -> pd.DataFrame:
    """Normalize one in-memory processed-source table without imputation."""

    validate_source_columns(source.columns)
    if not source.index.is_unique:
        source = source.reset_index(drop=True)

    result = pd.DataFrame(index=source.index)
    installation_ids = source["noInstallation"].astype("string").str.strip()
    installation_ids = _replace_missing(installation_ids, parser.missing_values)
    if installation_ids.isna().any() or installation_ids.eq("").any():
        rows = installation_ids.index[installation_ids.isna() | installation_ids.eq("")]
        raise DataAccessValidationError(
            f"noInstallation is missing at source rows: {rows[:5].tolist()}"
        )
    result["installation_id"] = installation_ids.astype("string")

    names = source["nomInstallation"].astype("string")
    result["installation_name"] = _replace_missing(
        names, parser.missing_values
    ).astype("string")

    for source_name, internal_name in SOURCE_TO_INTERNAL.items():
        if internal_name in {"installation_id", "installation_name"}:
            continue
        integer = internal_name in COUNT_COLUMNS
        result[internal_name] = _parse_numeric(
            source[source_name],
            source_name=source_name,
            missing_values=parser.missing_values,
            decimal_mark=parser.decimal_mark,
            integer=integer,
        )

    combined = (
        source[SOURCE_DATE_COLUMN].astype("string")
        + " "
        + source[SOURCE_HOUR_COLUMN].astype("string")
    )
    try:
        local_time = pd.to_datetime(
            combined,
            format=f"{parser.date_format} {parser.hour_format}",
            errors="raise",
            exact=True,
        )
    except (TypeError, ValueError) as exc:
        raise DataAccessValidationError(
            "Could not parse date + heure exactly with configured formats "
            f"{parser.date_format!r} and {parser.hour_format!r}: {exc}"
        ) from exc
    result["local_time"] = local_time
    result["timezone"] = pd.Series(parser.timezone, index=result.index, dtype="string")

    result = result.loc[:, STANDARDIZED_COLUMNS]
    result = _coerce_contract_dtypes(result)
    result.attrs["timezone"] = parser.timezone
    _validate_hour_alignment(result)
    validate_standardized_table(result)
    if len(result) != len(source):
        raise RuntimeError("Normalization changed the number of source rows")
    return result


def load_processed_ed_file(
    source: SourceFileSpec,
    *,
    parser: ParserOptions,
    subset: SubsetFilter | None = None,
) -> LoadedEDData:
    """Load, normalize, validate, and optionally subset one processed CSV file."""

    source.validate()
    path = source.path
    if not path.is_file():
        raise DataAccessValidationError(f"Processed ED source does not exist: {path}")

    read_options = {
        "encoding": parser.encoding,
        "sep": parser.delimiter,
        "dtype": "string",
        "keep_default_na": False,
        "na_filter": False,
    }
    if parser.chunk_size is None:
        chunks: Iterable[pd.DataFrame] = [pd.read_csv(path, **read_options)]
    else:
        chunks = pd.read_csv(path, chunksize=parser.chunk_size, **read_options)

    selected_chunks: list[pd.DataFrame] = []
    input_rows = 0
    all_ids: set[str] = set()
    observed_start: pd.Timestamp | None = None
    observed_end: pd.Timestamp | None = None
    for raw_chunk in chunks:
        normalized = normalize_processed_table(raw_chunk, parser=parser)
        input_rows += len(normalized)
        all_ids.update(normalized["installation_id"].dropna().tolist())
        if not normalized.empty:
            chunk_start = normalized["local_time"].min()
            chunk_end = normalized["local_time"].max()
            observed_start = (
                chunk_start if observed_start is None else min(observed_start, chunk_start)
            )
            observed_end = (
                chunk_end if observed_end is None else max(observed_end, chunk_end)
            )
        selected_chunks.append(
            subset.apply(normalized) if subset is not None else normalized
        )

    table = _combine_tables(selected_chunks, parser.timezone)
    table = _sort_table(table)
    validate_standardized_table(table)
    manifest = SourceFileManifest(
        source_path=str(path),
        logical_name=source.logical_name or path.name,
        fiscal_period=source.fiscal_period,
        source_era=source.source_era,
        occupancy_rate_origin=source.occupancy_rate_origin,
        identity_origin=source.identity_origin,
        sha256=_sha256(path),
        file_size_bytes=path.stat().st_size,
        input_rows=input_rows,
        selected_rows=len(table),
        installation_count=len(all_ids),
        observed_start=_timestamp_text(observed_start),
        observed_end=_timestamp_text(observed_end),
    )
    return LoadedEDData(table, [manifest])


def load_processed_ed_files(
    sources: Sequence[SourceFileSpec],
    *,
    parser: ParserOptions,
    subset: SubsetFilter | None = None,
) -> LoadedEDData:
    """Load multiple files and enforce key uniqueness across their union."""

    if not sources:
        raise DataAccessValidationError("At least one processed ED source is required")
    loaded = [
        load_processed_ed_file(source, parser=parser, subset=subset)
        for source in sources
    ]
    table = _sort_table(
        _combine_tables([item.table for item in loaded], parser.timezone)
    )
    validate_standardized_table(table)
    manifests = [manifest for item in loaded for manifest in item.manifests]
    return LoadedEDData(table, manifests)


def load_configured_subset(config: Mapping[str, Any]) -> LoadedEDData:
    """Validate a resolved Instance 2 config and return its standardized subset."""

    _require_exact_keys(config, {"files", "parser", "subset", "output"}, "root")
    files = config["files"]
    if not isinstance(files, list):
        raise DataAccessValidationError("files must be a list of source descriptors")
    sources = [SourceFileSpec.from_mapping(item) for item in files]
    parser = ParserOptions.from_mapping(config["parser"])
    subset = SubsetFilter.from_mapping(config["subset"])
    return load_processed_ed_files(sources, parser=parser, subset=subset)


def run_configured_access(config: Mapping[str, Any]) -> LoadedEDData:
    """Load configured rows and persist requested artifacts with resolved config."""

    loaded = load_configured_subset(config)
    output = config["output"]
    _require_exact_keys(
        output,
        {"standardized_csv", "manifest_json", "resolved_config"},
        "output",
    )
    requested = [output["standardized_csv"], output["manifest_json"]]
    if any(value is not None for value in requested) and output["resolved_config"] is None:
        raise DataAccessValidationError(
            "output.resolved_config is required when access artifacts are written"
        )
    for key, value in output.items():
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise DataAccessValidationError(f"output.{key} must be null or a path string")

    if output["standardized_csv"] is not None:
        csv_path = Path(output["standardized_csv"])
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        loaded.table.to_csv(csv_path, index=False, na_rep="")
    if output["manifest_json"] is not None:
        manifest_path = Path(output["manifest_json"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(loaded.manifest_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if output["resolved_config"] is not None:
        save_resolved_config(config, output["resolved_config"])
    return loaded


def _parse_numeric(
    values: pd.Series,
    *,
    source_name: str,
    missing_values: tuple[str, ...],
    decimal_mark: str,
    integer: bool,
) -> pd.Series:
    text = values.astype("string").str.strip()
    text = _replace_missing(text, missing_values)
    normalized = text.str.replace(decimal_mark, ".", regex=False)
    try:
        numeric = pd.to_numeric(normalized, errors="raise")
    except (TypeError, ValueError) as exc:
        invalid = []
        for index, value in text.dropna().items():
            try:
                float(str(value).replace(decimal_mark, "."))
            except ValueError:
                invalid.append((index, value))
            if len(invalid) == 5:
                break
        raise DataAccessValidationError(
            f"Unexpected nonnumeric text in {source_name}: {invalid or str(exc)}"
        ) from exc

    finite_mask = numeric.notna() & ~numeric.map(
        lambda value: math.isfinite(float(value)) if pd.notna(value) else True
    )
    if finite_mask.any():
        raise DataAccessValidationError(f"Non-finite numeric value in {source_name}")
    if integer:
        nonintegral = numeric.notna() & numeric.mod(1).ne(0)
        if nonintegral.any():
            rows = numeric.index[nonintegral][:5].tolist()
            raise DataAccessValidationError(
                f"Non-integral count in {source_name} at source rows: {rows}"
            )
        return numeric.astype("Int64")
    return numeric.astype("Float64")


def _replace_missing(values: pd.Series, missing_values: tuple[str, ...]) -> pd.Series:
    result = values.copy()
    for marker in missing_values:
        result = result.mask(result.eq(marker), pd.NA)
    return result


def _parse_filter_time(value: Any, field_name: str) -> pd.Timestamp | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise DataAccessValidationError(f"subset.{field_name} must be null or a string")
    try:
        parsed = pd.Timestamp(value)
    except ValueError as exc:
        raise DataAccessValidationError(
            f"subset.{field_name} is not a valid timestamp: {value}"
        ) from exc
    if parsed.tzinfo is not None:
        raise DataAccessValidationError(
            f"subset.{field_name} must be timezone-naive local clock time"
        )
    if parsed != parsed.floor("h"):
        raise DataAccessValidationError(
            f"subset.{field_name} must align to an exact hour"
        )
    return parsed


def _require_exact_keys(
    mapping: Mapping[str, Any], expected: set[str], context: str
) -> None:
    if not isinstance(mapping, Mapping):
        raise DataAccessValidationError(f"{context} configuration must be a mapping")
    missing = sorted(expected - set(mapping))
    unknown = sorted(set(mapping) - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise DataAccessValidationError(
            f"Invalid {context} configuration keys ({'; '.join(details)})"
        )


def _coerce_contract_dtypes(table: pd.DataFrame) -> pd.DataFrame:
    result = table.copy()
    result["installation_id"] = result["installation_id"].astype("string")
    result["installation_name"] = result["installation_name"].astype("string")
    for column in COUNT_COLUMNS:
        result[column] = result[column].astype("Int64")
    for column in CONTINUOUS_COLUMNS:
        result[column] = result[column].astype("Float64")
    result["local_time"] = pd.to_datetime(result["local_time"])
    result["timezone"] = result["timezone"].astype("string")
    return result.loc[:, STANDARDIZED_COLUMNS]


def _validate_hour_alignment(table: pd.DataFrame) -> None:
    if not table["local_time"].dt.floor("h").equals(table["local_time"]):
        raise DataAccessValidationError(
            "Parsed date + heure values are not aligned to exact hours"
        )


def _combine_tables(tables: Sequence[pd.DataFrame], timezone: str) -> pd.DataFrame:
    nonempty = [table for table in tables if not table.empty]
    if nonempty:
        return _coerce_contract_dtypes(pd.concat(nonempty, ignore_index=True))
    empty = pd.DataFrame(
        {
            "installation_id": pd.Series(dtype="string"),
            "installation_name": pd.Series(dtype="string"),
            **{column: pd.Series(dtype="Int64") for column in COUNT_COLUMNS},
            **{column: pd.Series(dtype="Float64") for column in CONTINUOUS_COLUMNS},
            "local_time": pd.Series(dtype="datetime64[ns]"),
            "timezone": pd.Series(dtype="string"),
        }
    )
    # Retain explicit timezone metadata even though an empty subset has no rows.
    empty.attrs["timezone"] = timezone
    return empty.loc[:, STANDARDIZED_COLUMNS]


def _sort_table(table: pd.DataFrame) -> pd.DataFrame:
    return table.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _timestamp_text(value: pd.Timestamp | None) -> str | None:
    return None if value is None else value.isoformat(timespec="minutes")
