"""CLI: Create a new monthly invoice tab by duplicating the previous month's tab
and filling in the invoice number (B10) and weekly breakdown rows.

The invoices spreadsheet must be shared with the service account (Editor access).
Set FILOZ_INVOICE_SHEET_ID in .env.

Usage:
    uv run python -m filoz_time_tracking.create_invoice_tab --invoice 2026-5
    uv run python -m filoz_time_tracking.create_invoice_tab --invoice 2026-5 --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date

from . import config
from .google_sheet import get_client


# ── Constants ────────────────────────────────────────────────────────────────

_INVOICE_RE = re.compile(r"^(\d{4})-(\d{1,2})$")
SHEETS_EPOCH = date(1899, 12, 30)

INVOICE_NUMBER_CELL = "B10"   # holds first-of-month date serial, formatted as YYYY-M
WEEK_DATA_START_ROW = 22      # week rows always begin here
INVOICE_TOTALS_LABEL = "Invoice Totals"

# D and E columns multiply hours (C) by the USD/FIL rates locked in row 20.
WEEK_D_FORMULA = "=$C{row}*D$20"
WEEK_E_FORMULA = "=$C{row}*E$20"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_serial(d: date) -> int:
    """Convert a Python date to a Google Sheets date serial."""
    return (d - SHEETS_EPOCH).days


def _parse_invoice(invoice: str) -> tuple[int, int]:
    m = _INVOICE_RE.match(invoice.strip())
    if not m:
        raise ValueError(f"--invoice must be YYYY-M or YYYY-MM (got: {invoice!r})")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise ValueError("Invoice month must be between 1 and 12.")
    return year, month


def _prev_invoice_label(year: int, month: int) -> str:
    """Return the tab name for the previous invoice period."""
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1}"


def _toku_key(year: int, month: int) -> str:
    """Return the Toku Invoice key used in the tracking sheet, e.g. '2026-05'."""
    return f"{year}-{month:02d}"


def _find_totals_row(col_a_values: list[str]) -> int:
    """Return the 1-based row index of the 'Invoice Totals' label in column A."""
    for i, val in enumerate(col_a_values, start=1):
        if str(val).strip() == INVOICE_TOTALS_LABEL:
            return i
    raise ValueError(
        f"Could not find '{INVOICE_TOTALS_LABEL}' row in the invoice tab. "
        "Check that the template tab has not been modified."
    )


# ── Core logic ───────────────────────────────────────────────────────────────

def _get_week_rows(tracking_ws, toku: str) -> list[dict]:
    """
    Read the tracking sheet, filter to the given Toku Invoice key, group entries
    by (year, WEEKNUM), and return a sorted list of week summaries:
        [{"serial": int, "days": int, "hours": float}, ...]
    "serial" is the Sheets date serial of the first worked day of each week.
    Uses the WEEKNUM and YEAR columns already computed in the tracking sheet —
    no formulas are hardcoded here.
    """
    all_rows = tracking_ws.get("A1:J100000", value_render_option="UNFORMATTED_VALUE")

    week_groups: dict[tuple, dict] = defaultdict(
        lambda: {"days": set(), "hours": 0.0, "min_serial": float("inf")}
    )

    for row in all_rows[1:]:  # skip header
        while len(row) < 10:
            row.append("")
        try:
            toku_val = str(row[9]).strip()
            if toku_val != toku:
                continue
            day_serial = int(row[0])
            hours = float(row[6]) if row[6] != "" else 0.0
            year_val = int(row[7]) if row[7] != "" else 0
            weeknum = int(row[5]) if row[5] != "" else 0
            if not year_val or not weeknum:
                continue
            key = (year_val, weeknum)
            week_groups[key]["days"].add(day_serial)
            week_groups[key]["hours"] += hours
            if day_serial < week_groups[key]["min_serial"]:
                week_groups[key]["min_serial"] = day_serial
        except Exception:
            pass

    result = []
    for key in sorted(week_groups.keys()):
        g = week_groups[key]
        result.append({
            "serial": int(g["min_serial"]),
            "days": len(g["days"]),
            "hours": round(g["hours"], 2),
        })
    return result


def _serial_to_date(serial: int) -> date:
    from datetime import timedelta
    return SHEETS_EPOCH + timedelta(days=serial)


def create_invoice_tab(invoice: str, *, dry_run: bool = False) -> None:
    """
    Duplicate the previous invoice tab, rename it, and fill in the new period's
    invoice number and weekly breakdown.

    In dry_run mode: prints every action that would be taken without touching
    any spreadsheet.
    """
    year, month = _parse_invoice(invoice)
    new_tab_name = f"{year}-{month}"
    prev_tab_name = _prev_invoice_label(year, month)
    toku = _toku_key(year, month)

    # B10 = first day of the invoice month, formatted as "YYYY-M" by the sheet.
    b10_serial = _to_serial(date(year, month, 1))
    b10_date = date(year, month, 1)

    print(f"\n{'='*60}")
    print(f"  CREATE INVOICE TAB: {new_tab_name}")
    print(f"  Template (source):  {prev_tab_name}")
    print(f"  Tracking period:    {toku}")
    print(f"  B10 (invoice date): {b10_date}  [serial {b10_serial}]")
    if dry_run:
        print(f"  *** DRY RUN — no changes will be made ***")
    print(f"{'='*60}\n")

    # ── Connect ──────────────────────────────────────────────────────────────
    client = get_client()
    invoice_ss = client.open_by_key(config.get_invoice_sheet_id())
    tracking_ss = client.open_by_key(config.get_sheet_id())
    tracking_ws = tracking_ss.worksheet(config.get_tracking_sheet_name())

    # ── Check tab doesn't already exist ──────────────────────────────────────
    existing_tabs = [ws.title for ws in invoice_ss.worksheets()]
    print(f"Existing tabs: {existing_tabs}")

    if new_tab_name in existing_tabs:
        raise ValueError(
            f"Tab '{new_tab_name}' already exists in the invoices spreadsheet. "
            "Delete or rename it before running this command."
        )
    if prev_tab_name not in existing_tabs:
        raise ValueError(
            f"Template tab '{prev_tab_name}' not found in the invoices spreadsheet."
        )

    # ── Pull week data from tracking sheet ───────────────────────────────────
    print(f"Reading tracking sheet for period '{toku}'...")
    week_rows = _get_week_rows(tracking_ws, toku)

    if not week_rows:
        print(f"  ⚠  No tracking entries found for '{toku}'. "
              "Make sure data has been imported before creating the invoice tab.")
        if not dry_run:
            raise ValueError(f"No tracking data found for period '{toku}'.")

    print(f"  Found {len(week_rows)} week(s):")
    total_days = sum(w["days"] for w in week_rows)
    total_hours = sum(w["hours"] for w in week_rows)
    for i, w in enumerate(week_rows, 1):
        wdate = _serial_to_date(w["serial"])
        print(f"    Week {i}: {wdate}  {w['days']} days  {w['hours']:.2f} hrs")
    print(f"  Totals: {total_days} days  {total_hours:.2f} hrs")

    # ── Determine row structure changes ──────────────────────────────────────
    # Peek at the template to find current week count and totals row position.
    template_ws = invoice_ss.worksheet(prev_tab_name)
    col_a = template_ws.col_values(1)
    old_totals_row = _find_totals_row(col_a)
    old_week_count = old_totals_row - WEEK_DATA_START_ROW
    new_week_count = len(week_rows)
    new_totals_row = WEEK_DATA_START_ROW + new_week_count

    print(f"\nRow structure:")
    print(f"  Template weeks:     {old_week_count}  (rows {WEEK_DATA_START_ROW}–{old_totals_row - 1}, totals at {old_totals_row})")
    print(f"  New invoice weeks:  {new_week_count}  (rows {WEEK_DATA_START_ROW}–{new_totals_row - 1}, totals at {new_totals_row})")

    row_diff = new_week_count - old_week_count
    if row_diff > 0:
        print(f"  → Will INSERT {row_diff} row(s) before the totals row")
    elif row_diff < 0:
        print(f"  → Will DELETE {abs(row_diff)} row(s) from the end of the week section")
    else:
        print(f"  → Week count unchanged, no row insert/delete needed")

    # ── Actions summary (always printed; skipped in dry-run) ─────────────────
    print(f"\nActions:")
    print(f"  1. Duplicate tab '{prev_tab_name}' → rename to '{new_tab_name}'")
    print(f"  2. Set {INVOICE_NUMBER_CELL} = {b10_serial}  ({b10_date}, displays as '{new_tab_name}')")
    if row_diff != 0:
        action = f"insert {row_diff}" if row_diff > 0 else f"delete {abs(row_diff)}"
        print(f"  3. {action} row(s) to adjust week section")
    print(f"  {'4' if row_diff != 0 else '3'}. Write {new_week_count} week row(s) to A{WEEK_DATA_START_ROW}:E{new_totals_row - 1}")
    print(f"  {'5' if row_diff != 0 else '4'}. Write Invoice Totals row at row {new_totals_row} "
          f"(SUM B{WEEK_DATA_START_ROW}:B{new_totals_row - 1})")

    if dry_run:
        print(f"\nDRY RUN complete — no changes made.\n")
        return

    # ── 1. Duplicate tab ─────────────────────────────────────────────────────
    print(f"\nExecuting...")
    source_sheet_id = template_ws.id
    insert_index = len(invoice_ss.worksheets())
    invoice_ss.batch_update({
        "requests": [{
            "duplicateSheet": {
                "sourceSheetId": source_sheet_id,
                "insertSheetIndex": insert_index,
                "newSheetName": new_tab_name,
            }
        }]
    })
    new_ws = invoice_ss.worksheet(new_tab_name)
    print(f"  ✓ Duplicated '{prev_tab_name}' → '{new_tab_name}'")

    # ── 2. Set B10 ───────────────────────────────────────────────────────────
    new_ws.update([[b10_serial]], INVOICE_NUMBER_CELL, value_input_option="RAW")
    print(f"  ✓ Set {INVOICE_NUMBER_CELL} = {b10_serial} ({b10_date})")

    # ── 3. Adjust row count ───────────────────────────────────────────────────
    if row_diff != 0:
        if row_diff > 0:
            # Insert rows before the old totals row
            invoice_ss.batch_update({"requests": [{
                "insertDimension": {
                    "range": {
                        "sheetId": new_ws.id,
                        "dimension": "ROWS",
                        "startIndex": old_totals_row - 1,  # 0-based, insert before totals
                        "endIndex": old_totals_row - 1 + row_diff,
                    },
                    "inheritFromBefore": True,
                }
            }]})
            print(f"  ✓ Inserted {row_diff} row(s) before row {old_totals_row}")
        else:
            # Delete excess week rows just before the old totals row
            del_start = old_totals_row - 1 + row_diff   # 0-based
            del_end = old_totals_row - 1                 # 0-based, exclusive
            invoice_ss.batch_update({"requests": [{
                "deleteDimension": {
                    "range": {
                        "sheetId": new_ws.id,
                        "dimension": "ROWS",
                        "startIndex": del_start,
                        "endIndex": del_end,
                    }
                }
            }]})
            print(f"  ✓ Deleted {abs(row_diff)} row(s) from week section")

    # ── 4. Write week rows ───────────────────────────────────────────────────
    week_data = []
    for i, w in enumerate(week_rows):
        row_num = WEEK_DATA_START_ROW + i
        week_data.append([
            w["serial"],
            w["days"],
            w["hours"],
            WEEK_D_FORMULA.format(row=row_num),
            WEEK_E_FORMULA.format(row=row_num),
        ])

    last_week_row = WEEK_DATA_START_ROW + new_week_count - 1
    week_range = f"A{WEEK_DATA_START_ROW}:E{last_week_row}"
    new_ws.update(week_data, week_range, value_input_option="USER_ENTERED")
    print(f"  ✓ Wrote {new_week_count} week row(s) to {week_range}")

    # ── 5. Write Invoice Totals row ──────────────────────────────────────────
    sum_range = f"B{WEEK_DATA_START_ROW}:B{last_week_row}"
    totals_data = [[
        INVOICE_TOTALS_LABEL,
        f"=SUM(B{WEEK_DATA_START_ROW}:B{last_week_row})",
        f"=SUM(C{WEEK_DATA_START_ROW}:C{last_week_row})",
        f"=SUM(D{WEEK_DATA_START_ROW}:D{last_week_row})",
        f"=SUM(E{WEEK_DATA_START_ROW}:E{last_week_row})",
    ]]
    new_ws.update(
        totals_data,
        f"A{new_totals_row}:E{new_totals_row}",
        value_input_option="USER_ENTERED",
    )
    print(f"  ✓ Wrote Invoice Totals row at row {new_totals_row} (SUM over {sum_range})")

    print(f"\n{'='*60}")
    print(f"  Done! Invoice tab '{new_tab_name}' is ready.")
    print(f"  {total_days} days  |  {total_hours:.2f} hrs")
    print(f"{'='*60}\n")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a new monthly invoice tab from the previous month's template."
    )
    parser.add_argument(
        "--invoice",
        required=True,
        metavar="YYYY-N",
        help="Invoice period to create, e.g. 2026-5",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print all actions that would be taken without modifying any spreadsheet.",
    )
    args = parser.parse_args()

    try:
        create_invoice_tab(args.invoice, dry_run=args.dry_run)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
