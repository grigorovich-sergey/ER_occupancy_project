"""Serialization-friendly identities exchanged between project subsystems."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import re
from typing import TypeAlias
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .provenance import Eligibility, ValueProvenance


JsonScalar: TypeAlias = str | int | float | bool | None
_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ContractValidationError(ValueError):
    """Raised when shared contract data violate structural invariants."""


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")


def _require_code(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _CODE_PATTERN.fullmatch(value):
        raise ContractValidationError(
            f"{field_name} must be a lowercase identifier using letters, "
            "digits, and underscores"
        )


@dataclass(frozen=True, slots=True)
class InstallationIdentity:
    """Stable installation ID plus optional non-identifying display name."""

    installation_id: str
    installation_name: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.installation_id, "installation_id")
        if self.installation_name is not None:
            _require_nonempty(self.installation_name, "installation_name")

    def to_record(self) -> dict[str, str | None]:
        return {
            "installation_id": self.installation_id,
            "installation_name": self.installation_name,
        }


@dataclass(frozen=True, slots=True)
class LocalClockHour:
    """Naive local clock hour accompanied by explicit IANA timezone metadata.

    The datetime deliberately has no UTC offset. This preserves the project's
    normalized Quebec clock-time convention, including the synthetic spring
    02:00 and the single retained autumn 01:00. The timezone is metadata and
    must not be used to reject the deliberately synthetic spring hour.
    """

    local_time: datetime
    timezone: str

    def __post_init__(self) -> None:
        if not isinstance(self.local_time, datetime):
            raise ContractValidationError("local_time must be a datetime")
        if self.local_time.tzinfo is not None:
            raise ContractValidationError("local_time must be timezone-naive")
        if any(
            (
                self.local_time.minute,
                self.local_time.second,
                self.local_time.microsecond,
            )
        ):
            raise ContractValidationError("local_time must be aligned to an exact hour")
        _require_nonempty(self.timezone, "timezone")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ContractValidationError(
                f"timezone must be a recognized IANA name: {self.timezone}"
            ) from exc

    def shift_hours(self, hours: int) -> "LocalClockHour":
        if not isinstance(hours, int):
            raise ContractValidationError("hours must be an integer")
        return LocalClockHour(self.local_time + timedelta(hours=hours), self.timezone)

    def to_value(self) -> str:
        return self.local_time.isoformat(timespec="minutes")


@dataclass(frozen=True, slots=True)
class HistoryWindow:
    """N hourly observations ending at and including the forecast origin."""

    hours: int

    def __post_init__(self) -> None:
        if not isinstance(self.hours, int) or isinstance(self.hours, bool) or self.hours < 1:
            raise ContractValidationError("history-window hours must be a positive integer")

    def start_for(self, forecast_origin: LocalClockHour) -> LocalClockHour:
        return forecast_origin.shift_hours(-(self.hours - 1))


@dataclass(frozen=True, slots=True)
class ForecastHorizon:
    """Positive number of normalized local clock hours after forecast origin."""

    hours: int

    def __post_init__(self) -> None:
        if not isinstance(self.hours, int) or isinstance(self.hours, bool) or self.hours < 1:
            raise ContractValidationError("forecast-horizon hours must be a positive integer")

    def target_for(self, forecast_origin: LocalClockHour) -> LocalClockHour:
        return forecast_origin.shift_hours(self.hours)


@dataclass(frozen=True, slots=True)
class HourlyEDStateIdentity:
    """Canonical identity of one installation's standardized hourly state."""

    installation_id: str
    hour: LocalClockHour

    def __post_init__(self) -> None:
        _require_nonempty(self.installation_id, "installation_id")

    def to_record(self) -> dict[str, str]:
        return {
            "installation_id": self.installation_id,
            "hour": self.hour.to_value(),
            "timezone": self.hour.timezone,
        }


@dataclass(frozen=True, slots=True)
class SampleIdentity:
    """Model-independent identity shared by features, targets, and predictions."""

    installation_id: str
    forecast_origin: LocalClockHour
    history_window: HistoryWindow
    forecast_horizon: ForecastHorizon
    target_time: LocalClockHour
    target_type: str

    def __post_init__(self) -> None:
        _require_nonempty(self.installation_id, "installation_id")
        _require_code(self.target_type, "target_type")
        expected_target = self.forecast_horizon.target_for(self.forecast_origin)
        if self.target_time != expected_target:
            raise ContractValidationError(
                "target_time must equal forecast_origin plus forecast_horizon "
                "on the normalized local clock-hour grid"
            )

    @classmethod
    def from_origin(
        cls,
        *,
        installation_id: str,
        forecast_origin: LocalClockHour,
        history_window: HistoryWindow,
        forecast_horizon: ForecastHorizon,
        target_type: str,
    ) -> "SampleIdentity":
        return cls(
            installation_id=installation_id,
            forecast_origin=forecast_origin,
            history_window=history_window,
            forecast_horizon=forecast_horizon,
            target_time=forecast_horizon.target_for(forecast_origin),
            target_type=target_type,
        )

    def to_record(self) -> dict[str, str | int]:
        return {
            "installation_id": self.installation_id,
            "forecast_origin": self.forecast_origin.to_value(),
            "timezone": self.forecast_origin.timezone,
            "history_window_hours": self.history_window.hours,
            "forecast_horizon_hours": self.forecast_horizon.hours,
            "target_time": self.target_time.to_value(),
            "target_type": self.target_type,
        }


@dataclass(frozen=True, slots=True)
class TargetRecord:
    """Observed scalar target linked to a model-independent sample identity."""

    sample: SampleIdentity
    value: int | float | bool
    provenance: ValueProvenance = ValueProvenance.OBSERVED

    def __post_init__(self) -> None:
        if self.provenance is not ValueProvenance.OBSERVED:
            raise ContractValidationError("Targets must be directly observed, never reconstructed")
        if not isinstance(self.value, (int, float, bool)):
            raise ContractValidationError("target value must be numeric or boolean")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ContractValidationError("target value must be finite")

    def to_record(self) -> dict[str, JsonScalar]:
        return {
            **self.sample.to_record(),
            "target_value": self.value,
            "target_provenance": self.provenance.value,
        }


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    """Scalar model output linked to the same sample identity as its target."""

    sample: SampleIdentity
    value: float
    model_run_id: str
    output_type: str = "point_estimate"

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise ContractValidationError("prediction value must be numeric")
        if not math.isfinite(float(self.value)):
            raise ContractValidationError("prediction value must be finite")
        _require_nonempty(self.model_run_id, "model_run_id")
        _require_code(self.output_type, "output_type")

    def to_record(self) -> dict[str, JsonScalar]:
        return {
            **self.sample.to_record(),
            "prediction_value": float(self.value),
            "prediction_output_type": self.output_type,
            "model_run_id": self.model_run_id,
        }
