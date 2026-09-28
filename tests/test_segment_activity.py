"""Tests for segment_activity classification and merging (stdlib unittest)."""
import unittest
from pathlib import Path

from filoz_time_tracking.segment_activity import classify, load_rows, merge, to_blocks

SAMPLE = Path(__file__).resolve().parent.parent / "docs" / "samples" / "activity-slice-sample.txt"
MADISON = "Volunteering ▸ Madison Ultimate"


class ClassifyTest(unittest.TestCase):
    def test_brave_is_filoz(self):
        self.assertEqual(classify("Brave Browser", "github.com", "FilOz ▸ Filecoin Onchain Cloud"), "F")

    def test_brave_localhost_filed_under_madison_is_madison(self):
        self.assertEqual(classify("Brave Browser", "localhost", MADISON), "M")

    def test_brave_localhost_without_madison_project_stays_filoz(self):
        self.assertEqual(classify("Brave Browser", "localhost", "(Unassigned)"), "F")

    def test_madison_project_elsewhere_in_brave_is_not_trusted(self):
        self.assertEqual(classify("Brave Browser", "docs.google.com", MADISON), "F")

    def test_whatsapp_defaults_to_madison(self):
        self.assertEqual(classify("WhatsApp", "(no title)"), "M")

    def test_whatsapp_personal_override(self):
        self.assertEqual(classify("WhatsApp", "(no title)", whatsapp_personal=True), "P")


class SampleTest(unittest.TestCase):
    def candidates(self, **kwargs):
        rows = load_rows(str(SAMPLE), **kwargs)
        return [(e.cls, f"{e.start:%H:%M:%S}", f"{e.end:%H:%M:%S}") for e in merge(to_blocks(rows, 300), 120, 300)]

    def test_sample_segments(self):
        self.assertEqual(self.candidates(), [
            ("M", "08:50:00", "08:56:00"),
            ("F", "08:56:10", "09:36:25"),  # meeting; 1.2m of Messages absorbed
            ("P", "09:36:25", "09:42:30"),  # 6m detour ends the FilOz candidate
            ("F", "09:49:00", "09:51:06"),
            ("M", "09:51:06", "10:05:00"),  # Plannotator on localhost is Madison, not FilOz
        ])


if __name__ == "__main__":
    unittest.main()
