"""Small strict YAML configuration mechanism shared by project subsystems."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ConfigMapping = dict[str, Any]


class ConfigError(ValueError):
    """Base class for configuration loading and resolution errors."""


class UnknownConfigKeyError(ConfigError):
    """Raised when an override contains a key absent from the defaults."""


class ConfigStructureError(ConfigError):
    """Raised when YAML or an override has an incompatible mapping shape."""


def load_yaml_mapping(path: str | Path) -> ConfigMapping:
    """Load a YAML file whose root must be a mapping.

    Empty YAML files are interpreted as empty mappings. This is useful for an
    intentionally empty partial override, but a subsystem's canonical default
    configuration will normally be non-empty.
    """

    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as stream:
            loaded = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Could not load YAML config {config_path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ConfigStructureError(
            f"YAML config root must be a mapping: {config_path}"
        )
    return deepcopy(dict(loaded))


def merge_strict(
    defaults: Mapping[str, Any],
    override: Mapping[str, Any],
    *,
    _path: tuple[str, ...] = (),
) -> ConfigMapping:
    """Recursively merge a partial override into defaults.

    Nested mappings merge recursively. Non-mapping values, including lists,
    replace their defaults in full. Unknown keys and mapping/non-mapping shape
    changes fail explicitly. Inputs are never mutated.
    """

    if not isinstance(defaults, Mapping) or not isinstance(override, Mapping):
        raise ConfigStructureError("Both defaults and override must be mappings")

    resolved = deepcopy(dict(defaults))
    for key, override_value in override.items():
        dotted_key = ".".join((*_path, str(key)))
        if key not in defaults:
            raise UnknownConfigKeyError(f"Unknown configuration key: {dotted_key}")

        default_value = defaults[key]
        default_is_mapping = isinstance(default_value, Mapping)
        override_is_mapping = isinstance(override_value, Mapping)

        if default_is_mapping and override_is_mapping:
            resolved[key] = merge_strict(
                default_value,
                override_value,
                _path=(*_path, str(key)),
            )
        elif default_is_mapping != override_is_mapping:
            raise ConfigStructureError(
                f"Configuration structure mismatch at {dotted_key}: "
                "cannot replace a mapping with a non-mapping or vice versa"
            )
        else:
            resolved[key] = deepcopy(override_value)

    return resolved


def resolve_config(
    default_path: str | Path,
    override_path: str | Path | None = None,
) -> ConfigMapping:
    """Load canonical defaults and apply an optional strict partial override."""

    defaults = load_yaml_mapping(default_path)
    if override_path is None:
        return defaults
    return merge_strict(defaults, load_yaml_mapping(override_path))


def save_resolved_config(config: Mapping[str, Any], path: str | Path) -> Path:
    """Persist the fully resolved configuration as portable YAML."""

    if not isinstance(config, Mapping):
        raise ConfigStructureError("Resolved configuration must be a mapping")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(
                deepcopy(dict(config)),
                stream,
                sort_keys=False,
                allow_unicode=True,
            )
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Could not save resolved config {output_path}: {exc}") from exc
    return output_path
