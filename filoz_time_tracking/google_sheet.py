"""Append rows to the Tracking tab via Google Sheets API. Supports dry-run (no writes)."""
from __future__ import annotations

import os

import gspread
from google.oauth2.service_account import Credentials

from .config import get_credentials_path, get_sheet_id, get_tracking_sheet_name

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Column letters whose formulas should be filled down after each import.
# The sheet is the source of truth for the actual formulas — this list just
# tells the script which columns to copy from the row above.
# D=3, F=5, G=6, H=7, I=8, J=9  (0-based indices used internally)
AUTOFILL_COL_LETTERS = ["D", "F", "G", "H", "I", "J"]


def _col_letter_to_index(letter: str) -> int:
    """Convert a column letter (A=0, B=1, …) to a 0-based index."""
    letter = letter.upper()
    result = 0
    for ch in letter:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def get_client():
    """Build gspread client using GOOGLE_APPLICATION_CREDENTIALS."""
    path = get_credentials_path()
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(
            "GOOGLE_APPLICATION_CREDENTIALS must point to a service account JSON file. "
            "Share the Google Sheet with the service account email (Editor)."
        )
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def test_credentials() -> None:
    """
    Open the sheet and read the Tracking tab header (no writes). Raises on failure.
    Use to verify service account access without appending rows.
    """
    client = get_client()
    sheet_id = get_sheet_id()
    tab_name = get_tracking_sheet_name()
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(tab_name)
    # Read first cell to confirm we have read access (and that the tab exists)
    _ = worksheet.acell("A1").value


def fill_formula_columns(
    spreadsheet,
    worksheet,
    *,
    source_row: int,
    first_fill_row: int,
    last_fill_row: int,
    col_letters: list[str] | None = None,
) -> int:
    """
    Fill formula columns by copying from source_row down to first_fill_row:last_fill_row.

    The sheet is the source of truth — no formulas are hardcoded here.
    source_row is read but never modified.

    Args:
        source_row:      1-based row to copy formulas FROM (not modified).
        first_fill_row:  1-based first row to fill (must be > source_row).
        last_fill_row:   1-based last row to fill (inclusive).
        col_letters:     Columns to fill; defaults to AUTOFILL_COL_LETTERS.

    Returns the number of rows filled, or 0 if nothing to do.
    """
    if col_letters is None:
        col_letters = AUTOFILL_COL_LETTERS

    if first_fill_row > last_fill_row:
        return 0

    sheet_id = worksheet.id
    col_indices = [_col_letter_to_index(c) for c in col_letters]

    # Build one copyPaste request per column (handles non-contiguous columns cleanly).
    requests = [
        {
            "copyPaste": {
                "source": {
                    "sheetId": sheet_id,
                    "startRowIndex": source_row - 1,      # 0-based, inclusive
                    "endRowIndex": source_row,             # 0-based, exclusive (one row)
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1,
                },
                "destination": {
                    "sheetId": sheet_id,
                    "startRowIndex": first_fill_row - 1,  # 0-based, inclusive
                    "endRowIndex": last_fill_row,          # 0-based, exclusive
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1,
                },
                "pasteType": "PASTE_FORMULA",
            }
        }
        for col_idx in col_indices
    ]

    spreadsheet.batch_update({"requests": requests})
    return last_fill_row - first_fill_row + 1


def append_tracking_rows(
    rows: list[list], *, dry_run: bool = False, autofill: bool = True
) -> tuple[int, int]:
    """
    Append rows to the Tracking tab. Each row is [Day, Start, End, "", Notes].
    After appending, fills formula columns (AUTOFILL_COL_LETTERS) by copying
    from the row directly above the first new row — unless autofill=False.

    Returns (rows_appended, rows_formula_filled).
    """
    if dry_run:
        return 0, 0

    if not rows:
        return 0, 0

    client = get_client()
    sheet_id = get_sheet_id()
    tab_name = get_tracking_sheet_name()

    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(tab_name)

    # Record where new rows will land (last data row in col A + 1).
    existing = len(worksheet.col_values(1))  # 1-based count of rows with data
    first_new_row = existing + 1

    # Append all rows in one batch (columns A:E; formula cols filled below).
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    last_new_row = first_new_row + len(rows) - 1

    filled = 0
    if autofill and first_new_row > 1:
        filled = fill_formula_columns(
            spreadsheet,
            worksheet,
            source_row=first_new_row - 1,
            first_fill_row=first_new_row,
            last_fill_row=last_new_row,
        )

    return len(rows), filled
