import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.recommendations import RecommendationDataError, RecommendationStore


class RecommendationStoreTests(unittest.TestCase):
    def write_json(self, payload):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "recommendations.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    def valid_payload(self):
        return {
            "version": "test-001",
            "source": {"type": "manual", "description": "unit test"},
            "types": [
                {
                    "name": "攻击接口",
                    "cards": [
                        {
                            "name": "Card A",
                            "rank": 1,
                            "total": 2,
                            "recommendIndex": "1/2",
                        },
                        {
                            "name": "Card B",
                            "rank": 2,
                            "total": 2,
                            "recommendIndex": "2/2",
                        },
                    ],
                },
                {
                    "name": "防御接口",
                    "cards": [
                        {
                            "name": "Card C",
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
            ],
        }

    def test_loads_card_recommendation_by_name(self):
        store = RecommendationStore.from_file(self.write_json(self.valid_payload()))

        recommendation = store.lookup("Card B")

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.card_name, "Card B")
        self.assertEqual(recommendation.type_name, "攻击接口")
        self.assertEqual(recommendation.rank, 2)
        self.assertEqual(recommendation.total, 2)
        self.assertEqual(recommendation.recommend_index, "2/2")

    def test_loads_card_recommendation_by_chinese_or_english_alias(self):
        payload = self.valid_payload()
        payload["types"][0]["cards"][0].update(
            {
                "id": "BEAM_CELL",
                "name": "Beam Cell",
                "names": {"eng": "Beam Cell", "zhs": "光束射线"},
                "aliases": ["光束射线+", "Beam Cell+"],
            }
        )
        store = RecommendationStore.from_file(self.write_json(payload))

        english = store.lookup("Beam Cell")
        chinese = store.lookup("光束射线")
        upgraded_chinese = store.lookup("光束射线+")

        self.assertIsNotNone(english)
        self.assertEqual(english, chinese)
        self.assertEqual(english, upgraded_chinese)
        self.assertEqual(english.card_id, "BEAM_CELL")
        self.assertEqual(english.card_name, "Beam Cell")
        self.assertEqual(english.display_name, "光束射线")

    def test_loads_known_card_display_name_without_recommendation_group(self):
        payload = self.valid_payload()
        payload["knownCards"] = [
            {
                "id": "SQUASH",
                "name": "Squash",
                "names": {"eng": "Squash", "zhs": "压扁"},
            }
        ]
        store = RecommendationStore.from_file(self.write_json(payload))

        self.assertEqual(store.card_display_name("SQUASH"), "压扁")
        self.assertEqual(store.lookup_all("SQUASH"), [])
        self.assertEqual(store.known_card_display_names()["压扁"], "SQUASH")

    def test_summarizes_duplicate_cards_without_deduplicating(self):
        store = RecommendationStore.from_file(self.write_json(self.valid_payload()))

        summary = store.summarize_cards(["Card A", "Card A", "Card C", "Unknown"])

        self.assertEqual(summary.total_cards, 4)
        self.assertEqual(summary.unknown_count, 1)
        self.assertEqual(summary.by_type["攻击接口"].count, 2)
        self.assertEqual(summary.by_type["攻击接口"].recommend_indexes, ["1/2", "1/2"])
        self.assertEqual(summary.by_type["防御接口"].count, 1)
        self.assertEqual(summary.by_type["防御接口"].recommend_indexes, ["1/1"])

    def test_rejects_total_that_does_not_match_type_card_count(self):
        payload = self.valid_payload()
        payload["types"][0]["cards"][0]["total"] = 3

        with self.assertRaises(RecommendationDataError):
            RecommendationStore.from_file(self.write_json(payload))

    def test_allows_same_card_in_multiple_interface_types(self):
        payload = {
            "version": "test-duplicate-interface",
            "types": [
                {
                    "name": "过牌端口",
                    "cards": [
                        {
                            "id": "ROCKET_PUNCH",
                            "name": "Rocket Punch",
                            "names": {"eng": "Rocket Punch", "zhs": "火箭飞拳"},
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
                {
                    "name": "伤害端口",
                    "cards": [
                        {
                            "id": "ROCKET_PUNCH",
                            "name": "Rocket Punch",
                            "names": {"eng": "Rocket Punch", "zhs": "火箭飞拳"},
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
            ],
        }

        store = RecommendationStore.from_file(self.write_json(payload))

        recommendations = store.lookup_all("ROCKET_PUNCH")

        self.assertEqual([item.type_name for item in recommendations], ["过牌端口", "伤害端口"])


if __name__ == "__main__":
    unittest.main()
