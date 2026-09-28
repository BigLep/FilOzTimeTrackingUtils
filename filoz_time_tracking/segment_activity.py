"""CLI: segment Timing activity into candidate time entries using the ADR 0001 rules.

Reads raw ``activity_slice`` output from the timing-local MCP (the plain-text
table, or the JSON wrapper Claude Code persists large tool results in), labels
each activity row FilOz (F), Madison (M), or personal (P) from its app and
context, and merges the rows into candidate entries:

- A foreign stretch of more than 2 minutes (``--detour-max``) ends an entry.
- Silence of more than 5 minutes (``--gap-max``) ends an entry.
- Shorter foreign glances are absorbed into the surrounding entry, and their
  total is reported so the proposal can note (and flag) them.

The output is a starting point for a day proposal, not the proposal itself.
Classification is mostly by app, so some activity is mislabeled (Messages
contacts, Orca, WhatsApp on a day it wasn't Madison). Two exceptions use more
than the app: a Brave ``localhost`` row that Timing filed under Madison is
Madison (Plannotator reviewing a Madison repo; Timing sees the page title, the
slice only shows the domain), and all WhatsApp is Madison unless
``--whatsapp-personal``. The accuracy gates that catch the rest are in
docs/adr/0004 and the timing-daily-draft skill; subprojects, titles, and
meetings are also left to that process.

With ``--detail``, each candidate is followed by what was in it: the top
app / context (domain, file path, or window title) / Timing-project lines by
time, each marked with its class. That is the input the content-check gate
needs, without re-reading the raw rows.

Usage:
    uv run python -m filoz_time_tracking.segment_activity slice-morning.txt slice-afternoon.txt
    uv run python -m filoz_time_tracking.segment_activity --detail --min-span 5 slice.txt
    uv run python -m filoz_time_tracking.segment_activity --whatsapp-personal slice.txt
    uv run python -m filoz_time_tracking.segment_activity --min-span 5 slice.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

FILOZ_APPS = {"Brave Browser", "Slack", "Orca", "Zoom", "Granola", "Google Meet", "Trello", "Timing", "MeetingBar", "Warp"}
MADISON_APPS = {"Dia"}
PERSONAL_APPS = {"Safari", "Messages", "Mail", "Books", "Netflix", "Phone", "KaraFun", "Drawful 2", "Preview", "FaceTime"}
MADISON_PROJECT = "Volunteering ▸ Madison Ultimate"
# Apps that say nothing about the thread of work: they inherit the previous row's class.
NEUTRAL_APPS = {"Timing Tracker", "System Settings", "Finder", "loginwindow", "Claude", "ChatGPT", "Terminal", "Xcode", "Spotify"}

# ADR 0001 rules, in minutes: a longer foreign stretch, or longer silence, ends an entry.
DETOUR_MAX_MINUTES = 2
GAP_MAX_MINUTES = 5

_ROW_RE = re.compile(r"(\d\d:\d\d:\d\d)-(\d\d:\d\d:\d\d) \| [^|]+\| ([^|]+)\| ([^|]+)\|")


@dataclass
class Block:
    cls: str
    start: datetime
    end: datetime
    active: float  # seconds of activity, excluding gaps
    absorbed: dict[str, float] = field(default_factory=dict)


def classify(app: str, context: str, project: str = "", whatsapp_personal: bool = False) -> str:
    """Return F, M, P, or N (neutral) for one activity row."""
    if app == "Cursor":
        if "Madison" in context:
            return "M"
        return "F" if "filoz" in context.lower() else "N"
    if app == "WhatsApp":
        # Rows carry no chat name; in practice WhatsApp is the Madison coach groups.
        return "P" if whatsapp_personal else "M"
    if app == "Brave Browser" and context.startswith("localhost") and project.startswith(MADISON_PROJECT):
        # Plannotator on a Madison repo, opened in the FilOz Brave profile.
        return "M"
    if app in NEUTRAL_APPS:
        return "N"
    if app in FILOZ_APPS:
        return "F"
    if app in MADISON_APPS:
        return "M"
    if app in PERSONAL_APPS:
        return "P"
    return "N"


def load_rows(path: str, whatsapp_personal: bool = False) -> list[tuple[datetime, datetime, str, str, str, str]]:
    with open(path) as f:
        text = f.read()
    if text.lstrip().startswith("["):
        text = json.loads(text)[0]["text"]
    day_match = re.search(r"Time range: (\d{4}-\d{2}-\d{2})", text)
    if not day_match:
        raise ValueError(f"{path}: no 'Time range:' header; is this activity_slice output?")
    day = day_match.group(1)
    rows = []
    for line in text.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        start = datetime.fromisoformat(f"{day}T{m.group(1)}")
        end = datetime.fromisoformat(f"{day}T{m.group(2)}")
        if end < start:
            end += timedelta(days=1)
        app, context = m.group(3).strip(), m.group(4).strip()
        project = line.rsplit("|", 1)[-1].strip()
        rows.append((start, end, app, context, classify(app, context, project, whatsapp_personal), project))
    return rows


def to_blocks(rows, gap_max: float) -> list[Block]:
    """Collapse consecutive same-class rows into blocks; neutral rows inherit the previous class."""
    blocks: list[Block] = []
    last_cls = None
    for start, end, _app, _context, cls, _project in sorted(rows):
        if cls == "N":
            cls = last_cls or "N"
        else:
            last_cls = cls
        seconds = (end - start).total_seconds()
        if blocks and blocks[-1].cls == cls and (start - blocks[-1].end).total_seconds() <= gap_max:
            blocks[-1].end = max(blocks[-1].end, end)
            blocks[-1].active += seconds
        else:
            blocks.append(Block(cls, start, end, seconds))
    return blocks


def merge(blocks: list[Block], detour_max: float, gap_max: float) -> list[Block]:
    """Absorb foreign runs of at most detour_max seconds between two blocks of the same class."""
    entries: list[Block] = []
    i = 0
    while i < len(blocks):
        cur = Block(blocks[i].cls, blocks[i].start, blocks[i].end, blocks[i].active)
        i += 1
        while i < len(blocks):
            nxt = blocks[i]
            if nxt.cls == cur.cls and (nxt.start - cur.end).total_seconds() <= gap_max:
                cur.end, cur.active = nxt.end, cur.active + nxt.active
                i += 1
                continue
            # Look ahead over a run of foreign blocks; absorb it if the class resumes soon enough.
            j, foreign, prev_end = i, {}, cur.end
            while j < len(blocks) and blocks[j].cls != cur.cls:
                if (blocks[j].start - prev_end).total_seconds() > gap_max:
                    break
                foreign[blocks[j].cls] = foreign.get(blocks[j].cls, 0) + blocks[j].active
                prev_end = blocks[j].end
                j += 1
            resumes = j < len(blocks) and blocks[j].cls == cur.cls and (blocks[j].start - prev_end).total_seconds() <= gap_max
            if resumes and sum(foreign.values()) <= detour_max:
                for cls, seconds in foreign.items():
                    cur.absorbed[cls] = cur.absorbed.get(cls, 0) + seconds
                cur.end, cur.active = blocks[j].end, cur.active + blocks[j].active
                i = j + 1
                continue
            break
        entries.append(cur)
    return entries


def detail_lines(entry: Block, rows, top: int, min_seconds: float) -> list[str]:
    """Top app / context / Timing-project lines by time inside an entry's span."""
    totals: dict[tuple[str, str, str, str], float] = {}
    for start, end, app, context, cls, project in rows:
        overlap = (min(end, entry.end) - max(start, entry.start)).total_seconds()
        if overlap > 0:
            key = (cls, app, context, project)
            totals[key] = totals.get(key, 0) + overlap
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    shown = [(k, v) for k, v in ranked[:top] if v >= min_seconds]
    lines = [f"    {v / 60:5.1f}m {cls} {app} | {context} | {project}" for (cls, app, context, project), v in shown]
    rest = sum(v for _, v in ranked) - sum(v for _, v in shown)
    if rest >= 1:
        lines.append(f"    {rest / 60:5.1f}m in {len(ranked) - len(shown)} other lines")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", help="activity_slice output files for one day (any order)")
    parser.add_argument("--detour-max", type=float, default=DETOUR_MAX_MINUTES, help=f"minutes; a longer foreign stretch ends an entry (default {DETOUR_MAX_MINUTES})")
    parser.add_argument("--gap-max", type=float, default=GAP_MAX_MINUTES, help=f"minutes; longer silence ends an entry (default {GAP_MAX_MINUTES})")
    parser.add_argument("--min-span", type=float, default=0, help="minutes; hide candidates shorter than this")
    parser.add_argument("--detail", action="store_true", help="list what each candidate contains (top app/context/project lines)")
    parser.add_argument("--detail-top", type=int, default=8, help="lines per candidate with --detail (default 8)")
    parser.add_argument("--whatsapp-personal", action="store_true", help="treat WhatsApp as personal (default is Madison); use on days with non-Madison chats")
    args = parser.parse_args(argv)

    rows = [row for path in args.files for row in load_rows(path, args.whatsapp_personal)]
    if not rows:
        print("No activity rows found.", file=sys.stderr)
        return 1
    entries = merge(to_blocks(rows, args.gap_max * 60), args.detour_max * 60, args.gap_max * 60)
    for e in entries:
        span = (e.end - e.start).total_seconds() / 60
        if span < args.min_span:
            continue
        absorbed = ", ".join(f"{cls}:{seconds / 60:.1f}m" for cls, seconds in e.absorbed.items())
        pct = sum(e.absorbed.values()) / 60 / span * 100 if span else 0
        flag = " FLAG>10%" if e.cls == "F" and pct > 10 else ""
        print(f"{e.cls} {e.start:%H:%M:%S}-{e.end:%H:%M:%S} span={span:5.1f}m active={e.active / 60:5.1f}m"
              + (f" absorbed[{absorbed}]" if absorbed else "") + flag + (" SHORT" if span < 5 else ""))
        if args.detail:
            print("\n".join(detail_lines(e, rows, args.detail_top, 20)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
