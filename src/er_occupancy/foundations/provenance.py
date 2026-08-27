"""Shared provenance and eligibility vocabulary without scientific logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ValueProvenance(str, Enum):
    """Established source status for a feature or observed target value."""

    OBSERVED = "observed"
    RECONSTRUCTED_SHORT_GAP = "reconstructed_short_gap"
    SYNTHETIC_SPRING_DST = "synthetic_spring_dst"


class EligibilityStatus(str, Enum):
    """Whether a downstream subsystem accepts a modeling observation."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True, slots=True)
class Eligibility:
    """Eligibility decision made by a scientific subsystem.

    Reason codes are intentionally open vocabulary. The subsystem that owns an
    eligibility rule also owns and documents its reason codes.
    """

    status: EligibilityStatus
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, EligibilityStatus):
            raise ValueError("status must be an EligibilityStatus value")
        if self.reason_code is not None and not _CODE_PATTERN.fullmatch(
            self.reason_code
        ):
            raise ValueError(
                "reason_code must be a lowercase identifier using letters, "
                "digits, and underscores"
            )
        if self.status is EligibilityStatus.ELIGIBLE and self.reason_code is not None:
            raise ValueError("An eligible observation cannot have an ineligibility reason")

    @property
    def is_eligible(self) -> bool:
        return self.status is EligibilityStatus.ELIGIBLE

    @classmethod
    def eligible(cls) -> "Eligibility":
        return cls(EligibilityStatus.ELIGIBLE)

    @classmethod
    def ineligible(cls, reason_code: str | None = None) -> "Eligibility":
        return cls(EligibilityStatus.INELIGIBLE, reason_code)

    def to_record(self) -> dict[str, str | None]:
        return {
            "eligibility": self.status.value,
            "ineligibility_reason": self.reason_code,
        }
