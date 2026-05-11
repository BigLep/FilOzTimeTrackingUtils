"""CLI: analyze the Tracking tab for a given invoice period.

Checks for:
- Hours summary vs. recent period averages
- Missing weekdays (possible untracked days or vacation)
- Travel days billed at exactly 8 hrs (per contract)
- Unusually high or low individual days
- Long single entries (possible forgotten timer stop)
- Sub-5-minute entries (possible tracking noise)
- Overlapping entries within the same day
- Project/category breakdown

Usage:
    uv run python -m filoz_time_tracking.analyze_tracking --invoice 2026-5
    uv run python -m filoz_time_tracking.analyze_tracking --invoice 2026-5 --context-periods 13
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import re

from . import config
from .google_sheet import get_client, get_sheet_id, get_tracking_sheet_name

_INVOICE_RE = re.compile(r"^(\d{4})-(\d{1,2})$")


def _invoice_date_range(invoice: str) -> tuple:
    """Return (start_date, end_date) for an invoice shorthand like '2026-5'."""
    from datetime import date
    m = _INVOICE_RE.match(invoice.strip())
    if not m:
        raise ValueError(f"--invoice must be YYYY-M or YYYY-MM (got: {invoice!r})")
    year, month = int(m.group(1)), int(m.group(2))
    if month == 1:
        start = date(year - 1, 12, 10)
    else:
        start = date(year, month - 1, 10)
    return start, date(year, month, 9)


# Keywords in Notes that indicate a travel day (case-insensitive).
TRAVEL_KEYWORDS = ["travel", "colo", "flight", "airport", "driving to", "drove to"]

# Per-contract: travel days should be billed as exactly this many hours.
CONTRACT_TRAVEL_HOURS = 8.0


def _is_travel_entry(notes: str) -> bool:
    lower = notes.lower()
    return any(kw in lower for kw in TRAVEL_KEYWORDS)


def _load_all_records(worksheet) -> list[dict]:
    """Fetch all data rows from the Tracking tab as dicts."""
    all_rows = worksheet.get("A1:J100000", value_render_option="FORMATTED_VALUE")
    records = []
    for row in all_rows[1:]:  # skip header
        while len(row) < 10:
            row.append("")
        try:
            records.append({
                "day":     row[0],
                "start":   row[1],
                "end":     row[2],
                "dur_str": row[3],
                "notes":   row[4],
                "dur":     float(row[6]) if row[6] else 0.0,
                "year":    int(row[7]) if row[7] else 0,
                "month":   int(row[8]) if row[8] else 0,
                "toku":    row[9],
            })
        except Exception:
            pass
    return records


def _group_by_period(records: list[dict]) -> dict:
    """Group records by Toku Invoice period."""
    by_toku: dict = defaultdict(lambda: {"hours": 0.0, "days": set(), "entries": []})
    for r in records:
        t = r["toku"]
        if not t:
            continue
        by_toku[t]["hours"] += r["dur"]
        by_toku[t]["days"].add(r["day"])
        by_toku[t]["entries"].append(r)
    return dict(by_toku)


def analyze(invoice: str, context_periods: int = 13) -> None:
    """Run the full analysis for the given invoice period and print a report."""
    # Resolve date range for display
    start_date, end_date = _invoice_date_range(invoice)

    print(f"\n{'='*60}")
    print(f"  INVOICE PERIOD ANALYSIS: {invoice}")
    print(f"  Range: {start_date} to {end_date}")
    print(f"{'='*60}\n")

    # Load sheet data
    client = get_client()
    spreadsheet = client.open_by_key(get_sheet_id())
    ws = spreadsheet.worksheet(get_tracking_sheet_name())
    records = _load_all_records(ws)
    by_toku = _group_by_period(records)

    toku_key = f"{invoice[:4]}-{invoice[5:].zfill(2)}"  # normalise e.g. 2026-5 → 2026-05
    if toku_key not in by_toku:
        print(f"No entries found for period '{toku_key}'. Check that data has been imported.")
        return

    cur = by_toku[toku_key]
    cur_entries = cur["entries"]

    # --- Historical context ---
    sorted_periods = sorted(by_toku.keys())
    past_periods = [p for p in sorted_periods if p < toku_key][-context_periods:]
    if past_periods:
        past_hrs  = [by_toku[p]["hours"] for p in past_periods]
        avg_hrs   = sum(past_hrs) / len(past_hrs)
        stddev    = math.sqrt(sum((x - avg_hrs) ** 2 for x in past_hrs) / len(past_hrs))
        z_score   = (cur["hours"] - avg_hrs) / stddev if stddev else 0
        avg_days  = sum(len(by_toku[p]["days"]) for p in past_periods) / len(past_periods)
    else:
        avg_hrs = avg_days = stddev = z_score = 0

    # --- Per-day totals ---
    by_day: dict[str, float] = defaultdict(float)
    for e in cur_entries:
        by_day[e["day"]] += e["dur"]

    # ── Section 1: Summary ──────────────────────────────────────────────
    print("── SUMMARY ────────────────────────────────────────────────────")
    print(f"  Total hours:   {cur['hours']:.1f} hrs")
    print(f"  Working days:  {len(cur['days'])}")
    print(f"  Entries:       {len(cur_entries)}")
    if past_periods:
        direction = "+" if cur["hours"] >= avg_hrs else ""
        print(f"  Avg hrs/period (last {len(past_periods)}): {avg_hrs:.1f}  "
              f"({direction}{cur['hours'] - avg_hrs:.1f} vs avg, z={z_score:.2f})")
        direction = "+" if len(cur["days"]) >= avg_days else ""
        print(f"  Avg days/period:              {avg_days:.1f}  "
              f"({direction}{len(cur['days']) - avg_days:.1f} vs avg)")

    # ── Section 2: Historical period table ──────────────────────────────
    print(f"\n── RECENT PERIODS (last {len(past_periods)}) ─────────────────────────────────")
    for p in past_periods:
        h = by_toku[p]["hours"]
        d = len(by_toku[p]["days"])
        bar = "█" * int(h / 10)
        print(f"  {p}: {h:6.1f} hrs / {d:2d} days  {bar}")
    cur_bar = "█" * int(cur["hours"] / 10)
    print(f"  {toku_key}: {cur['hours']:6.1f} hrs / {len(cur['days']):2d} days  {cur_bar}  ◄ current")

    # ── Section 3: Project breakdown ────────────────────────────────────
    print("\n── PROJECT BREAKDOWN ──────────────────────────────────────────")
    by_proj: dict[str, float] = defaultdict(float)
    for e in cur_entries:
        p = e["notes"].split(":")[0].strip() if ":" in e["notes"] else e["notes"]
        by_proj[p] += e["dur"]
    for p, h in sorted(by_proj.items(), key=lambda x: -x[1]):
        pct = h / cur["hours"] * 100 if cur["hours"] else 0
        print(f"  {p:<35} {h:5.1f} hrs  ({pct:.0f}%)")

    # ── Section 4: Day-level detail ──────────────────────────────────────
    print("\n── HOURS PER DAY ──────────────────────────────────────────────")
    for d in sorted(by_day):
        h = by_day[d]
        flag = "  *** HIGH (>10h)" if h > 10 else ("  ?? very low (<1h)" if h < 1 else "")
        print(f"  {d}: {h:.2f} hrs{flag}")

    # ── Section 5: Missing weekdays ──────────────────────────────────────
    print("\n── MISSING WEEKDAYS ───────────────────────────────────────────")
    sorted_days = sorted(by_day.keys())
    if sorted_days:
        d = datetime.strptime(sorted_days[0], "%Y-%m-%d").date()
        end_d = datetime.strptime(sorted_days[-1], "%Y-%m-%d").date()
        gaps = []
        while d <= end_d:
            if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in by_day:
                gaps.append(str(d))
            d += timedelta(days=1)
        if gaps:
            # Group consecutive gaps for readability
            groups, group = [], [gaps[0]]
            for g in gaps[1:]:
                prev = datetime.strptime(group[-1], "%Y-%m-%d").date()
                curr = datetime.strptime(g, "%Y-%m-%d").date()
                if (curr - prev).days <= 3:  # allow weekend bridge
                    group.append(g)
                else:
                    groups.append(group)
                    group = [g]
            groups.append(group)
            for grp in groups:
                if len(grp) == 1:
                    print(f"  {grp[0]}  (1 day)")
                else:
                    print(f"  {grp[0]} – {grp[-1]}  ({len(grp)} weekdays)  ← check calendar")
        else:
            print("  None — all weekdays accounted for.")

    # ── Section 6: Travel day billing check ──────────────────────────────
    print("\n── TRAVEL DAY BILLING CHECK (contract: 8.0 hrs each) ─────────")
    travel_days: dict[str, list] = defaultdict(list)
    for e in cur_entries:
        if _is_travel_entry(e["notes"]):
            travel_days[e["day"]].append(e)
    if travel_days:
        issues = []
        for d, entries in sorted(travel_days.items()):
            day_total = by_day[d]
            status = "OK" if abs(day_total - CONTRACT_TRAVEL_HOURS) < 0.1 else "⚠ REVIEW"
            print(f"  {d}: {day_total:.2f} hrs  [{status}]")
            for e in entries:
                print(f"    {e['start']}-{e['end']} ({e['dur_str']}): {e['notes']}")
            if status != "OK":
                issues.append(d)
        if issues:
            print(f"\n  ⚠  {len(issues)} travel day(s) not at exactly {CONTRACT_TRAVEL_HOURS} hrs — review before submitting.")
    else:
        print("  No travel day entries detected this period.")

    # ── Section 7: Anomalous entries ────────────────────────────────────
    print("\n── ANOMALOUS ENTRIES ──────────────────────────────────────────")

    long_entries = [e for e in cur_entries if e["dur"] > 6 and not _is_travel_entry(e["notes"])]
    print(f"  Long single entries >6 hrs (non-travel): {len(long_entries)}")
    for e in long_entries:
        print(f"    {e['day']} {e['start']}-{e['end']} ({e['dur_str']}): {e['notes']}")

    short_entries = [e for e in cur_entries if 0 < e["dur"] < 0.083]
    print(f"  Sub-5-min entries (possible noise): {len(short_entries)}")
    for e in short_entries:
        print(f"    {e['day']} {e['start']}-{e['end']} ({e['dur_str']}): {e['notes']}")

    # ── Section 8: Overlaps ──────────────────────────────────────────────
    print("\n── OVERLAPPING ENTRIES ────────────────────────────────────────")
    day_ents: dict[str, list] = defaultdict(list)
    for e in cur_entries:
        day_ents[e["day"]].append(e)
    overlaps = []
    for d, ents in day_ents.items():
        ents_sorted = sorted(ents, key=lambda x: x["start"])
        for i in range(len(ents_sorted) - 1):
            if ents_sorted[i]["end"] > ents_sorted[i + 1]["start"]:
                overlaps.append((d, ents_sorted[i], ents_sorted[i + 1]))
    if overlaps:
        for d, a, b in overlaps:
            print(f"  {d}: {a['start']}-{a['end']} overlaps {b['start']}-{b['end']}")
            print(f"    {a['notes']}")
            print(f"    {b['notes']}")
    else:
        print("  None.")

    print(f"\n{'='*60}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the Tracking tab for a given invoice period."
    )
    parser.add_argument(
        "--invoice",
        required=True,
        metavar="YYYY-N",
        help="Invoice period to analyze, e.g. 2026-5",
    )
    parser.add_argument(
        "--context-periods",
        type=int,
        default=13,
        metavar="N",
        help="Number of prior periods to use for comparison (default: 13).",
    )
    args = parser.parse_args()

    try:
        analyze(args.invoice, context_periods=args.context_periods)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
