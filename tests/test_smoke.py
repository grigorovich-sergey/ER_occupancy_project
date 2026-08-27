from er_occupancy.foundations.smoke import run_foundations_smoke


def test_foundations_smoke_uses_override_and_rejects_unknown_key():
    result = run_foundations_smoke(
        "configs/foundations_smoke_default.yaml",
        "configs/foundations_smoke_override.yaml",
    )

    assert result["status"] == "ok"
    assert result["resolved_forecast_horizon_hours"] == 2
    assert result["sample"]["target_time"] == "2025-03-09T03:00"
    assert result["unknown_key_rejected"] is True
