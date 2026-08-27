"""Canonical columns and structural validation for observed hourly ED states."""

from __future__ import annotations

from datetime import datetime
from typing import Final

import pandas as pd

from er_occupancy.foundations import (
    ContractValidationError,
    LocalClockHour,
)


class DataAccessValidationError(ValueError):
    """Raised when source or standardized data violate the access contract."""


SOURCE_TO_INTERNAL: Final[dict[str, str]] = {
    "noInstallation": "installation_id",
    "nomInstallation": "installation_name",
    "Nbre civières fonctionnelles": "functional_stretchers",
    "Nbre patients présents": "patients_present",
    "Nbre patients présents sur civière": "patients_on_stretchers",
    "Nbre patients présents sur civière plus de 24h": (
        "patients_on_stretchers_gt_24h"
    ),
    "Nbre patients présents sur civière plus de 48h": (
        "patients_on_stretchers_gt_48h"
    ),
    "DMS sur civière la veille": "dms_stretcher_previous_day",
    "DMS ambulatoire la veille": "dms_ambulatory_previous_day",
    "Nbre patients présents en attente de prise en charge": (
        "patients_waiting_for_care"
    ),
    "tauxocc": "occupancy_rate_pct",
}

SOURCE_DATE_COLUMN: Final = "date"
SOURCE_HOUR_COLUMN: Final = "heure"
REQUIRED_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    *SOURCE_TO_INTERNAL,
    SOURCE_DATE_COLUMN,
    SOURCE_HOUR_COLUMN,
)

COUNT_COLUMNS: Final[tuple[str, ...]] = (
    "functional_stretchers",
    "patients_present",
    "patients_on_stretchers",
    "patients_on_stretchers_gt_24h",
    "patients_on_stretchers_gt_48h",
    "patients_waiting_for_care",
)
CONTINUOUS_COLUMNS: Final[tuple[str, ...]] = (
    "dms_stretcher_previous_day",
    "dms_ambulatory_previous_day",
    "occupancy_rate_pct",
)
MEASUREMENT_COLUMNS: Final[tuple[str, ...]] = tuple(
    internal_name
    for internal_name in SOURCE_TO_INTERNAL.values()
    if internal_name not in {"installation_id", "installation_name"}
)
STANDARDIZED_COLUMNS: Final[tuple[str, ...]] = (
    "installation_id",
    "installation_name",
    *MEASUREMENT_COLUMNS,
    "local_time",
    "timezone",
)
KEY_COLUMNS: Final[tuple[str, str]] = ("installation_id", "local_time")


def validate_source_columns(columns: pd.Index | list[str]) -> None:
    """Require every established processed-source column, allowing extras."""

    available = set(columns)
    missing = [name for name in REQUIRED_SOURCE_COLUMNS if name not in available]
    if missing:
        raise DataAccessValidationError(
            "Processed ED data are missing required columns: " + ", ".join(missing)
        )


def validate_standardized_table(table: pd.DataFrame) -> None:
    """Validate the stable dataframe contract without adding scientific rules."""

    missing = [name for name in STANDARDIZED_COLUMNS if name not in table.columns]
    if missing:
        raise DataAccessValidationError(
            "Standardized ED table is missing columns: " + ", ".join(missing)
        )

    if tuple(table.columns) != STANDARDIZED_COLUMNS:
        raise DataAccessValidationError(
            "Standardized ED table columns or ordering do not match the contract"
        )

    if table["installation_id"].isna().any() or table[
        "installation_id"
    ].str.strip().eq("").any():
        raise DataAccessValidationError("installation_id must be nonempty for every row")

    if not isinstance(table["local_time"].dtype, pd.DatetimeTZDtype) and not pd.api.types.is_datetime64_dtype(
        table["local_time"]
    ):
        raise DataAccessValidationError("local_time must have a pandas datetime dtype")
    if isinstance(table["local_time"].dtype, pd.DatetimeTZDtype):
        raise DataAccessValidationError("local_time must be timezone-naive")
    if table["local_time"].isna().any():
        raise DataAccessValidationError("local_time must be present for every row")
    if not table["local_time"].dt.floor("h").equals(table["local_time"]):
        raise DataAccessValidationError("local_time values must align to exact hours")

    timezone_values = table["timezone"].dropna().unique().tolist()
    if table.empty:
        empty_timezone = table.attrs.get("timezone")
        timezone_values = [empty_timezone] if empty_timezone is not None else []
    elif len(timezone_values) != 1 or table["timezone"].isna().any():
        raise DataAccessValidationError(
            "timezone must contain one explicit IANA name for the loaded table"
        )
    if len(timezone_values) != 1:
        raise DataAccessValidationError(
            "timezone metadata is required even for an empty standardized subset"
        )
    try:
        LocalClockHour(datetime(2000, 1, 1), str(timezone_values[0]))
    except ContractValidationError as exc:
        raise DataAccessValidationError(str(exc)) from exc

    duplicate_mask = table.duplicated(list(KEY_COLUMNS), keep=False)
    if duplicate_mask.any():
        examples = (
            table.loc[duplicate_mask, list(KEY_COLUMNS)]
            .head(5)
            .astype(str)
            .to_dict("records")
        )
        raise DataAccessValidationError(
            "Duplicate (installation_id, local_time) keys; examples: "
            f"{examples}"
        )

    for column in COUNT_COLUMNS:
        if not isinstance(table[column].dtype, pd.Int64Dtype):
            raise DataAccessValidationError(f"{column} must use nullable Int64 dtype")
    for column in CONTINUOUS_COLUMNS:
        if not isinstance(table[column].dtype, pd.Float64Dtype):
            raise DataAccessValidationError(f"{column} must use nullable Float64 dtype")
