"""CLI: Gather structured audit data for an invoice period.

Reads all historical invoice tabs, the tracking sheet, and (optionally) the
downloaded XLSX for the target period, then prints a structured comparison
report. Designed to be run before LLM-assisted review — the script handles
the data gathering; the reasoning is done by the analyst.

Usage:
    uv run python -m filoz_time_tracking.audit_invoice --invoice 2026-5
    uv run python -m filoz_time_tracking.audit_invoice --invoice 2026-5 --xlsx "biglep invoice - 2026-5.xlsx"
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from . import config
from .google_sheet import get_client

_INVOICE_RE = re.compile(r"^(\d{4})-(\d{1,2})$")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_invoice(invoice: str) -> tuple[int, int]:
    m = _INVOICE_RE.match(invoice.strip())
    if not m:
        raise ValueError(f"--invoice must be YYYY-M or YYYY-MM (got: {invoice!r})")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise ValueError("Invoice month must be between 1 and 12.")
    return year, month


def _toku_key(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _cell(data: list, row: int, col: int, default="") -> object:
    try:
        return data[row - 1][col - 1]
    except IndexError:
        return default


def _fmt_num(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v) if v != "" else "—"


def _is_invoice_tab(title: str) -> bool:
    return bool(_INVOICE_RE.match(title))


def _tab_sort_key(title: str) -> tuple[int, int]:
    y, m = title.split("-")
    return int(y), int(m)


# ── Data gathering ────────────────────────────────────────────────────────────

def _read_invoice_tab(ws) -> dict:
    """Read key fields from one invoice tab. Two API calls (raw + formatted)."""
    raw = ws.get("A1:E50", value_render_option="UNFORMATTED_VALUE")
    fmt = ws.get("A1:E50", value_render_option="FORMATTED_VALUE")

    g  = lambda r, c: _cell(raw, r, c)
    gf = lambda r, c: _cell(fmt, r, c)

    totals_row = next(
        (i + 1 for i, r in enumerate(raw)
         if r and str(r[0]).strip() == "Invoice Totals"),
        None,
    )

    week_rows = []
    if totals_row:
        for r in range(22, totals_row):
            week_rows.append({
                "start": gf(r, 1),
                "days":  g(r, 2),
                "hours": g(r, 3),
            })

    # Bank details live in the lower section; search for labels rather than
    # hardcoding row numbers, since the row count shifts with week insertions.
    bank = {}
    for i, row in enumerate(raw, start=1):
        if not row:
            continue
        label = str(row[0]).strip().lower()
        val   = _cell(raw, i, 2)
        if "bank name" in label:
            bank["name"] = val
        elif "branch address" in label:
            bank["branch_address"] = val
        elif "name as mentioned" in label:
            bank["account_name"] = val
        elif "account number" in label:
            bank["account_number"] = val
        elif "routing" in label:
            bank["routing"] = val
        elif "currency" in label:
            bank["currency"] = val

    return {
        "invoice_date": gf(10, 2),
        "period":       gf(12, 2),
        "due_date":     gf(13, 2),
        "rate_usd":     g(20, 4),
        "rate_fil":     g(20, 5),
        "total_days":   g(totals_row, 2) if totals_row else None,
        "total_hours":  g(totals_row, 3) if totals_row else None,
        "total_usd":    g(totals_row, 4) if totals_row else None,
        "total_fil":    g(totals_row, 5) if totals_row else None,
        "weeks":        len(week_rows),
        "week_rows":    week_rows,
        "from_name":    g(2, 1),
        "from_address": g(3, 1),
        # Row 4 is blank, row 5 is the "To" label, row 6 is the company name
        "to_name":      g(6, 1),
        "to_address":   g(7, 1),
        "bank":         bank,
    }


def _read_tracking_hours(tracking_ws, toku: str) -> tuple[float, int]:
    """Return (total_hours, unique_days) from the tracking sheet for the period."""
    all_rows = tracking_ws.get("A1:J100000", value_render_option="UNFORMATTED_VALUE")
    day_hours: dict[int, float] = {}
    for row in all_rows[1:]:
        while len(row) < 10:
            row.append("")
        if str(row[9]).strip() != toku:
            continue
        try:
            day = int(row[0])
            hrs = float(row[6]) if row[6] != "" else 0.0
            day_hours[day] = day_hours.get(day, 0.0) + hrs
        except (ValueError, TypeError):
            pass
    return sum(day_hours.values()), len(day_hours)


def _read_xlsx_snapshot(path: Path) -> dict | None:
    """Read key fields from the downloaded XLSX. Returns None if file not found."""
    try:
        import openpyxl
    except ImportError:
        return None

    if not path.exists():
        return None

    wb = openpyxl.load_workbook(path)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))

    def xg(r, c, d=""):  # 1-based
        try:
            v = rows[r - 1][c - 1]
            return v if v is not None else d
        except IndexError:
            return d

    bank = {}
    for i, row in enumerate(rows, start=1):
        if not row or row[0] is None:
            continue
        label = str(row[0]).strip().lower()
        val = xg(i, 2)
        if "bank name" in label:
            bank["name"] = val
        elif "branch address" in label:
            bank["branch_address"] = val
        elif "name as mentioned" in label:
            bank["account_name"] = val
        elif "account number" in label:
            bank["account_number"] = val
        elif "routing" in label:
            bank["routing"] = val
        elif "currency" in label:
            bank["currency"] = val

    return {
        "from_name":    xg(2, 1),
        "from_address": xg(3, 1),
        # Row 4 is blank, row 5 is the "To" label, row 6 is the company name
        "to_name":      xg(6, 1),
        "to_address":   xg(7, 1),
        "invoice_date": xg(10, 2),
        "rate_usd":     xg(20, 4),
        "rate_fil":     xg(20, 5),
        "bank":         bank,
    }


# ── Report ────────────────────────────────────────────────────────────────────

def audit_invoice(invoice: str, xlsx_path: Path | None = None) -> None:
    year, month = _parse_invoice(invoice)
    target = f"{year}-{month}"
    toku   = _toku_key(year, month)

    print(f"\n{'='*65}")
    print(f"  INVOICE AUDIT: {target}")
    print(f"{'='*65}\n")

    # ── Connect ───────────────────────────────────────────────────────────────
    client     = get_client()
    invoice_ss = client.open_by_key(config.get_invoice_sheet_id())
    tracking_ss = client.open_by_key(config.get_sheet_id())
    tracking_ws = tracking_ss.worksheet(config.get_tracking_sheet_name())

    all_tabs = sorted(
        [ws for ws in invoice_ss.worksheets() if _is_invoice_tab(ws.title)],
        key=lambda w: _tab_sort_key(w.title),
    )
    tab_titles = [w.title for w in all_tabs]

    if target not in tab_titles:
        raise ValueError(f"Tab '{target}' not found in invoices workbook.")

    # ── Read all invoice tabs ─────────────────────────────────────────────────
    print(f"Reading {len(all_tabs)} invoice tabs (this takes ~{len(all_tabs)*3}s)...")
    results: dict[str, dict] = {}
    for ws in all_tabs:
        results[ws.title] = _read_invoice_tab(ws)
        print(f"  ✓ {ws.title}")
        time.sleep(1.5)   # stay under Sheets API read quota

    # ── Read tracking hours ───────────────────────────────────────────────────
    print(f"\nReading tracking sheet for {toku}...")
    tracked_hours, tracked_days = _read_tracking_hours(tracking_ws, toku)
    print(f"  ✓ {tracked_hours:.2f} hrs across {tracked_days} days")

    # ── Optionally read downloaded XLSX ───────────────────────────────────────
    xlsx_data = None
    if xlsx_path is None:
        default = Path(f"biglep invoice - {target}.xlsx")
        if default.exists():
            xlsx_path = default
    if xlsx_path:
        xlsx_data = _read_xlsx_snapshot(xlsx_path)
        if xlsx_data:
            print(f"  ✓ Read local XLSX: {xlsx_path}")

    t = results[target]
    prior_tabs = [r for r in results if r != target and results[r]["total_hours"] is not None]

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  1. HOURS CROSS-CHECK")
    print(f"{'─'*65}")
    inv_hours = t["total_hours"]
    try:
        inv_h = float(inv_hours)
        diff = inv_h - tracked_hours
        match = "✓ match" if abs(diff) < 0.05 else "⚠  MISMATCH"
        print(f"  Invoice total hours  : {inv_h:.2f}")
        print(f"  Tracking sheet hours : {tracked_hours:.2f}  ({tracked_days} days with entries)")
        print(f"  Difference           : {diff:+.2f}  {match}")
    except (TypeError, ValueError):
        print(f"  Invoice hours: {inv_hours}  |  Tracking: {tracked_hours:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  2. RATES")
    print(f"{'─'*65}")
    rate_groups: dict[tuple, list] = {}
    for tab, r in results.items():
        if r["rate_usd"] or r["rate_fil"]:
            k = (r["rate_usd"], r["rate_fil"])
            rate_groups.setdefault(k, []).append(tab)
    for (usd, fil), tabs_list in rate_groups.items():
        flag = "  ← TARGET" if target in tabs_list else ""
        print(f"  USD={usd}  FIL={fil}  → {tabs_list}{flag}")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  3. TOTALS vs HISTORY  (tabs with structured data)")
    print(f"{'─'*65}")
    structured = [tab for tab in tab_titles if results[tab]["total_hours"] is not None]
    print(f"  {'Tab':<10} {'Wks':>4} {'Days':>5} {'Hours':>8} {'USD total':>12} {'FIL total':>12}")
    print(f"  {'-'*10} {'-'*4} {'-'*5} {'-'*8} {'-'*12} {'-'*12}")
    for tab in structured:
        r = results[tab]
        flag = "  ← TARGET" if tab == target else ""
        try:
            h = f"{float(r['total_hours']):.2f}"
        except (TypeError, ValueError):
            h = "—"
        print(f"  {tab:<10} {r['weeks']:>4} {str(r['total_days'] or '—'):>5} "
              f"{h:>8} {_fmt_num(r['total_usd']):>12} {_fmt_num(r['total_fil']):>12}{flag}")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  4. WEEK BREAKDOWN  ({target})")
    print(f"{'─'*65}")
    for i, w in enumerate(t["week_rows"], 1):
        try:
            h = f"{float(w['hours']):.2f}"
        except (TypeError, ValueError):
            h = str(w["hours"])
        print(f"  Week {i}: start={w['start']:<14}  days={w['days']}  hours={h}")
    print(f"  Totals : days={t['total_days']}  hours={_fmt_num(t['total_hours'])}")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  5. DATES")
    print(f"{'─'*65}")
    for tab in structured:
        r = results[tab]
        flag = "  ← TARGET" if tab == target else ""
        print(f"  {tab:<10}  invoice={str(r['invoice_date']):<12}  "
              f"period={str(r['period']):<28}  due={r['due_date']}{flag}")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  6. ADDRESSES  ({target} vs previous)")
    print(f"{'─'*65}")
    if prior_tabs:
        prev = prior_tabs[-1]
        for field, label in [("from_name","From name"), ("from_address","From address"),
                              ("to_name","To name"),   ("to_address","To address")]:
            tv = t.get(field, "")
            pv = results[prev].get(field, "")
            flag = "  ⚠  DIFFERS" if str(tv).strip() != str(pv).strip() else ""
            print(f"  {label:<16}: {str(tv)!r:<45}  (prev: {str(pv)!r}){flag}")

    # ─────────────────────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  7. BANK DETAILS  ({target} vs previous)")
    print(f"{'─'*65}")
    bank_t = t.get("bank", {})
    bank_p = results[prior_tabs[-1]].get("bank", {}) if prior_tabs else {}
    for key in ["name", "branch_address", "account_name", "account_number", "routing", "currency"]:
        tv = bank_t.get(key, "")
        pv = bank_p.get(key, "")
        flag = "  ⚠  DIFFERS" if str(tv).strip() != str(pv).strip() else ""
        print(f"  {key:<16}: {str(tv)!r:<45}  (prev: {str(pv)!r}){flag}")

    # ─────────────────────────────────────────────────────────────────────────
    if xlsx_data:
        print(f"\n{'─'*65}")
        print(f"  8. XLSX SNAPSHOT (downloaded file)")
        print(f"{'─'*65}")
        print(f"  From      : {xlsx_data.get('from_name')}  |  {xlsx_data.get('from_address','').replace(chr(10),' ')}")
        print(f"  To        : {xlsx_data.get('to_name')}  |  {xlsx_data.get('to_address','').replace(chr(10),' ')}")
        print(f"  Inv date  : {xlsx_data.get('invoice_date')}")
        print(f"  Rate USD  : {xlsx_data.get('rate_usd')}  FIL: {xlsx_data.get('rate_fil')}")
        xb = xlsx_data.get("bank", {})
        print(f"  Bank      : {xb.get('name','')}  acct={xb.get('account_number','')}  "
              f"routing={xb.get('routing','')}  name={xb.get('account_name','')}")

    print(f"\n{'='*65}")
    print(f"  Audit data complete. Review sections above for anomalies.")
    print(f"{'='*65}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gather structured audit data for an invoice period."
    )
    parser.add_argument(
        "--invoice", required=True, metavar="YYYY-N",
        help="Invoice period to audit, e.g. 2026-5",
    )
    parser.add_argument(
        "--xlsx", metavar="PATH",
        help=(
            'Path to the downloaded invoice XLSX '
            '(default: "biglep invoice - YYYY-N.xlsx" in the current directory).'
        ),
    )
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx).expanduser() if args.xlsx else None

    try:
        audit_invoice(args.invoice, xlsx_path)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
