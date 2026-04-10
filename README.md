# FilOz Time Tracking Utils

Convert **Timing App** Excel exports into the **Tracking** tab of the biglep time tracking Google Sheet. Only Day, Start, End, and Notes are inserted; Duration, Week Number, Duration (decimal), Year, Month Number, and Toku Invoice are calculated by the sheet.

**Current scope:** This project is primarily for **billing import** from Timing XLSX exports into Google Sheets.
It may also include **optional** read-focused helpers around the **[Timing Web API](https://web.timingapp.com/llms.txt)** for data access, but categorization remains in the **Timing App native UI** (rules, suggestions, and manual workflow).

## Setup

1. **Clone or create the project** and install with [uv](https://docs.astral.sh/uv/):

   ```bash
   cd FilOzTimeTrackingUtils
   uv sync
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

   If you don’t have uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`).

2. **Google Service Account**

   - In [Google Cloud Console](https://console.cloud.google.com/), create a project (or use an existing one), enable the **Google Sheets API**, and create a **Service Account**.
   - Download the JSON key and save it somewhere safe (e.g. `~/.config/filoz-time-tracking/sa.json`).
   - Share the [biglep time tracking](https://docs.google.com/spreadsheets/d/1DXOSegKaVjzzmQr1SbLO3tWP_QQVg0M8kUo5Msvw8TU/edit) sheet with the service account email (e.g. `xxx@yyy.iam.gserviceaccount.com`) and give it **Editor** access.

3. **Environment**

   Copy `.env.example` to `.env` and set:

   - `FILOZ_SHEET_ID` – already set to the biglep time tracking sheet ID.
   - `FILOZ_TRACKING_SHEET_NAME` – default `Tracking`; change if your tab name differs.
   - `GOOGLE_APPLICATION_CREDENTIALS` – path to the service account JSON file.

## Usage

From the project directory with `.venv` activated, or use `uv run` so uv uses the project env automatically:

### 1) Export Timing report to XLSX (new)

This command automates the Timing Reports export and writes an `.xlsx` file that can be fed into the importer. It uses **TimingHelper** on your Mac (`save report` only). It does **not** use the Timing Web API and does **not** create, change, or delete time entries or projects—only reads data into a file (then the script may rewrite that file to filter rows for your project tree).

**Explicit date range:**

```bash
uv run python -m filoz_time_tracking.export_timing_report \
  --start 2026-03-10 --end 2026-04-09 \
  --project FilOz \
  --output ~/Desktop/filoz-2026-03-10_2026-04-09.xlsx
```

**Invoice shorthand:**

```bash
uv run python -m filoz_time_tracking.export_timing_report --invoice 2026-3
```

`--invoice 2026-3` resolves to `2026-02-10` through `2026-03-09` (inclusive). January rolls to December of the previous year.

**Conflict safety:**

- Use either `--invoice` **or** `--start/--end`.
- Combining them is rejected with a clear error.

**No-data behavior:**

- If no rows match the project/range, the command still writes a valid workbook with headers only and reports that no entries matched.

**Timeouts (`AppleEvent timed out` / -1712):**

Large exports can exceed the default Apple Event deadline. This CLI wraps Timing in an AppleScript `with timeout` (default **900** seconds) and passes **`--project`** plus **`with subprojects included`** to Timing so the report matches “FilOz & subprojects” without exporting your whole library. If you still hit -1712, narrow the date range or raise the limit, for example:

```bash
uv run python -m filoz_time_tracking.export_timing_report --invoice 2026-3 --timeout 1800
```

Keep **Timing** running and responsive (no blocking dialogs) while the export runs. See [Timing AppleScript reference](https://timingapp.com/help/applescript) (`save report` / `with subprojects included`).

### 2) Import XLSX into Google Sheet

**Verify service account access (no rows added):**

```bash
uv run python -m filoz_time_tracking.import_timing_export --test-credentials
```

This opens the sheet and reads the Tracking tab header. Use it to confirm credentials work before running a real import.

**Test mode (no changes to the sheet):**

```bash
uv run python -m filoz_time_tracking.import_timing_export path/to/your-timing-export.xlsx --dry-run
```

This prints how many rows would be appended and shows the first 10 rows (Day, Start, End, Notes).

**Run for real:**

```bash
uv run python -m filoz_time_tracking.import_timing_export path/to/your-timing-export.xlsx
```

**Add only the first N rows** (e.g. to test with one row):

```bash
uv run python -m filoz_time_tracking.import_timing_export path/to/export.xlsx --limit 1
```

## Monthly workflow

1. Export with CLI for explicit range or invoice shorthand, e.g. `uv run python -m filoz_time_tracking.export_timing_report --invoice 2026-3`.
2. Run importer with `--dry-run` to confirm rows look correct.
3. Run importer without `--dry-run` to append to the Tracking tab.
4. Use the sheet as usual for invoicing (Monthly Pivot, Invoice Pivot, etc.).

## Column mapping

- **Timing** columns used: Start Date, End Date, Project, Title.
- **Tracking** row written: `[Day, Start, End, "", Notes]` where **Notes** = `"{Project}: {Title}"`.
- Day = date from Start Date (YYYY-MM-DD); Start/End = time (HH:MM). Column D is left blank so the sheet’s Duration formula applies.
