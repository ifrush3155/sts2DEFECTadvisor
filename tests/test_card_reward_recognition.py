import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.recognition.card_reward import (
    CardTemplate,
    RecognitionSession,
    format_card_reward_recognition,
    recognize_card_reward_image,
    save_card_reward_debug_artifacts,
)


class CardRewardRecognitionTests(unittest.TestCase):
    def test_recognizes_three_reward_cards_from_art_templates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            templates = [
                _write_template(base, "ALPHA", "甲", seed=1),
                _write_template(base, "BETA", "乙", seed=2),
                _write_template(base, "GAMMA", "丙", seed=3),
            ]
            image_path = _write_reward_screenshot(base, [1, 2, 3])

            report = recognize_card_reward_image(image_path, templates)

            self.assertEqual([item.card_id for item in report.matches], ["ALPHA", "BETA", "GAMMA"])
            self.assertTrue(all(item.confidence > 0.5 for item in report.matches))
            self.assertTrue(all(not item.is_uncertain for item in report.matches))

    def test_recognizes_four_reward_cards_from_art_templates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            templates = [
                _write_template(base, "ALPHA", "Alpha", seed=1),
                _write_template(base, "BETA", "Beta", seed=2),
                _write_template(base, "GAMMA", "Gamma", seed=3),
                _write_template(base, "DELTA", "Delta", seed=4),
            ]
            image_path = _write_four_reward_screenshot(base, [1, 2, 3, 4])

            report = recognize_card_reward_image(image_path, templates)

            self.assertEqual(
                [item.card_id for item in report.matches],
                ["ALPHA", "BETA", "GAMMA", "DELTA"],
            )
            self.assertTrue(all(item.confidence > 0.5 for item in report.matches))
            self.assertTrue(all(not item.is_uncertain for item in report.matches))

    def test_formats_uncertain_alternatives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            templates = [
                _write_template(base, "ALPHA", "甲", seed=1),
                _write_template(base, "BETA", "乙", seed=1),
            ]
            image_path = _write_reward_screenshot(base, [1, 1, 1])

            report = recognize_card_reward_image(image_path, templates)
            lines = format_card_reward_recognition(report)

            self.assertTrue(any("uncertain" in line for line in lines))
            self.assertTrue(any("alternatives:" in line for line in lines))

    def test_saves_debug_artifacts_for_matches_and_alternatives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            templates = [
                _write_template(base, "ALPHA", "Alpha", seed=1),
                _write_template(base, "BETA", "Beta", seed=2),
                _write_template(base, "GAMMA", "Gamma", seed=3),
            ]
            image_path = _write_reward_screenshot(base, [1, 2, 3])
            report = recognize_card_reward_image(image_path, templates)
            debug_dir = base / "debug"

            manifest_path = save_card_reward_debug_artifacts(
                report,
                templates,
                debug_dir,
            )

            self.assertTrue(manifest_path.exists())
            run_dir = manifest_path.parent
            self.assertTrue((run_dir / "slot-0-crop.png").exists())
            self.assertTrue(any(run_dir.glob("slot-0-match-ALPHA.*")))
            self.assertTrue(any(run_dir.glob("slot-0-alt-1-*.png")))

    def test_session_reuses_preloaded_template_features(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            templates = [
                _write_template(base, "ALPHA", "Alpha", seed=1),
                _write_template(base, "BETA", "Beta", seed=2),
                _write_template(base, "GAMMA", "Gamma", seed=3),
            ]
            image_path = _write_reward_screenshot(base, [1, 2, 3])
            session = RecognitionSession.from_templates(templates)

            for template in templates:
                template.image_path.unlink()
            report = session.recognize_image(image_path)

            self.assertEqual([item.card_id for item in report.matches], ["ALPHA", "BETA", "GAMMA"])

    def test_session_recognizes_in_memory_image_without_image_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            templates = [
                _write_template(base, "ALPHA", "Alpha", seed=1),
                _write_template(base, "BETA", "Beta", seed=2),
                _write_template(base, "GAMMA", "Gamma", seed=3),
            ]
            image_path = _write_reward_screenshot(base, [1, 2, 3])
            image = Image.open(image_path).convert("RGB")
            image_path.unlink()
            session = RecognitionSession.from_templates(templates)

            report = session.recognize_image_object(image, label="screen")

            self.assertEqual([item.card_id for item in report.matches], ["ALPHA", "BETA", "GAMMA"])
            self.assertEqual(str(report.image_path), "screen")

    def test_recognizes_four_reward_cards_when_art_is_right_of_nominal_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            templates = [
                _write_template(base, "ALPHA", "Alpha", seed=1),
                _write_template(base, "BETA", "Beta", seed=2),
                _write_template(base, "GAMMA", "Gamma", seed=3),
                _write_template(base, "DELTA", "Delta", seed=4),
            ]
            image_path = _write_four_reward_screenshot(
                base,
                [1, 2, 3, 4],
                x_offset=40,
            )
            session = RecognitionSession.from_templates(templates)

            report = session.recognize_image(image_path)

            self.assertEqual(
                [item.card_id for item in report.matches],
                ["ALPHA", "BETA", "GAMMA", "DELTA"],
            )


def _write_template(base: Path, card_id: str, name: str, seed: int) -> CardTemplate:
    image = Image.new("RGB", (400, 520), (0, 0, 0))
    image.paste(_pattern(seed, (238, 151)), (82, 143))
    path = base / f"{card_id}.png"
    image.save(path)
    return CardTemplate(card_id=card_id, display_name=name, image_path=path)


def _write_reward_screenshot(base: Path, seeds: list[int]) -> Path:
    image = Image.new("RGB", (1967, 1162), (8, 12, 14))
    boxes = [
        (535, 555, 188, 139),
        (894, 555, 189, 139),
        (1249, 555, 190, 139),
    ]
    for seed, (x, y, width, height) in zip(seeds, boxes):
        image.paste(_pattern(seed, (width, height)), (x, y))
    path = base / "reward.png"
    image.save(path)
    return path


def _write_four_reward_screenshot(
    base: Path,
    seeds: list[int],
    x_offset: int = 0,
    y_offset: int = 0,
) -> Path:
    image = Image.new("RGB", (2559, 1516), (8, 12, 14))
    boxes = [
        (413, 730, 250, 184),
        (872, 730, 250, 184),
        (1331, 730, 250, 184),
        (1790, 730, 250, 184),
    ]
    for seed, (x, y, width, height) in zip(seeds, boxes):
        art = _pattern(seed, (238, 151)).resize((width, height), Image.Resampling.LANCZOS)
        image.paste(art, (x + x_offset, y + y_offset))
    path = base / "four-reward.png"
    image.save(path)
    return path


def _pattern(seed: int, size: tuple[int, int]) -> Image.Image:
    rng = np.random.default_rng(seed)
    width, height = size
    yy, xx = np.mgrid[0:height, 0:width]
    values = (
        np.sin((xx + seed * 13) / (7 + seed))
        + np.cos((yy + seed * 17) / (5 + seed))
        + rng.normal(0, 0.15, (height, width))
    )
    values = ((values - values.min()) / (values.max() - values.min()) * 255).astype(np.uint8)
    rgb = np.dstack(
        [
            values,
            np.roll(values, seed * 7, axis=1),
            np.roll(values, seed * 11, axis=0),
        ]
    )
    return Image.fromarray(rgb, "RGB")


if __name__ == "__main__":
    unittest.main()
