"""CLI: Download a single invoice tab from the invoices workbook as an XLSX file.

Workflow:
    1. Export the entire invoices workbook as XLSX via the Drive API (in memory).
    2. Use openpyxl to remove every sheet except the target tab.
    3. Write the resulting single-sheet workbook to disk.

Why client-side stripping with openpyxl instead of a server-side approach:
  - The Google Sheets API has no "export a single tab" endpoint; it always
    exports the full workbook.
  - The obvious alternative — copy the tab to a new temporary spreadsheet,
    export that, then delete it — requires creating a file in Google Drive.
    Service accounts have a negligible Drive storage quota (~0 bytes for new
    accounts), so spreadsheet creation fails immediately with a quota error.
  - Routing the copy to the user's personal Drive would require domain-wide
    delegation, which is significantly more complex to set up.
  - openpyxl sheet deletion is trivial (one line per unwanted sheet) and runs
    entirely in memory — no storage, no cleanup, no side effects.

No temporary spreadsheets are created; everything happens in memory.

The invoices spreadsheet must be shared with the service account (at least
Viewer access). The Google Drive API must be enabled in the Cloud project.

Usage:
    uv run python -m filoz_time_tracking.download_invoice_sheet --invoice 2026-5
    uv run python -m filoz_time_tracking.download_invoice_sheet --invoice 2026-5 --output ~/Desktop/"biglep invoice - 2026-5.xlsx"
    uv run python -m filoz_time_tracking.download_invoice_sheet --invoice 2026-5 --dry-run
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path

import openpyxl
import requests as _requests
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
import gspread

from . import config

_INVOICE_RE = re.compile(r"^(\d{4})-(\d{1,2})$")

DRIVE_EXPORT_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/export"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_credentials() -> Credentials:
    path = config.get_credentials_path()
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(
            "GOOGLE_APPLICATION_CREDENTIALS must point to a service account JSON file. "
            "Share the invoices Google Sheet with the service account (at least Viewer access)."
        )
    return Credentials.from_service_account_file(path, scopes=SCOPES)


def _parse_invoice(invoice: str) -> tuple[int, int]:
    m = _INVOICE_RE.match(invoice.strip())
    if not m:
        raise ValueError(f"--invoice must be YYYY-M or YYYY-MM (got: {invoice!r})")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise ValueError("Invoice month must be between 1 and 12.")
    return year, month


def download_invoice_sheet(
    invoice: str,
    output: str | None = None,
    *,
    dry_run: bool = False,
) -> Path:
    """
    Download a single invoice tab from the invoices workbook as a clean XLSX file.

    Steps:
        1. Export the full workbook as XLSX bytes via the Drive API.
        2. Open with openpyxl and delete every sheet except the target tab.
        3. Write the single-sheet workbook to disk.

    Args:
        invoice:  Invoice period, e.g. "2026-5".
        output:   Output file path. Defaults to "biglep invoice - YYYY-N.xlsx" in cwd.
        dry_run:  If True, print actions without downloading or writing anything.

    Returns the resolved output Path (even in dry_run mode).
    """
    year, month = _parse_invoice(invoice)
    tab_name = f"{year}-{month}"
    spreadsheet_id = config.get_invoice_sheet_id()

    if output is None:
        output_path = Path(f"biglep invoice - {tab_name}.xlsx")
    else:
        output_path = Path(output).expanduser()

    print(f"\n{'='*60}")
    print(f"  DOWNLOAD INVOICE SHEET: {tab_name}")
    print(f"  Source spreadsheet:     {spreadsheet_id}")
    print(f"  Output file:            {output_path.resolve()}")
    if dry_run:
        print(f"  *** DRY RUN — no files will be written ***")
    print(f"{'='*60}\n")

    if dry_run:
        print(f"  Would export workbook from Drive API as XLSX (in memory)")
        print(f"  Would isolate sheet '{tab_name}' with openpyxl (remove all other tabs)")
        print(f"  Would write: {output_path.resolve()}")
        print(f"\nDRY RUN complete — no files written.\n")
        return output_path

    # ── Authenticate ──────────────────────────────────────────────────────────
    creds = _get_credentials()
    creds.refresh(Request())

    # ── Verify the tab exists before downloading the whole workbook ───────────
    print(f"Verifying sheet '{tab_name}' exists...")
    gspread_client = gspread.authorize(creds)
    invoice_ss = gspread_client.open_by_key(spreadsheet_id)
    all_tabs = [ws.title for ws in invoice_ss.worksheets()]
    if tab_name not in all_tabs:
        raise ValueError(
            f"Sheet '{tab_name}' not found in the invoices workbook. "
            f"Available sheets: {all_tabs}"
        )
    print(f"  ✓ Found '{tab_name}' ({len(all_tabs)} total sheets in workbook)")

    # ── Export the full workbook as XLSX via Drive API ────────────────────────
    print(f"Exporting workbook from Drive API...")
    url = DRIVE_EXPORT_URL.format(file_id=spreadsheet_id)
    resp = _requests.get(
        url,
        params={"mimeType": XLSX_MIME},
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=60,
    )
    resp.raise_for_status()
    print(f"  ✓ Downloaded workbook ({len(resp.content):,} bytes)")

    # ── Strip all sheets except the target ────────────────────────────────────
    print(f"Isolating sheet '{tab_name}'...")
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    to_remove = [name for name in wb.sheetnames if name != tab_name]
    for name in to_remove:
        del wb[name]
    print(f"  ✓ Removed {len(to_remove)} other sheet(s), kept '{tab_name}'")

    # ── Write to disk ─────────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"  ✓ Saved to {output_path.resolve()}")

    print(f"\n{'='*60}")
    print(f"  Done! Invoice file ready: {output_path}")
    print(f"  Upload to Toku: https://app.toku.com/myinfo/invoices")
    print(f"{'='*60}\n")

    return output_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download a single invoice tab from the invoices workbook as an XLSX file "
            "ready for upload to Toku."
        )
    )
    parser.add_argument(
        "--invoice",
        required=True,
        metavar="YYYY-N",
        help="Invoice period to download, e.g. 2026-5",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help=(
            'Output file path (default: "biglep invoice - YYYY-N.xlsx" in the current directory). '
            "Tilde expansion is supported."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without downloading or writing any files.",
    )
    args = parser.parse_args()

    try:
        download_invoice_sheet(args.invoice, args.output, dry_run=args.dry_run)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
