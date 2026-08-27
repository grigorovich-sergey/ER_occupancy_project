# Instance 2 — ED Data Access / Standardized Source Representation

## Responsibility and boundary

`er_occupancy.data_access` is the canonical Python access layer for approved,
already-processed Quebec hourly ED files. It parses the established French
source schema, preserves measurement missingness and installation identity,
validates inexpensive structural invariants, supports deterministic subsets,
and records file-level provenance.

It does not join historical occupancy/rate sources, recurse through raw JSON,
recompute `tauxocc`, map current identities, interpolate gaps, synthesize DST
rows, decide eligibility, construct targets/features, or implement models.

## Accepted processed source schema

Every input CSV must contain all of these columns; additional columns are
allowed but do not enter the standardized table.

| Processed source field | Standardized field | Pandas dtype |
|---|---|---|
| `noInstallation` | `installation_id` | `string` |
| `nomInstallation` | `installation_name` | `string` |
| `Nbre civières fonctionnelles` | `functional_stretchers` | nullable `Int64` |
| `Nbre patients présents` | `patients_present` | nullable `Int64` |
| `Nbre patients présents sur civière` | `patients_on_stretchers` | nullable `Int64` |
| `Nbre patients présents sur civière plus de 24h` | `patients_on_stretchers_gt_24h` | nullable `Int64` |
| `Nbre patients présents sur civière plus de 48h` | `patients_on_stretchers_gt_48h` | nullable `Int64` |
| `DMS sur civière la veille` | `dms_stretcher_previous_day` | nullable `Float64` |
| `DMS ambulatoire la veille` | `dms_ambulatory_previous_day` | nullable `Float64` |
| `Nbre patients présents en attente de prise en charge` | `patients_waiting_for_care` | nullable `Int64` |
| `tauxocc` | `occupancy_rate_pct` | nullable `Float64` |
| `date` + `heure` | `local_time` | timezone-naive `datetime64[ns]` |
| configured metadata | `timezone` | `string` |

The output column order is exactly the order above. The unique key and stable
sort order are `(installation_id, local_time)`. Downstream code must use this
key rather than row positions. `installation_id` is stripped of surrounding
whitespace and remains a string, so leading zeroes are preserved.
`installation_name` is row-level display metadata: it is preserved without
fuzzy matching, ID merging, case changes, or name-based identity inference.
Known labels may therefore vary while the numeric/string ID remains canonical.

## Numeric and missing-value behavior

The parser reads source cells as strings before conversion. Only explicitly
configured missing markers become `pd.NA`. Numeric whitespace is stripped,
the configured decimal mark is applied, and arbitrary nonnumeric text fails
with an auditable error. Counts must be mathematically integral; values such as
`12.0` are accepted as counts, while `12.5` is rejected. Finite numeric values
are otherwise preserved without scientific thresholding or imputation.

`occupancy_rate_pct` remains a percentage. Missing rates remain missing,
including the established Paul-Gilbert Charny case. The DMS fields retain their
source names and numeric values because their precise unit has not yet been
verified from available source documentation.

## Local-clock parsing

`date` and `heure` are parsed exactly with configured `date_format` and
`hour_format` strings. The result must be aligned to an exact hour and remains
timezone-naive. One explicit, valid IANA timezone string is attached as
metadata and checked using the shared `LocalClockHour` contract.

This layer only represents observed rows. Temporal preparation remains
responsible for spring `02:00` synthesis, autumn semantics, missing-hour
reconstruction, local-clock arithmetic, and forecast eligibility.

No real processed files were present during implementation. Consequently the
canonical default deliberately leaves encoding, delimiter, datetime formats,
decimal mark, and timezone unset. A real-data override must state values
verified from the file/source; the synthetic smoke override is an example, not
a scientific real-data default.

## Public API

Stable imports are exposed from `er_occupancy.data_access`:

```python
from er_occupancy.data_access import (
    ParserOptions,
    SourceFileSpec,
    SubsetFilter,
    load_processed_ed_file,
    load_processed_ed_files,
    load_configured_subset,
    normalize_processed_table,
    run_configured_access,
    validate_standardized_table,
)
```

- `normalize_processed_table(source, *, parser)` normalizes an in-memory
  dataframe.
- `load_processed_ed_file(source, *, parser, subset=None)` returns
  `LoadedEDData` for one CSV.
- `load_processed_ed_files(sources, *, parser, subset=None)` loads a union and
  also rejects duplicate keys across files.
- `load_configured_subset(config)` validates a fully resolved config and loads
  its subset without writing artifacts.
- `run_configured_access(config)` additionally writes configured CSV/manifest
  artifacts and the fully resolved config.
- `validate_standardized_table(table)` checks the downstream table contract.

`LoadedEDData.table` is the dataframe. `LoadedEDData.manifests` contains one
`SourceFileManifest` per file, and `manifest_dict()` creates a JSON-ready access
summary.

## Source-era provenance

Each source descriptor records a path/logical name, optional fiscal period,
source era (`legacy_merged_csv`, `reconstructed_current`, or `unspecified`),
rate origin (`reported`, `reconstructed_upstream`, or `unspecified`), and
identity origin (`native_legacy`, `mapped_upstream_to_legacy`, or
`unspecified`). These describe upstream processing; they are not
`ValueProvenance.RECONSTRUCTED_SHORT_GAP`.

The generated file manifest adds SHA-256, byte size, source row count, selected
row count, source installation count, and observed local-time bounds. Provenance
is file-level rather than repeated on every hourly row.

## Configuration and subset access

Resolve the canonical default with a strict partial override:

```python
from er_occupancy.data_access import load_configured_subset
from er_occupancy.foundations import resolve_config

config = resolve_config(
    "configs/data_access_default.yaml",
    "configs/scenarios/my_pre_2026_subset.yaml",
)
loaded = load_configured_subset(config)
```

Example real-data override shape (parser values are illustrative and must be
checked against the actual file):

```yaml
files:
  - path: data_processed/2024-2025.csv
    logical_name: processed-2024-2025
    fiscal_period: "2024-2025"
    source_era: legacy_merged_csv
    occupancy_rate_origin: reported
    identity_origin: native_legacy
parser:
  encoding: utf-8
  delimiter: ","
  date_format: "%Y-%m-%d"
  hour_format: "%H:%M"
  decimal_mark: "."
  timezone: America/Toronto
  chunk_size: 100000
subset:
  installation_ids: ["51234567"]
  start_local_time: "2024-01-01 00:00"
  end_local_time: "2024-01-03 23:00"
```

Start/end filters are inclusive normalized local hours. An empty installation
list means all installations. Files may be selected explicitly by replacing
the `files` list. Chunking reduces peak input memory while every encountered
row is still structurally parsed; only selected standardized chunks are kept.

For an export run, configure `output.standardized_csv` and/or
`output.manifest_json` plus the required `output.resolved_config`, then run:

```bash
python scripts/access_ed_data.py --override-config path/to/override.yaml
```

## Structural validation

The access boundary enforces required source fields, explicit exact date/hour
parsing, nonempty installation IDs, numeric-or-explicitly-missing measurement
cells, exact hourly alignment, canonical nullable dtypes, one configured IANA
timezone, no silent normalization row loss, and unique keys within/across
files. It does not repeat the historical scientific data audit.

## Smoke and tests

```bash
python scripts/smoke_data_access.py
pytest
```

The smoke uses `tests/fixtures/processed_ed_smoke.csv`, a tiny deterministic
2024 synthetic file. It demonstrates French-header parsing, a preserved
leading-zero ID, exact local hours, missing `tauxocc`, strict config resolution,
chunked subsetting, SHA-256 provenance, and visible rejection of malformed
numeric text. It neither requires real data nor inspects 2026.

## Downstream contract and limitations

Temporal preparation, target, and feature subsystems should consume the
standardized table and must not parse French headers, remap identities, or
recompute `tauxocc`. Source-derived rows here are observed source states; this
layer intentionally adds no reconstruction/target/eligibility columns.

Before the first real-data use, verify the actual separator, encoding, date
format, hour format, decimal mark, missing markers, timezone assumption, and
DMS units from supplied processed files or authoritative documentation.
