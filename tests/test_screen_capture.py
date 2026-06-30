import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.capture.screenshot import ScreenshotCaptureSource


class ScreenshotCaptureTests(unittest.TestCase):
    def test_captures_full_screen_to_png_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = ScreenshotCaptureSource(
                output_dir=Path(temp_dir),
                grabber=lambda bbox=None: Image.new("RGB", (80, 60), (1, 2, 3)),
            )

            frame = source.capture()

            self.assertTrue(Path(frame.image).exists())
            self.assertEqual(Path(frame.image).suffix, ".png")
            self.assertEqual(frame.window_bounds.x, 0)
            self.assertEqual(frame.window_bounds.y, 0)
            self.assertEqual(frame.window_bounds.width, 80)
            self.assertEqual(frame.window_bounds.height, 60)

    def test_captures_window_bbox_when_title_is_configured(self):
        calls = []

        def grabber(bbox=None):
            calls.append(bbox)
            return Image.new("RGB", (30, 40), (4, 5, 6))

        with tempfile.TemporaryDirectory() as temp_dir:
            source = ScreenshotCaptureSource(
                output_dir=Path(temp_dir),
                window_title="Slay the Spire 2",
                grabber=grabber,
                window_locator=lambda title: (10, 20, 40, 60),
            )

            frame = source.capture()

            self.assertEqual(calls, [(10, 20, 40, 60)])
            self.assertEqual(frame.window_bounds.x, 10)
            self.assertEqual(frame.window_bounds.y, 20)
            self.assertEqual(frame.window_bounds.width, 30)
            self.assertEqual(frame.window_bounds.height, 40)

    def test_can_capture_without_persisting_png_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = ScreenshotCaptureSource(
                output_dir=Path(temp_dir),
                persist=False,
                grabber=lambda bbox=None: Image.new("RGB", (80, 60), (1, 2, 3)),
            )

            frame = source.capture()

            self.assertIsInstance(frame.image, Image.Image)
            self.assertEqual(list(Path(temp_dir).glob("*.png")), [])


if __name__ == "__main__":
    unittest.main()
