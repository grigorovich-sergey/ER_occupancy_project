# Instance 2 Data Access Handoff

## Implemented

`er_occupancy.data_access` now loads approved processed ED CSV files, maps the
established French schema to one nullable pandas table, validates structural
contracts, preserves measurement missingness/string installation identity,
loads deterministic time/installation/file subsets, and emits file-level
checksums and access summaries. It adds no upstream reconstruction or downstream
temporal/modeling logic.

## Owned files

- `src/er_occupancy/data_access/__init__.py`
- `src/er_occupancy/data_access/schema.py`
- `src/er_occupancy/data_access/loader.py`
- `src/er_occupancy/data_access/provenance.py`
- `src/er_occupancy/data_access/smoke.py`
- `configs/data_access_default.yaml`
- `configs/data_access_smoke_override.yaml`
- `scripts/access_ed_data.py`
- `scripts/smoke_data_access.py`
- `tests/fixtures/processed_ed_smoke.csv`
- `tests/fixtures/processed_ed_smoke_malformed.csv`
- `tests/test_data_access.py`
- `tests/test_data_access_smoke.py`
- `docs/instance_02_data_access.md`
- `docs/handoffs/instance_02_data_access.md`
- narrow dependency/architecture edits to `pyproject.toml` and `README.md`

## Public API

Stable imports from `er_occupancy.data_access`:

- `normalize_processed_table(source, *, parser) -> pandas.DataFrame`
- `load_processed_ed_file(source, *, parser, subset=None) -> LoadedEDData`
- `load_processed_ed_files(sources, *, parser, subset=None) -> LoadedEDData`
- `load_configured_subset(config) -> LoadedEDData`
- `run_configured_access(config) -> LoadedEDData`
- `validate_source_columns(columns) -> None`
- `validate_standardized_table(table) -> None`
- `ParserOptions`, `SubsetFilter`, `SourceFileSpec`, `SourceFileManifest`,
  `LoadedEDData`
- schema constants including `SOURCE_TO_INTERNAL`, `STANDARDIZED_COLUMNS`, and
  `KEY_COLUMNS`

## Standardized table contract

Exact ordered columns and dtypes:

| Column | Dtype |
|---|---|
| `installation_id` | pandas `string` |
| `installation_name` | pandas `string` |
| `functional_stretchers` | nullable `Int64` |
| `patients_present` | nullable `Int64` |
| `patients_on_stretchers` | nullable `Int64` |
| `patients_on_stretchers_gt_24h` | nullable `Int64` |
| `patients_on_stretchers_gt_48h` | nullable `Int64` |
| `dms_stretcher_previous_day` | nullable `Float64` |
| `dms_ambulatory_previous_day` | nullable `Float64` |
| `patients_waiting_for_care` | nullable `Int64` |
| `occupancy_rate_pct` | nullable `Float64` |
| `local_time` | naive `datetime64[ns]` |
| `timezone` | pandas `string` |

Key and deterministic ordering: `(installation_id, local_time)`. Missing
measurements are `pd.NA`, never zero/imputed. Installation IDs remain strings;
names remain row-level display metadata and are not used to merge identities.

## Source mapping

`noInstallation` → `installation_id`; `nomInstallation` →
`installation_name`; `Nbre civières fonctionnelles` →
`functional_stretchers`; `Nbre patients présents` → `patients_present`;
`Nbre patients présents sur civière` → `patients_on_stretchers`; the `plus de
24h/48h` fields → `patients_on_stretchers_gt_24h/_gt_48h`; the two `DMS ... la
veille` fields → `dms_stretcher_previous_day` and
`dms_ambulatory_previous_day`; waiting-for-care →
`patients_waiting_for_care`; `tauxocc` → `occupancy_rate_pct`; and configured
`date` + `heure` → `local_time`.

## Time semantics

The parser uses explicit `date_format` and `hour_format`, requires exact hourly
alignment, creates a timezone-naive timestamp, and repeats one explicit valid
IANA timezone as metadata compatible with `LocalClockHour`. It performs no DST
synthesis, gap interpolation, or forecast-window arithmetic; temporal
preparation owns those steps.

## Provenance

Each source descriptor carries path/logical name, fiscal period, source era,
reported-vs-upstream-reconstructed rate origin, and native-vs-upstream-mapped
identity origin. `SourceFileManifest` adds SHA-256, bytes, input/selected rows,
source installation count, and observed time bounds. `LoadedEDData.manifests`
retains these; `manifest_dict()` is JSON-ready. This is intentionally separate
from temporal `ValueProvenance`.

## Config

Canonical default: `configs/data_access_default.yaml`. It intentionally leaves
source-dependent parser/timezone settings null. Use `resolve_config(default,
override)`; nested override keys are strict and file descriptor keys receive
subsystem validation. Synthetic example:

```yaml
parser:
  encoding: utf-8
  delimiter: ","
  date_format: "%Y-%m-%d"
  hour_format: "%H:%M"
  decimal_mark: "."
  timezone: America/Toronto
subset:
  installation_ids: ["00123"]
```

Export runs must configure and save `output.resolved_config` alongside any
standardized CSV/manifest artifact.

## Smoke

Smallest command:

```bash
python scripts/smoke_data_access.py
```

Reusable call: `er_occupancy.data_access.smoke.run_data_access_smoke()`.
Expected: JSON `status: ok`, two ordered rows for string ID `00123`, one missing
occupancy rate, explicit `America/Toronto`, SHA-256 provenance, malformed input
rejected, and unknown config key rejected.

## Tests

```bash
pytest
```

At handoff: 38 tests passed. Coverage includes exact mapping/dtypes, leading-zero
IDs, local-hour parsing/alignment, numeric missingness and malformed text,
required fields, integral counts, duplicate keys within/across files, inclusive subsets,
deterministic ordering, empty subsets, strict override behavior, source
descriptor validation, manifests/export persistence, both smoke paths, and all
foundation tests.

## Development-harness guidance

Use the committed synthetic fixture through
`configs/data_access_smoke_override.yaml`, or resolve a partial override listing
one verified pre-2026 processed file, a few `installation_ids`, and inclusive
`start_local_time`/`end_local_time`. Call `load_configured_subset(config)` and
consume `.table`; the harness need not understand French headers. `chunk_size`
may be set to limit input memory.

## Downstream guidance

Temporal preparation should consume the standardized columns above and use
`installation_id + local_time` as its observed-state key. Target/features must
not reparse source files, fuzzy-match names, remap IDs, or recompute `tauxocc`.
They should add their own provenance/eligibility only after this observed table.

## Open issues

- No real processed file was available in the workspace. Actual delimiter,
  encoding, date/hour formats, decimal mark, missing markers, and real-data IANA
  timezone must be verified and provided through configuration before real use.
- DMS units were not established by supplied source documentation; values and
  source meaning are preserved without an invented unit suffix.
- No foundation change was required.

## Git

- Branch: `instance-02-data-access`
- Commit: pending final verification
- Draft PR: pending; the selected GitHub integration returned HTTP 403 when
  asked to create the branch remotely
- Status: local implementation complete; publication access unresolved
