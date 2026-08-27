from datetime import datetime
import json

import pytest

from er_occupancy.foundations import (
    ContractValidationError,
    Eligibility,
    EligibilityStatus,
    ForecastHorizon,
    HistoryWindow,
    HourlyEDStateIdentity,
    InstallationIdentity,
    LocalClockHour,
    PredictionRecord,
    SampleIdentity,
    TargetRecord,
    ValueProvenance,
)


def clock(value: str = "2025-03-09T01:00") -> LocalClockHour:
    return LocalClockHour(datetime.fromisoformat(value), "America/Toronto")


def sample() -> SampleIdentity:
    return SampleIdentity.from_origin(
        installation_id="51234567",
        forecast_origin=clock(),
        history_window=HistoryWindow(6),
        forecast_horizon=ForecastHorizon(2),
        target_type="absolute_occupancy",
    )


def test_local_clock_hour_requires_naive_exact_hour_and_iana_timezone():
    assert clock().to_value() == "2025-03-09T01:00"

    with pytest.raises(ContractValidationError, match="exact hour"):
        LocalClockHour(datetime(2025, 1, 1, 1, 30), "America/Toronto")
    with pytest.raises(ContractValidationError, match="recognized IANA"):
        LocalClockHour(datetime(2025, 1, 1, 1), "Quebec/Invented")


def test_synthetic_spring_hour_is_representable_on_normalized_clock_grid():
    synthetic_hour = clock().shift_hours(1)

    assert synthetic_hour.to_value() == "2025-03-09T02:00"
    assert ValueProvenance.SYNTHETIC_SPRING_DST.value == "synthetic_spring_dst"


def test_history_window_includes_forecast_origin():
    assert HistoryWindow(6).start_for(clock()).to_value() == "2025-03-08T20:00"


def test_sample_identity_derives_target_and_has_stable_equality():
    first = sample()
    second = sample()

    assert first == second
    assert hash(first) == hash(second)
    assert first.target_time.to_value() == "2025-03-09T03:00"


def test_sample_identity_rejects_inconsistent_target_time():
    with pytest.raises(ContractValidationError, match="target_time"):
        SampleIdentity(
            installation_id="51234567",
            forecast_origin=clock(),
            history_window=HistoryWindow(6),
            forecast_horizon=ForecastHorizon(2),
            target_time=clock().shift_hours(3),
            target_type="absolute_occupancy",
        )


def test_target_must_be_observed():
    with pytest.raises(ContractValidationError, match="directly observed"):
        TargetRecord(
            sample(),
            42,
            provenance=ValueProvenance.RECONSTRUCTED_SHORT_GAP,
        )


def test_contract_records_are_flat_and_json_serializable():
    state = HourlyEDStateIdentity("51234567", clock())
    target = TargetRecord(sample(), 42)
    prediction = PredictionRecord(sample(), 41.5, "regression_run_001")

    for record in (state.to_record(), target.to_record(), prediction.to_record()):
        assert all(not isinstance(value, dict) for value in record.values())
        json.dumps(record)


def test_installation_name_is_metadata_not_part_of_sample_identity():
    installation = InstallationIdentity("51234567", "Hôpital synthétique")

    assert installation.to_record()["installation_name"] == "Hôpital synthétique"
    assert sample().installation_id == installation.installation_id


def test_eligibility_has_closed_status_and_open_validated_reason():
    eligible = Eligibility.eligible()
    ineligible = Eligibility.ineligible("missing_target")

    assert eligible.status is EligibilityStatus.ELIGIBLE
    assert eligible.is_eligible
    assert ineligible.to_record() == {
        "eligibility": "ineligible",
        "ineligibility_reason": "missing_target",
    }
    with pytest.raises(ValueError, match="lowercase identifier"):
        Eligibility.ineligible("Missing target")
    with pytest.raises(ValueError, match="EligibilityStatus"):
        Eligibility("eligible")


@pytest.mark.parametrize("wrapper", [HistoryWindow, ForecastHorizon])
@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_window_and_horizon_require_positive_integer(wrapper, value):
    with pytest.raises(ContractValidationError, match="positive integer"):
        wrapper(value)
