"""Tests use synthetic log lines; they do NOT represent camera measurements."""
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_mmio_traces import read_log, compare, classify


class TestTraceDiff(unittest.TestCase):
    def test_matching_magic_lantern_record(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "MMIO.LOG"
            path.write_text(
                "5.123456  MovRecTask:FF000000:00000000:MMIO : [0xC0E20008] <- 0x00000001\n"
                "5.123460  MovRecTask:FF000004:00000000:MMIO : [0xC0F04A08] -> 0x54000000\n"
                "noise\n", encoding="utf-8"
            )
            writes, stats = read_log(path, writes_only=True)
            self.assertEqual(writes[0xC0E20008], [1])
            self.assertNotIn(0xC0F04A08, writes)
            self.assertEqual(stats["parsed"], 2)
            self.assertEqual(stats["reads"], 1)
            both, _ = read_log(path, writes_only=False)
            self.assertEqual(both[0xC0F04A08], [0x54000000])

    def test_comparison_and_region(self):
        rows = compare(
            {0xC0E20008: [1, 1], 0xC0F04A08: [0x100]},
            {0xC0E20008: [1, 2], 0xC0F04A08: [0x100]},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["address"], "0xC0E20008")
        self.assertTrue(classify(0xC0E20008).startswith("JPCORE"))
        self.assertTrue(classify(0xC0F04A08).startswith("EDMAC"))

    def test_unobserved_is_not_a_capability_proof(self):
        rows = compare({}, {})
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
