from er_occupancy.data_access.smoke import run_data_access_smoke


def test_data_access_smoke() -> None:
    result = run_data_access_smoke()

    assert result["status"] == "ok"
    assert result["rows"] == 2
    assert result["installation_ids"] == ["00123"]
    assert result["missing_occupancy_rate_values"] == 1
    assert result["malformed_fixture_rejected"] is True
    assert result["unknown_key_rejected"] is True
