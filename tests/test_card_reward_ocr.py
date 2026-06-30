import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.recommendations import RecommendationStore
from sts2defect.recognition.card_reward_ocr import (
    OcrTextLine,
    OcrCardRewardSession,
    best_known_card_match,
    merge_uncertain_matches_with_fallback,
    normalize_ocr_card_name,
    recognize_card_reward_titles_from_ocr_lines,
)
from PIL import Image
from sts2defect.models import Bounds
from sts2defect.recognition.card_reward import CardRewardMatch, CardRewardRecognitionReport


def recommendation_store() -> RecommendationStore:
    return RecommendationStore.from_file(
        ROOT / "data" / "recommendations" / "slay-the-spire-2-manual.json"
    )


class CardRewardOcrTests(unittest.TestCase):
    def test_normalizes_chinese_title_text_and_upgrade_marker(self):
        normalized = normalize_ocr_card_name("（工 合成+")

        self.assertEqual(normalized.text, "工合成")
        self.assertTrue(normalized.is_upgraded)

    def test_fuzzy_matches_known_chinese_card_names(self):
        store = recommendation_store()

        cases = [
            ("烟肉+", "SMOKESTACK", "烟囱", True),
            ("（工合成+", "SYNTHESIS", "人工合成", True),
            ("火箭飞拳", "ROCKET_PUNCH", "火箭飞拳", False),
            ("暴涨", "BULK_UP", "暴涨", False),
        ]

        for text, card_id, display_name, is_upgraded in cases:
            with self.subTest(text=text):
                match = best_known_card_match(text, store)

                self.assertIsNotNone(match)
                assert match is not None
                self.assertEqual(match.card_id, card_id)
                self.assertEqual(match.display_name, display_name)
                self.assertEqual(match.is_upgraded, is_upgraded)
                self.assertFalse(match.is_uncertain)

    def test_builds_report_from_injected_ocr_lines(self):
        store = recommendation_store()
        lines = [
            [OcrTextLine("烟肉+", 0.91)],
            [OcrTextLine("人工合成+", 0.98)],
            [OcrTextLine("火箭飞拳", 0.97)],
            [OcrTextLine("暴涨", 0.96)],
        ]

        report = recognize_card_reward_titles_from_ocr_lines(
            lines,
            store,
            image_label="unit-ocr",
        )

        self.assertEqual(report.method, "ocr")
        self.assertEqual(
            [item.card_id for item in report.matches],
            ["SMOKESTACK", "SYNTHESIS", "ROCKET_PUNCH", "BULK_UP"],
        )
        self.assertEqual([item.display_name for item in report.matches], ["烟囱+", "人工合成+", "火箭飞拳", "暴涨"])
        self.assertTrue(all(not item.is_uncertain for item in report.matches))

    def test_replaces_only_uncertain_ocr_slots_with_fallback(self):
        primary = CardRewardRecognitionReport(
            image_path=Path("unit.png"),
            method="ocr",
            candidates_loaded=4,
            candidates_failed=0,
            matches=[
                _match(0, None, None, True),
                _match(1, "SYNTHESIS", "人工合成+", False),
            ],
            notes=[],
        )
        fallback = CardRewardRecognitionReport(
            image_path=Path("unit.png"),
            method="art-template",
            candidates_loaded=10,
            candidates_failed=0,
            matches=[
                _match(0, "SMOKESTACK", "烟囱+", False),
                _match(1, "CLAW", "爪击", False),
            ],
            notes=[],
        )

        merged = merge_uncertain_matches_with_fallback(primary, fallback)

        self.assertEqual([item.card_id for item in merged.matches], ["SMOKESTACK", "SYNTHESIS"])
        self.assertEqual(merged.method, "ocr+fallback")

    def test_ocr_session_uses_one_engine_call_for_all_title_slots(self):
        engine = FakeCombinedOcrEngine(
            [
                _ocr_item(80, "烟肉+", 0.91),
                _ocr_item(420, "人工合成+", 0.98),
                _ocr_item(800, "火箭飞拳", 0.97),
                _ocr_item(1160, "暴涨", 0.96),
            ]
        )
        session = OcrCardRewardSession(recommendation_store(), engine=engine)

        report = session.recognize_image_object(Image.new("RGB", (1750, 1094), "black"))

        self.assertEqual(engine.calls, 1)
        self.assertEqual(
            [item.card_id for item in report.matches],
            ["SMOKESTACK", "SYNTHESIS", "ROCKET_PUNCH", "BULK_UP"],
        )

def _match(
    slot: int,
    card_id: str | None,
    display_name: str | None,
    is_uncertain: bool,
) -> CardRewardMatch:
    return CardRewardMatch(
        slot=slot,
        card_id=card_id,
        display_name=display_name,
        confidence=0.9 if card_id else 0.0,
        score=0.9 if card_id else 0.0,
        margin=0.1 if card_id else 0.0,
        is_uncertain=is_uncertain,
        bounds=Bounds(x=0, y=0, width=1, height=1),
        alternatives=[],
    )


class FakeCombinedOcrEngine:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def __call__(self, image):
        self.calls += 1
        return self.result


def _ocr_item(center_x: float, text: str, confidence: float):
    return [
        [
            [center_x - 10, 5],
            [center_x + 10, 5],
            [center_x + 10, 20],
            [center_x - 10, 20],
        ],
        text,
        confidence,
    ]


if __name__ == "__main__":
    unittest.main()
