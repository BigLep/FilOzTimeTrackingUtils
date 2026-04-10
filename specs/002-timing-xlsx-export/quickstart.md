# Quickstart: FilOz Timing XLSX export

## Prerequisites

- macOS with **Timing** and **TimingHelper** available.
- **Timing Connect** (or equivalent) so **advanced scripting** is available — scripts error otherwise; see [Timing JavaScript export help](https://timingapp.com/help/javascript-time-entries).
- **uv** + project synced: `uv sync`.

## Run

**Explicit range:**

```bash
cd /path/to/FilOzTimeTrackingUtils
uv run python -m filoz_time_tracking.export_timing_report \
  --start 2026-03-10 --end 2026-04-09 \
  -o ~/Desktop/filoz-2026-03-10_2026-04-09.xlsx
```

**Invoice shorthand** (`2026-3` → 2026-02-10 … 2026-03-09):

```bash
uv run python -m filoz_time_tracking.export_timing_report \
  --invoice 2026-3 \
  -o ~/Desktop/filoz-invoice-2026-3.xlsx
```

## Verify against Timing UI

1. Open Timing **Reports**, select **FilOz** (and confirm subproject count matches expectations).
2. Set the same date range as the CLI.
3. Advanced: **Raw Data (for Export)**, Time entries ✓, App usage ✗, Excel, duration **XX:YY:ZZ**, include short entries ✓, group activities ✗.
4. Compare row counts and spot-check Start/End/Project/Title against the CLI output.
5. If no entries match, expect a headers-only workbook and a no-data message from the CLI.

## If export times out (-1712)

Timing’s automation can hit **AppleEvent timed out** on heavy reports. Try, in order:

1. Ensure **Timing** is open and not waiting on a dialog.
2. Use the default **`--project FilOz`** so only that tree (with subprojects) is exported.
3. Increase the automation window: `--timeout 1800` (seconds).

## Next step in billing flow

Feed the file into the existing importer:

```bash
uv run python -m filoz_time_tracking.import_timing_export path/to/export.xlsx --dry-run
```
