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

1. In Timing App, export the month’s time entries as **Excel (XLSX)** (e.g. for the “FilOz” project).
2. Run the script with `--dry-run` to confirm the rows look correct.
3. Run without `--dry-run` to append to the Tracking tab.
4. Use the sheet as usual for invoicing (Monthly Pivot, Invoice Pivot, etc.).

## Column mapping

- **Timing** columns used: Start Date, End Date, Project, Title.
- **Tracking** row written: `[Day, Start, End, "", Notes]` where **Notes** = `"{Project}: {Title}"`.
- Day = date from Start Date (YYYY-MM-DD); Start/End = time (HH:MM). Column D is left blank so the sheet’s Duration formula applies.
