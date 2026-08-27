"""File-level provenance for processed ED source access."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


_SOURCE_ERAS = {"legacy_merged_csv", "reconstructed_current", "unspecified"}
_RATE_ORIGINS = {"reported", "reconstructed_upstream", "unspecified"}
_IDENTITY_ORIGINS = {
    "native_legacy",
    "mapped_upstream_to_legacy",
    "unspecified",
}


class SourceDescriptorError(ValueError):
    """Raised when file-level provenance is missing or invalid."""


@dataclass(frozen=True, slots=True)
class SourceFileSpec:
    """Input path and already-established source-era metadata."""

    path: Path
    logical_name: str | None = None
    fiscal_period: str | None = None
    source_era: str = "unspecified"
    occupancy_rate_origin: str = "unspecified"
    identity_origin: str = "unspecified"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SourceFileSpec":
        if not isinstance(value, Mapping):
            raise SourceDescriptorError("Each source descriptor must be a mapping")
        allowed = {
            "path",
            "logical_name",
            "fiscal_period",
            "source_era",
            "occupancy_rate_origin",
            "identity_origin",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise SourceDescriptorError(
                "Unknown source descriptor keys: " + ", ".join(unknown)
            )
        if not isinstance(value.get("path"), str) or not value["path"].strip():
            raise SourceDescriptorError("Each source descriptor requires a path")
        spec = cls(
            path=Path(value["path"]),
            logical_name=value.get("logical_name"),
            fiscal_period=value.get("fiscal_period"),
            source_era=value.get("source_era", "unspecified"),
            occupancy_rate_origin=value.get(
                "occupancy_rate_origin", "unspecified"
            ),
            identity_origin=value.get("identity_origin", "unspecified"),
        )
        spec.validate()
        return spec

    def validate(self) -> None:
        for field_name in ("logical_name", "fiscal_period"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise SourceDescriptorError(
                    f"{field_name} must be null or a nonempty string"
                )
        choices = {
            "source_era": (self.source_era, _SOURCE_ERAS),
            "occupancy_rate_origin": (self.occupancy_rate_origin, _RATE_ORIGINS),
            "identity_origin": (self.identity_origin, _IDENTITY_ORIGINS),
        }
        for field_name, (value, allowed) in choices.items():
            if value not in allowed:
                raise SourceDescriptorError(
                    f"{field_name} must be one of: {', '.join(sorted(allowed))}"
                )


@dataclass(frozen=True, slots=True)
class SourceFileManifest:
    """Concise access diagnostics and recoverable source provenance."""

    source_path: str
    logical_name: str | None
    fiscal_period: str | None
    source_era: str
    occupancy_rate_origin: str
    identity_origin: str
    sha256: str
    file_size_bytes: int
    input_rows: int
    selected_rows: int
    installation_count: int
    observed_start: str | None
    observed_end: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
