# Data model: Timing FilOz XLSX export CLI

**Feature**: `002-timing-xlsx-export`

## CLI inputs (logical)

| Field | Description | Validation |
|-------|-------------|------------|
| `start_date` | Inclusive calendar start of export range | ISO date or locale-neutral `YYYY-MM-DD` |
| `end_date` | Inclusive calendar end of export range | Must be ≥ `start_date` |
| `invoice_id` | Shorthand `YYYY-M` or `YYYY-MM` (invoice “end month”) | Mutually exclusive with explicit `start_date`/`end_date`; resolves to prior month 10th → invoice month 9th |
| `output_path` | Filesystem path for `.xlsx` | Writable parent directory; default convention TBD in implementation (e.g. cwd + timestamp) |
| `project_root_name` | Timing project name for subtree filter | Default `FilOz`; configurable for tests |

## Resolved export range

After resolution:

- **From explicit dates**: `[start_date, end_date]` inclusive.
- **From invoice**: `start = (invoice_year, invoice_month-1, 10)` with month rollover; `end = (invoice_year, invoice_month, 9)` inclusive. January invoice month uses December of previous year for start.

## Output artifact

| Artifact | Description |
|----------|-------------|
| Timing XLSX workbook | First worksheet tabular **raw time entries**, compatible with downstream `parse_timing_export` (headers include at least **Start Date**, **End Date**, **Project**, **Title**). |

## Entities (from spec)

- **Time entry**: Represented only inside the XLSX (source of truth is Timing); no local DB.
- **Project subtree**: All entries under configured root project name in Timing’s hierarchy.

## State transitions

None (one-shot CLI: validate → call TimingHelper → write file → exit).
