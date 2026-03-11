"""CLI: import Timing App XLSX export into the Tracking tab. Use --dry-run to preview."""
import argparse
import sys

from . import config
from .google_sheet import append_tracking_rows
from .sheet_format import build_tracking_rows
from .timing_format import parse_timing_export


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Timing App Excel export to Tracking tab rows and append to the sheet."
    )
    parser.add_argument(
        "xlsx_path",
        type=str,
        nargs="?",
        default=None,
        help="Path to the Timing export XLSX file (e.g. FilOz & 8 subprojects.xlsx)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be appended without writing to the sheet.",
    )
    parser.add_argument(
        "--test-credentials",
        action="store_true",
        help="Verify service account can access the sheet (read-only, no rows added).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only add the first N rows (e.g. --limit 1 to add just one row).",
    )
    args = parser.parse_args()

    if args.test_credentials:
        try:
            from .google_sheet import test_credentials
            test_credentials()
            print("Credentials OK. Service account can access the sheet.")
            return 0
        except Exception as e:
            print(f"Credentials test failed: {e}", file=sys.stderr)
            return 1

    if not args.xlsx_path:
        parser.error("xlsx_path is required unless --test-credentials is used.")

    try:
        parsed = parse_timing_export(args.xlsx_path)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    if not parsed:
        print("No data rows found in the Timing export.", file=sys.stderr)
        return 0

    rows = build_tracking_rows(parsed)
    if args.limit is not None:
        if args.limit < 1:
            print("--limit must be at least 1.", file=sys.stderr)
            return 1
        if len(rows) > args.limit:
            print(f"Limiting to first {args.limit} row(s) (export has {len(rows)}).")
        rows = rows[: args.limit]

    if args.dry_run:
        print("DRY RUN – no changes will be made to the sheet.\n")
        print(f"Would append {len(rows)} row(s) to tab: {config.get_tracking_sheet_name()}")
        print("Columns: Day, Start, End, (Duration formula), Notes\n")
        show = min(10, len(rows))
        print(f"First {show} row(s):")
        print("-" * 80)
        for i, row in enumerate(rows[:show], 1):
            day, start, end, _, notes = row
            notes_preview = (notes[:60] + "…") if len(notes) > 60 else notes
            print(f"  {i}. {day}  {start}–{end}  {notes_preview}")
        if len(rows) > show:
            print(f"  ... and {len(rows) - show} more row(s).")
        print("-" * 80)
        return 0

    try:
        n = append_tracking_rows(rows, dry_run=False)
        print(f"Appended {n} row(s) to {config.get_tracking_sheet_name()}.")
        return 0
    except Exception as e:
        print(f"Error appending to sheet: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
