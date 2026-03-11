"""Append rows to the Tracking tab via Google Sheets API. Supports dry-run (no writes)."""
from __future__ import annotations

import os

import gspread
from google.oauth2.service_account import Credentials

from .config import get_credentials_path, get_sheet_id, get_tracking_sheet_name

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


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


def append_tracking_rows(rows: list[list], *, dry_run: bool = False) -> int:
    """
    Append rows to the Tracking tab. Each row is [Day, Start, End, "", Notes].
    Returns number of rows appended (0 if dry_run).
    """
    if dry_run:
        return 0

    if not rows:
        return 0

    client = get_client()
    sheet_id = get_sheet_id()
    tab_name = get_tracking_sheet_name()

    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(tab_name)

    # Append all rows in one batch (columns A:E; D is left for the sheet's Duration formula)
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)
