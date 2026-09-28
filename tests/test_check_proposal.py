"""Tests for check_proposal: billed time versus the segmenter's FilOz candidates (stdlib unittest)."""
import unittest
from datetime import datetime

from filoz_time_tracking.check_proposal import check, parse_proposal, subtract
from filoz_time_tracking.segment_activity import Block

DAY = "2026-09-17"


def t(hhmmss: str) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{hhmmss}")


def proposal(body: str) -> str:
    return f"# Day proposal: {DAY} (Thursday)\n\nStatus: draft\n\n{body}"


def entry(label: str, span: str, title: str, project: str, billing: str = "billable") -> str:
    return f"### {label} · {span} · {title}\n**{project}** · {billing} · 10m · Confidence: 🟢 High · Entry ID: (filled on apply)\n\nEvidence.\n\n"


FILOZ_CANDIDATE = [Block("F", t("07:22:35"), t("08:46:59"), 0)]


class ParseTest(unittest.TestCase):
    def test_entries_and_billing(self):
        entries, _ = parse_proposal(proposal(
            entry("E1", "07:31–08:00", "Lotus <> Forest", "FilOz ▸ Community Collaboration")
            + entry("M1", "14:37–14:57", "Swag and artwork setup", "Volunteering ▸ Madison Ultimate", "not billable")))
        self.assertEqual([(e.label, e.billable) for e in entries], [("E1", True), ("M1", False)])
        self.assertEqual(entries[0].start, t("07:31:00"))

    def test_entry_ending_at_midnight_ends_next_day(self):
        entries, _ = parse_proposal(proposal(entry("E15", "22:44–00:00", "Solstice project management", "FilOz ▸ Basecamp")))
        self.assertEqual(entries[0].end, datetime.fromisoformat("2026-09-18T00:00"))

    def test_deviations_only_read_from_their_section(self):
        _, deviations = parse_proposal(proposal(
            "## Morning\n\n- 07:00–07:10: a bullet elsewhere\n\n## Boundary deviations\n\n- 14:37–14:41: relabelled to Madison (M1)\n"))
        self.assertEqual([(d.start, d.reason) for d in deviations], [(t("14:37:00"), "relabelled to Madison (M1)")])


class SubtractTest(unittest.TestCase):
    def test_subtract_leaves_edges(self):
        self.assertEqual(subtract([(t("07:00:00"), t("08:00:00"))], [(t("07:10:00"), t("07:50:00"))]),
                         [(t("07:00:00"), t("07:10:00")), (t("07:50:00"), t("08:00:00"))])


class CheckTest(unittest.TestCase):
    def run_check(self, body: str) -> list[str]:
        entries, deviations = parse_proposal(proposal(body))
        return check(entries, deviations, FILOZ_CANDIDATE, min_span=3, tolerance=60)

    def test_trimmed_lead_in_is_undeclared(self):
        # The Sep 17 case: the draft started at 07:31 though the candidate starts at 07:22:35.
        lines = self.run_check(entry("E1", "07:31–08:47", "Lotus <> Forest", "FilOz ▸ Community Collaboration"))
        self.assertEqual(lines, ["UNDECLARED unbilled FilOz 07:22:35-07:31:00 (8.4m, not covered by any entry)"])

    def test_minute_rounding_is_tolerated(self):
        self.assertEqual(self.run_check(entry("E1", "07:23–08:47", "Morning comms", "FilOz ▸ Communication")), [])

    def test_relabel_names_the_covering_entry_and_can_be_declared(self):
        body = (entry("E1", "07:23–08:30", "Morning comms", "FilOz ▸ Communication")
                + entry("M1", "08:30–08:47", "Coach communication", "Volunteering ▸ Madison Ultimate", "not billable"))
        self.assertEqual(self.run_check(body),
                         ["UNDECLARED unbilled FilOz 08:30:00-08:46:59 (17.0m, covered by M1)"])
        declared = self.run_check(body + "## Boundary deviations\n\n- 08:30–08:47: WhatsApp Coaches, relabelled to Madison\n")
        self.assertEqual(declared,
                         ["declared   unbilled FilOz 08:30:00-08:46:59 (17.0m, covered by M1): WhatsApp Coaches, relabelled to Madison"])

    def test_billed_outside_filoz_is_undeclared(self):
        lines = self.run_check(entry("E1", "07:23–09:00", "Morning comms", "FilOz ▸ Communication"))
        self.assertEqual(lines, ["UNDECLARED billed outside FilOz 08:46:59-09:00:00 (13.0m)"])

    def test_short_candidates_need_no_entry(self):
        entries, deviations = parse_proposal(proposal(""))
        short = [Block("F", t("10:00:00"), t("10:03:00"), 0)]
        self.assertEqual(check(entries, deviations, short, min_span=3, tolerance=60), [])

    def test_candidates_over_min_span_need_an_entry(self):
        entries, deviations = parse_proposal(proposal(""))
        over = [Block("F", t("10:00:00"), t("10:03:30"), 0)]
        self.assertEqual(check(entries, deviations, over, min_span=3, tolerance=60),
                         ["UNDECLARED unbilled FilOz 10:00:00-10:03:30 (3.5m, not covered by any entry)"])


if __name__ == "__main__":
    unittest.main()
