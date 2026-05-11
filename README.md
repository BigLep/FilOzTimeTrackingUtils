# FilOz Time Tracking Utils

Automates the monthly invoicing workflow for FilOz:

1. Exports time entries from the Timing app into an XLSX file.
2. Imports the XLSX into the **Tracking** tab of the biglep time tracking Google Sheet (with formula autofill).
3. Runs an anomaly review — gaps, travel day billing, unusual durations.
4. Creates a new tab in the invoices workbook by duplicating the previous month and filling in the invoice number and weekly breakdown.
5. Downloads the invoice tab as a single-sheet XLSX file ready for upload to Toku.

**Current scope:** Billing import and invoice tab creation. Categorisation of time entries remains in the Timing App native UI.

## Setup

1. **Clone or create the project** and install with [uv](https://docs.astral.sh/uv/):

   ```bash
   cd FilOzTimeTrackingUtils
   uv sync
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

   If you don't have uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`).

2. **Google Service Account**

   - In [Google Cloud Console](https://console.cloud.google.com/), create a project (or use an existing one), enable the **Google Sheets API** and the **Google Drive API**, and create a **Service Account**.
   - Download the JSON key and save it somewhere safe (e.g. `~/.config/filoz-time-tracking/sa.json`).
   - Share the [biglep time tracking](https://docs.google.com/spreadsheets/d/1DXOSegKaVjzzmQr1SbLO3tWP_QQVg0M8kUo5Msvw8TU/edit) sheet with the service account email (e.g. `xxx@yyy.iam.gserviceaccount.com`) and give it **Editor** access.

3. **Environment**

   Copy `.env.example` to `.env` and set:

   - `FILOZ_SHEET_ID` – the biglep time tracking sheet ID.
   - `FILOZ_TRACKING_SHEET_NAME` – default `Tracking`; change if your tab name differs.
   - `FILOZ_INVOICE_SHEET_ID` – the invoices workbook sheet ID. Also share this sheet with the service account (Editor access).
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

Large exports can exceed the default Apple Event deadline. This CLI wraps Timing in an AppleScript `with timeout` (default **900** seconds) and passes **`--project`** plus **`with subprojects included`** to Timing so the report matches "FilOz & subprojects" without exporting your whole library. If you still hit -1712, narrow the date range or raise the limit, for example:

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

**Autofill behaviour:**

After appending rows, the importer automatically fills formula columns D, F, G, H, I, J by copying from the row directly above the first new row. The sheet remains the source of truth for the actual formulas — the script just pulls them down. To skip this step:

```bash
uv run python -m filoz_time_tracking.import_timing_export path/to/export.xlsx --no-autofill
```

### 3) Analyze time tracking (anomaly review)

Run after importing to catch issues before submitting the invoice:

```bash
uv run python -m filoz_time_tracking.analyze_tracking --invoice 2026-5
```

Checks performed: hours vs. rolling average, missing weekdays (with calendar-check prompt), travel day billing (contract requires 8 hrs/day), long entries (possible forgotten timer stop), sub-5-minute noise, overlapping entries, and a project breakdown.

Use `--context-periods N` to change the number of prior periods used for comparison (default: 13).

### 4) Create monthly invoice tab

Duplicates the previous month's tab in the invoices workbook, updates the invoice number (B10), and fills in the weekly breakdown rows from the tracking sheet. The invoices spreadsheet must be shared with the service account (Editor access); set `FILOZ_INVOICE_SHEET_ID` in `.env`.

**Dry-run (lists every action without touching the spreadsheet):**

```bash
uv run python -m filoz_time_tracking.create_invoice_tab --invoice 2026-5 --dry-run
```

**Run for real:**

```bash
uv run python -m filoz_time_tracking.create_invoice_tab --invoice 2026-5
```

What the script does:
- Duplicates the previous month's tab (e.g. `2026-4`) and renames it (e.g. `2026-5`)
- Sets B10 to the first day of the invoice month (formatted as `YYYY-M` by the sheet; all other dates derive from it via formula)
- Reads the Tracking sheet for the period, groups entries by week (using the `WEEKNUM` and `YEAR` columns already in the sheet)
- Inserts or deletes rows if the new invoice has a different number of weeks than the template
- Writes each week's start date, days worked, and hours; D and E columns use the existing rate formulas
- Updates the Invoice Totals row SUM range to match

### 5) Download invoice tab as XLSX

Exports a single invoice tab from the invoices workbook as a standalone XLSX file, ready for upload to Toku.

The script copies the tab into a temporary Google Spreadsheet, exports that as XLSX via the Drive API (so you get a clean single-sheet file with all formatting intact), then deletes the temporary spreadsheet.

**Dry-run (prints steps without touching anything):**

```bash
uv run python -m filoz_time_tracking.download_invoice_sheet --invoice 2026-5 --dry-run
```

**Download to current directory (`biglep invoice - 2026-5.xlsx`):**

```bash
uv run python -m filoz_time_tracking.download_invoice_sheet --invoice 2026-5
```

**Download to a specific path:**

```bash
uv run python -m filoz_time_tracking.download_invoice_sheet --invoice 2026-5 --output ~/Desktop/"biglep invoice - 2026-5.xlsx"
```

## Monthly workflow

1. Export from Timing:
   ```bash
   uv run python -m filoz_time_tracking.export_timing_report --invoice 2026-5
   ```
2. Dry-run the import to confirm rows look correct:
   ```bash
   uv run python -m filoz_time_tracking.import_timing_export FilOz-2026-04-10_2026-05-09.xlsx --dry-run
   ```
3. Import for real (formula columns D, F, G, H, I, J autofilled):
   ```bash
   uv run python -m filoz_time_tracking.import_timing_export FilOz-2026-04-10_2026-05-09.xlsx
   ```
4. Run the anomaly review (gaps, travel day billing, unusual entries):
   ```bash
   uv run python -m filoz_time_tracking.analyze_tracking --invoice 2026-5
   ```
5. Dry-run the invoice tab creation to confirm weeks and totals look right:
   ```bash
   uv run python -m filoz_time_tracking.create_invoice_tab --invoice 2026-5 --dry-run
   ```
6. Create the invoice tab for real:
   ```bash
   uv run python -m filoz_time_tracking.create_invoice_tab --invoice 2026-5
   ```
7. Download the invoice tab as XLSX:
   ```bash
   uv run python -m filoz_time_tracking.download_invoice_sheet --invoice 2026-5
   ```
   Saves as `biglep invoice - 2026-5.xlsx` in the current directory.
8. Upload the XLSX to Toku manually: [https://app.toku.com/myinfo/invoices](https://app.toku.com/myinfo/invoices)

## Column mapping

- **Timing** columns used: Start Date, End Date, Project, Title.
- **Tracking** row written: `[Day, Start, End, "", Notes]` where **Notes** = `"{Project}: {Title}"`.
- Day = date from Start Date (YYYY-MM-DD); Start/End = time (HH:MM).
- Columns D, F, G, H, I, J (Duration, Week Number, Duration (decimal), Year, Month Number, Toku Invoice) are filled by copying formulas from the row above. The sheet is the source of truth for those formulas.

## Future ideas (workflow backlog)

Possible enhancements—not implemented yet; capture here so they are not lost:

  1. **Automate Toku upload** — Use computer-use automation to open [https://app.toku.com/myinfo/invoices](https://app.toku.com/myinfo/invoices) and upload the XLSX file, replacing the current manual step. (Toku does not appear to have a public API for invoice submission.)
