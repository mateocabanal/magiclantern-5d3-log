"""Camera-free tests of ROM preflight; synthetic data only."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "5d3_lab.py"
spec = importlib.util.spec_from_file_location("lab5d3", SCRIPT)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class RomPreflightTests(unittest.TestCase):
    def test_refuses_missing_and_wrong_size_roms(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            valid, paths = lab.check_roms(root, "113")
            self.assertFalse(valid)
            self.assertEqual([p.name for p in paths], ["ROM0.BIN", "ROM1.BIN"])

            (root / "5D3").mkdir()
            with paths[0].open("wb") as f:
                f.truncate(8 * 1024 * 1024)
            valid, _ = lab.check_roms(root, "113")
            self.assertFalse(valid)

            with paths[1].open("wb") as f:
                f.truncate(16 * 1024 * 1024)
            valid, _ = lab.check_roms(root, "113")
            self.assertTrue(valid)

            with paths[1].open("r+b") as f:
                f.truncate(16 * 1024 * 1024 - 1)
            valid, _ = lab.check_roms(root, "113")
            self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
