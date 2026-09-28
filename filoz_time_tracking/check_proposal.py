"""CLI: check a day proposal's billed time against the segmenter's FilOz candidates.

The boundaries gate (ADR 0004) says every billed minute comes from the
segmenter, but the drafter still chooses where entries start and end. This
check compares the two mechanically:

- **Unbilled FilOz:** time inside a FilOz (F) candidate of at least
  ``--min-span`` minutes that no billable entry covers. This catches a
  lead-in or tail trimmed by judgment, and also a relabel (the time is covered
  by a Madison entry instead).
- **Billed outside FilOz:** billable entry time that falls outside every F
  candidate.

Differences of ``--tolerance`` seconds or less are ignored (entries are rounded
to the minute). Every other difference must be declared in the proposal under a
``## Boundary deviations`` section, one line per range:

    - 14:37–14:41: relabelled to Madison (M1), Madison Gmail and Cursor

A difference counts as declared when it sits inside a listed range (give or take
the tolerance). The command exits 1 if any difference is undeclared.

Usage:
    uv run python -m filoz_time_tracking.check_proposal local/proposals/2026-09-17.md slice.txt
    uv run python -m filoz_time_tracking.check_proposal --whatsapp-personal proposal.md slice-am.txt slice-pm.txt
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from filoz_time_tracking.segment_activity import DETOUR_MAX_MINUTES, GAP_MAX_MINUTES, load_rows, merge, to_blocks

Interval = tuple[datetime, datetime]

_DAY_RE = re.compile(r"^# Day proposal: (\d{4}-\d{2}-\d{2})", re.M)
_ENTRY_RE = re.compile(r"^### (\S+) · (\d\d:\d\d)[–-](\d\d:\d\d) · (.+)$")
_PROJECT_RE = re.compile(r"^\*\*(.+?)\*\* · (billable|not billable)")
_DEVIATION_RE = re.compile(r"^- (\d\d:\d\d)[–-](\d\d:\d\d):?\s*(.*)$")


@dataclass
class Entry:
    label: str
    start: datetime
    end: datetime
    title: str
    project: str
    billable: bool


@dataclass
class Deviation:
    start: datetime
    end: datetime
    reason: str


def _span(day: str, start: str, end: str) -> Interval:
    s = datetime.fromisoformat(f"{day}T{start}")
    e = datetime.fromisoformat(f"{day}T{end}")
    if e <= s:
        e += timedelta(days=1)  # an entry ending at 00:00 ends at the next midnight
    return s, e


def parse_proposal(text: str) -> tuple[list[Entry], list[Deviation]]:
    """Read the entries and the declared boundary deviations from a day proposal."""
    day_match = _DAY_RE.search(text)
    if not day_match:
        raise ValueError("no '# Day proposal: YYYY-MM-DD' header")
    day = day_match.group(1)
    lines = text.splitlines()
    entries: list[Entry] = []
    deviations: list[Deviation] = []
    in_deviations = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_deviations = line.strip() == "## Boundary deviations"
            continue
        m = _ENTRY_RE.match(line)
        if m:
            project_line = next((l for l in lines[i + 1:] if l.strip()), "")
            p = _PROJECT_RE.match(project_line)
            if not p:
                raise ValueError(f"entry {m.group(1)}: no '**Project** · billable' line after its header")
            start, end = _span(day, m.group(2), m.group(3))
            entries.append(Entry(m.group(1), start, end, m.group(4), p.group(1), p.group(2) == "billable"))
            continue
        d = _DEVIATION_RE.match(line)
        if in_deviations and d:
            start, end = _span(day, d.group(1), d.group(2))
            deviations.append(Deviation(start, end, d.group(3)))
    return entries, deviations


def union(intervals: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def subtract(a: list[Interval], b: list[Interval]) -> list[Interval]:
    """Parts of the intervals in ``a`` not covered by any interval in ``b``."""
    out: list[Interval] = []
    b = union(b)
    for s, e in union(a):
        cur = s
        for bs, be in b:
            if be <= cur or bs >= e:
                continue
            if bs > cur:
                out.append((cur, bs))
            cur = max(cur, be)
        if cur < e:
            out.append((cur, e))
    return out


def check(entries: list[Entry], deviations: list[Deviation], candidates, min_span: float, tolerance: float) -> list[str]:
    """Return one line per boundary difference; undeclared ones start with 'UNDECLARED'."""
    tol = timedelta(seconds=tolerance)
    filoz = [(c.start, c.end) for c in candidates if c.cls == "F"]
    filoz_counted = [(s, e) for s, e in filoz if (e - s).total_seconds() >= min_span * 60]
    billed = [(e.start, e.end) for e in entries if e.billable]
    others = [e for e in entries if not e.billable]

    def covered_by(s: datetime, e: datetime) -> str:
        labels = [o.label for o in others if o.start < e and o.end > s]
        return f"covered by {', '.join(labels)}" if labels else "not covered by any entry"

    def declared(s: datetime, e: datetime) -> Deviation | None:
        return next((d for d in deviations if d.start - tol <= s and e <= d.end + tol), None)

    lines = []
    for kind, gaps in (("unbilled FilOz", subtract(filoz_counted, billed)), ("billed outside FilOz", subtract(billed, filoz))):
        for s, e in gaps:
            if (e - s) <= tol:
                continue
            where = f", {covered_by(s, e)}" if kind == "unbilled FilOz" else ""
            desc = f"{kind} {s:%H:%M:%S}-{e:%H:%M:%S} ({(e - s).total_seconds() / 60:.1f}m{where})"
            d = declared(s, e)
            lines.append(f"declared   {desc}: {d.reason}" if d else f"UNDECLARED {desc}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("proposal", help="local/proposals/YYYY-MM-DD.md")
    parser.add_argument("files", nargs="+", help="that day's activity_slice output files")
    parser.add_argument("--min-span", type=float, default=5, help="minutes; F candidates shorter than this need no entry (default 5)")
    parser.add_argument("--tolerance", type=float, default=60, help="seconds of difference to ignore, for minute rounding (default 60)")
    parser.add_argument("--detour-max", type=float, default=DETOUR_MAX_MINUTES, help=f"minutes; pass through to the segmenter (default {DETOUR_MAX_MINUTES})")
    parser.add_argument("--gap-max", type=float, default=GAP_MAX_MINUTES, help=f"minutes; pass through to the segmenter (default {GAP_MAX_MINUTES})")
    parser.add_argument("--whatsapp-personal", action="store_true", help="pass through to the segmenter")
    args = parser.parse_args(argv)

    with open(args.proposal) as f:
        entries, deviations = parse_proposal(f.read())
    rows = [row for path in args.files for row in load_rows(path, args.whatsapp_personal)]
    candidates = merge(to_blocks(rows, args.gap_max * 60), args.detour_max * 60, args.gap_max * 60)
    lines = check(entries, deviations, candidates, args.min_span, args.tolerance)
    undeclared = [l for l in lines if l.startswith("UNDECLARED")]
    print("\n".join(lines) if lines else "Billed time matches the segmenter's FilOz candidates.")
    if undeclared:
        print(f"\n{len(undeclared)} undeclared difference(s): bill the time, or list the range under '## Boundary deviations' with the reason.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
