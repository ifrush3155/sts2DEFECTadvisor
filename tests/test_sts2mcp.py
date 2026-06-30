import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.recommendations import RecommendationStore
from sts2defect.sts2mcp import (
    CardRewardCard,
    CardRewardState,
    enrich_card_reward,
    format_card_reward_preview,
)


CARD_REWARD_PAYLOAD = {
    "state_type": "card_reward",
    "card_reward": {
        "cards": [
            {
                "id": "STORM",
                "name": "雷暴",
                "type": "Power",
                "cost": "1",
                "rarity": "Uncommon",
                "is_upgraded": False,
                "index": 0,
            },
            {
                "id": "CLAW",
                "name": "爪击",
                "type": "Attack",
                "cost": "0",
                "rarity": "Common",
                "is_upgraded": False,
                "index": 1,
            },
            {
                "id": "SYNTHESIS",
                "name": "人工合成",
                "type": "Attack",
                "cost": "2",
                "rarity": "Uncommon",
                "is_upgraded": False,
                "index": 2,
            },
        ],
        "can_skip": True,
    },
    "run": {"act": 1, "floor": 5, "ascension": 10},
}


def recommendation_store() -> RecommendationStore:
    return RecommendationStore.from_dict(
        {
            "version": "test-sts2mcp",
            "types": [
                {
                    "name": "能力接口",
                    "cards": [
                        {
                            "id": "STORM",
                            "name": "Storm",
                            "names": {"eng": "Storm", "zhs": "雷暴"},
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
                {
                    "name": "上限端口",
                    "cards": [
                        {
                            "id": "STORM",
                            "name": "Storm",
                            "names": {"eng": "Storm", "zhs": "雷暴"},
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
                {
                    "name": "攻击接口",
                    "cards": [
                        {
                            "id": "SYNTHESIS",
                            "name": "Synthesis",
                            "names": {"eng": "Synthesis", "zhs": "人工合成"},
                            "rank": 1,
                            "total": 1,
                            "recommendIndex": "1/1",
                        }
                    ],
                },
            ],
        }
    )


class Sts2McpCardRewardTests(unittest.TestCase):
    def test_parses_card_reward_payload(self):
        state = CardRewardState.from_payload(CARD_REWARD_PAYLOAD)

        self.assertEqual(state.state_type, "card_reward")
        self.assertTrue(state.can_skip)
        self.assertEqual(state.run_floor, 5)
        self.assertEqual(
            state.cards[0],
            CardRewardCard(
                card_id="STORM",
                name="雷暴",
                card_type="Power",
                cost="1",
                rarity="Uncommon",
                is_upgraded=False,
                index=0,
            ),
        )

    def test_rejects_non_card_reward_payload(self):
        with self.assertRaises(ValueError):
            CardRewardState.from_payload({"state_type": "map", "map": {}})

    def test_enriches_reward_cards_with_recommendations_by_id(self):
        state = CardRewardState.from_payload(CARD_REWARD_PAYLOAD)

        enriched = enrich_card_reward(state, recommendation_store())

        self.assertEqual(len(enriched), 3)
        self.assertEqual(enriched[0].card_name, "雷暴")
        self.assertEqual(enriched[0].recommendation.card_id, "STORM")
        self.assertEqual(enriched[0].recommendation.type_name, "能力接口")
        self.assertEqual(enriched[0].recommendation.recommend_index, "1/1")
        self.assertIsNone(enriched[1].recommendation)
        self.assertEqual(enriched[2].recommendation.card_id, "SYNTHESIS")

    def test_formats_all_matching_recommendations(self):
        state = CardRewardState.from_payload(CARD_REWARD_PAYLOAD)

        lines = format_card_reward_preview(state, recommendation_store())

        self.assertIn("card_reward floor 5: 3 cards", lines)
        self.assertIn("0. 雷暴: 能力接口 1/1; 上限端口 1/1", lines)
        self.assertIn("1. 爪击: no recommendation data", lines)

    def test_formats_ascii_when_console_cannot_display_chinese(self):
        state = CardRewardState.from_payload(CARD_REWARD_PAYLOAD)

        lines = format_card_reward_preview(state, recommendation_store(), ascii_only=True)

        self.assertIn("0. STORM: ability-interface 1/1; scaling-interface 1/1", lines)


if __name__ == "__main__":
    unittest.main()
