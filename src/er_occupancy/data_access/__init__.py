"""Canonical access to already-processed Quebec hourly ED files."""

from .loader import (
    LoadedEDData,
    ParserOptions,
    SubsetFilter,
    load_configured_subset,
    load_processed_ed_file,
    load_processed_ed_files,
    normalize_processed_table,
    run_configured_access,
)
from .provenance import (
    SourceDescriptorError,
    SourceFileManifest,
    SourceFileSpec,
)
from .schema import (
    CONTINUOUS_COLUMNS,
    COUNT_COLUMNS,
    KEY_COLUMNS,
    MEASUREMENT_COLUMNS,
    REQUIRED_SOURCE_COLUMNS,
    SOURCE_TO_INTERNAL,
    STANDARDIZED_COLUMNS,
    DataAccessValidationError,
    validate_source_columns,
    validate_standardized_table,
)

__all__ = [
    "CONTINUOUS_COLUMNS",
    "COUNT_COLUMNS",
    "DataAccessValidationError",
    "KEY_COLUMNS",
    "LoadedEDData",
    "MEASUREMENT_COLUMNS",
    "ParserOptions",
    "REQUIRED_SOURCE_COLUMNS",
    "SOURCE_TO_INTERNAL",
    "STANDARDIZED_COLUMNS",
    "SourceDescriptorError",
    "SourceFileManifest",
    "SourceFileSpec",
    "SubsetFilter",
    "load_configured_subset",
    "load_processed_ed_file",
    "load_processed_ed_files",
    "normalize_processed_table",
    "run_configured_access",
    "validate_source_columns",
    "validate_standardized_table",
]
