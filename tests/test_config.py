from copy import deepcopy

import pytest
import yaml

from er_occupancy.foundations import (
    ConfigStructureError,
    UnknownConfigKeyError,
    load_yaml_mapping,
    merge_strict,
    resolve_config,
    save_resolved_config,
)


def test_merge_strict_recurses_and_replaces_lists_without_mutating_inputs():
    defaults = {
        "model": {"alpha": 1.0, "options": {"fit_intercept": True}},
        "features": ["local"],
    }
    override = {
        "model": {"options": {"fit_intercept": False}},
        "features": ["local", "network"],
    }
    defaults_before = deepcopy(defaults)
    override_before = deepcopy(override)

    resolved = merge_strict(defaults, override)

    assert resolved == {
        "model": {"alpha": 1.0, "options": {"fit_intercept": False}},
        "features": ["local", "network"],
    }
    assert defaults == defaults_before
    assert override == override_before


def test_merge_strict_rejects_nested_unknown_key_with_full_path():
    with pytest.raises(UnknownConfigKeyError, match=r"model\.alpah"):
        merge_strict({"model": {"alpha": 1.0}}, {"model": {"alpah": 2.0}})


@pytest.mark.parametrize(
    ("defaults", "override"),
    [
        ({"model": {"alpha": 1.0}}, {"model": 2.0}),
        ({"model": 2.0}, {"model": {"alpha": 1.0}}),
    ],
)
def test_merge_strict_rejects_mapping_shape_changes(defaults, override):
    with pytest.raises(ConfigStructureError, match="structure mismatch"):
        merge_strict(defaults, override)


def test_load_yaml_mapping_rejects_non_mapping_root(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(ConfigStructureError, match="root must be a mapping"):
        load_yaml_mapping(path)


def test_resolve_and_save_config_round_trip(tmp_path):
    defaults_path = tmp_path / "defaults.yaml"
    override_path = tmp_path / "override.yaml"
    output_path = tmp_path / "run" / "resolved_config.yaml"
    defaults_path.write_text(
        "model:\n  alpha: 1.0\n  features: [local]\n", encoding="utf-8"
    )
    override_path.write_text("model:\n  alpha: 2.0\n", encoding="utf-8")

    resolved = resolve_config(defaults_path, override_path)
    saved_path = save_resolved_config(resolved, output_path)

    assert saved_path == output_path
    assert yaml.safe_load(output_path.read_text(encoding="utf-8")) == resolved
