"""Build Tracking tab rows from parsed Timing rows. Only Day, Start, End, Notes are inserted; D is blank for formula."""

TRACKING_ROW_LEN = 5  # [Day, Start, End, "", Notes]
FILOZ_PREFIX = "FilOz ▸ "  # Strip from project so notes show e.g. "Communication: Title"


def timing_row_to_tracking_row(row: dict) -> list:
    """
    Convert one parsed Timing row to a row for the Tracking tab.
    Returns [Day, Start, End, "", Notes] so column D (Duration) is left for the sheet formula.
    Notes = "{Project}: {Title}" with "FilOz ▸ " removed from the start of Project.
    """
    project = (row.get("project") or "").strip()
    if project.startswith(FILOZ_PREFIX):
        project = project[len(FILOZ_PREFIX) :].strip()
    title = (row.get("title") or "").strip()
    notes = f"{project}: {title}".strip(" :")
    return [
        row.get("day", ""),
        row.get("start", ""),
        row.get("end", ""),
        "",  # D = Duration (formula in sheet)
        notes,
    ]


def build_tracking_rows(parsed: list[dict]) -> list[list]:
    """Convert all parsed Timing rows to Tracking rows."""
    return [timing_row_to_tracking_row(r) for r in parsed]
