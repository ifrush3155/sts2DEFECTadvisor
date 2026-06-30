import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication, QScrollArea

from sts2defect.recommendations import RecommendationStore
from sts2defect.settings import UserSettings
from sts2defect.ui.panel import (
    DeckStatsPage,
    _default_card_cache_dir,
    _panel_minimum_size,
    _templates_from_existing_cache,
    _window_icon_path,
)


class UiPanelTests(unittest.TestCase):
    def test_window_icon_asset_exists(self):
        self.assertTrue(_window_icon_path().is_file())

    def test_window_icon_has_transparent_background_and_large_avatar(self):
        image = Image.open(_window_icon_path()).convert("RGBA")
        self.assertGreaterEqual(image.width, 128)
        self.assertGreaterEqual(image.height, 128)
        self.assertEqual(
            [
                image.getpixel(point)[3]
                for point in [
                    (0, 0),
                    (image.width - 1, 0),
                    (0, image.height - 1),
                    (image.width - 1, image.height - 1),
                ]
            ],
            [0, 0, 0, 0],
        )
        bbox = image.getbbox()
        self.assertIsNotNone(bbox)
        assert bbox is not None
        self.assertGreaterEqual(bbox[2] - bbox[0], round(image.width * 0.82))
        self.assertGreaterEqual(bbox[3] - bbox[1], round(image.height * 0.82))

    def test_panel_minimum_size_allows_more_flexible_resizing(self):
        self.assertLessEqual(_panel_minimum_size().width(), 360)
        self.assertLessEqual(_panel_minimum_size().height(), 140)

    def test_panel_uses_inline_details_instead_of_native_tooltips(self):
        panel_source = (SRC / "sts2defect" / "ui" / "panel.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("RecommendationDetailLabel", panel_source)
        self.assertIn("推荐详情", panel_source)
        self.assertNotIn("setToolTip", panel_source)

    def test_scroll_areas_hide_horizontal_scrollbars(self):
        panel_source = (SRC / "sts2defect" / "ui" / "panel.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("ScrollBarAlwaysOff", panel_source)

    def test_deck_stats_list_receives_extra_vertical_space(self):
        app = QApplication.instance() or QApplication(sys.argv[:1])
        page = DeckStatsPage(
            RecommendationStore.from_file(
                ROOT / "data" / "recommendations" / "slay-the-spire-2-manual.json"
            ),
            UserSettings(profile_path=ROOT / "tests" / "fixtures" / "profile1"),
        )
        page.refresh()
        page.resize(560, 900)
        page.show()
        app.processEvents()

        scroll = page.findChild(QScrollArea)
        self.assertIsNotNone(scroll)
        assert scroll is not None
        self.assertGreater(scroll.geometry().height(), 500)

        page.resize(300, 220)
        app.processEvents()
        self.assertGreater(scroll.geometry().height(), 0)

    def test_prefers_existing_project_card_template_cache(self):
        project_cache = ROOT / "data" / "samples" / "card-reward" / "debug-cache"
        expected = (
            project_cache
            if project_cache.is_dir()
            else Path.home() / ".cache" / "sts2defect" / "card-images" / "defect"
        )

        self.assertEqual(_default_card_cache_dir(), expected)

    def test_builds_templates_from_existing_cache_without_network_metadata(self):
        recommendations = RecommendationStore.from_dict(
            {
                "version": "test-cache",
                "knownCards": [
                    {
                        "id": "COMPACT",
                        "name": "Compact",
                        "names": {"zhs": "压缩"},
                    }
                ],
                "types": [
                    {
                        "name": "test",
                        "cards": [
                            {
                                "id": "COMPACT",
                                "name": "Compact",
                                "names": {"zhs": "压缩"},
                                "rank": 1,
                                "total": 1,
                                "recommendIndex": "1/1",
                            }
                        ],
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            (cache_dir / "COMPACT.png").write_bytes(b"not opened by this helper")
            (cache_dir / "notes.txt").write_text("ignored", encoding="utf-8")

            templates = _templates_from_existing_cache(cache_dir, recommendations)

            by_id = {template.card_id: template for template in templates}
            self.assertEqual(list(by_id), ["COMPACT"])
            self.assertEqual(by_id["COMPACT"].display_name, "压缩")
            self.assertTrue(by_id["COMPACT"].image_path.is_file())


if __name__ == "__main__":
    unittest.main()
