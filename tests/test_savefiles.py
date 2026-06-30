import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.savefiles import (
    SaveFileError,
    format_deck_snapshot_preview,
    find_current_run_save,
    load_deck_snapshot,
    normalize_game_card_id,
)


SAMPLE_PROFILE = ROOT / "tests" / "fixtures" / "profile1"


class SaveFileTests(unittest.TestCase):
    def test_normalizes_game_card_id_for_recommendation_lookup(self):
        self.assertEqual(normalize_game_card_id("CARD.ICE_LANCE"), "ICE_LANCE")
        self.assertEqual(normalize_game_card_id("ICE_LANCE"), "ICE_LANCE")

    def test_finds_current_run_save_under_profile_saves_directory(self):
        path = find_current_run_save(SAMPLE_PROFILE)

        self.assertEqual(path, SAMPLE_PROFILE / "saves" / "current_run.save")

    def test_loads_deck_snapshot_from_current_run_save(self):
        snapshot = load_deck_snapshot(SAMPLE_PROFILE / "saves" / "current_run.save")

        self.assertEqual(snapshot.character_id, "CHARACTER.DEFECT")
        self.assertEqual(snapshot.normalized_character_id, "DEFECT")
        self.assertEqual(snapshot.current_hp, 6)
        self.assertEqual(snapshot.max_hp, 75)
        self.assertEqual(snapshot.gold, 184)
        self.assertEqual(snapshot.card_count, 23)
        self.assertEqual(snapshot.cards[0].raw_id, "CARD.STRIKE_DEFECT")
        self.assertEqual(snapshot.cards[0].card_id, "STRIKE_DEFECT")
        self.assertFalse(snapshot.cards[0].is_upgraded)
        self.assertEqual(snapshot.cards[3].card_id, "DEFEND_DEFECT")
        self.assertTrue(snapshot.cards[3].is_upgraded)
        self.assertEqual(snapshot.cards[16].card_id, "SQUASH")

    def test_rejects_profile_without_current_run_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(SaveFileError):
                find_current_run_save(Path(temp_dir))

    def test_formats_deck_snapshot_with_all_matching_interfaces(self):
        snapshot = load_deck_snapshot(SAMPLE_PROFILE / "saves" / "current_run.save")

        lines = format_deck_snapshot_preview(
            snapshot,
            _recommendation_store_for_preview(),
        )

        self.assertIn("deck snapshot DEFECT: 23 cards", lines)
        self.assertIn("hp 6/75 gold 184", lines)
        self.assertIn("unknown cards: 22", lines)
        self.assertIn("draw-interface: 1 card(s), 1/1", lines)
        self.assertIn("startup-interface: 1 card(s), 1/1", lines)

    def test_starter_cards_are_not_unknown_with_formal_recommendations(self):
        snapshot = load_deck_snapshot(SAMPLE_PROFILE / "saves" / "current_run.save")

        lines = format_deck_snapshot_preview(
            snapshot,
            _formal_recommendation_store(),
        )

        self.assertIn("unknown cards: 1", lines)
        self.assertIn("初始牌: 6 card(s), 1/4, 2/4, 2/4, 2/4, 3/4, 4/4", lines)
        self.assertIn("伤害端口: 2 card(s), 1/10, 8/10", lines)
        self.assertIn("诅咒牌: 1 card(s), 1/1", lines)


def _recommendation_store_for_preview():
    from sts2defect.recommendations import RecommendationStore

    return RecommendationStore.from_dict(
        {
            "version": "test-deck-preview",
            "types": [
                {
                    "name": "draw-interface",
                    "cards": [
                        {
                            "id": "SKIM",
                            "name": "Skim",
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
                {
                    "name": "startup-interface",
                    "cards": [
                        {
                            "id": "SKIM",
                            "name": "Skim",
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
            ],
        }
    )


def _formal_recommendation_store():
    from sts2defect.recommendations import RecommendationStore

    return RecommendationStore.from_file(
        ROOT / "data" / "recommendations" / "slay-the-spire-2-manual.json"
    )


if __name__ == "__main__":
    unittest.main()
