import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.settings import UserSettings, load_settings, save_settings


class UserSettingsTests(unittest.TestCase):
    def test_loads_empty_settings_when_file_does_not_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"

            settings = load_settings(path)

            self.assertIsNone(settings.profile_path)

    def test_saves_and_loads_profile_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"

            save_settings(
                UserSettings(profile_path=Path("C:/Users/example/profile1")),
                path,
            )
            settings = load_settings(path)

            self.assertEqual(settings.profile_path, Path("C:/Users/example/profile1"))


if __name__ == "__main__":
    unittest.main()
