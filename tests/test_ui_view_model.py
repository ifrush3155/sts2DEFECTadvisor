import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PROFILE = ROOT / "tests" / "fixtures" / "profile1"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sts2defect.models import Bounds
from sts2defect.recommendations import RecommendationStore
from sts2defect.recognition.card_reward import (
    CardMatchAlternative,
    CardRewardMatch,
    CardRewardRecognitionReport,
)
from sts2defect.savefiles import load_deck_snapshot
from sts2defect.sts2mcp import CardRewardCard, CardRewardState
from sts2defect.ui.view_model import (
    build_card_reward_view,
    build_deck_snapshot_view,
    build_visual_card_reward_view,
)


def recommendation_store() -> RecommendationStore:
    return RecommendationStore.from_dict(
        {
            "version": "test-ui",
            "types": [
                {
                    "name": "ability-interface",
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
                    "name": "scaling-interface",
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
            ],
        }
    )


def formal_recommendation_store() -> RecommendationStore:
    return RecommendationStore.from_file(
        ROOT / "data" / "recommendations" / "slay-the-spire-2-manual.json"
    )


def _visual_report(matches: list[CardRewardMatch]) -> CardRewardRecognitionReport:
    return CardRewardRecognitionReport(
        image_path=ROOT / "data" / "samples" / "card-reward" / "unit.png",
        method="art-template",
        candidates_loaded=10,
        candidates_failed=0,
        matches=matches,
        notes=[],
    )


def _visual_match(
    *,
    slot: int,
    card_id: str | None,
    display_name: str | None,
    confidence: float,
    score: float,
    margin: float,
    is_uncertain: bool,
    reason: str | None = None,
) -> CardRewardMatch:
    return CardRewardMatch(
        slot=slot,
        card_id=card_id,
        display_name=display_name,
        confidence=confidence,
        score=score,
        margin=margin,
        is_uncertain=is_uncertain,
        bounds=Bounds(x=1, y=2, width=3, height=4),
        alternatives=[
            CardMatchAlternative(card_id="CLAW", display_name="爪击", score=0.31)
        ],
        reason=reason,
    )


class UiViewModelTests(unittest.TestCase):
    def test_builds_all_recommendations_for_known_reward_card(self):
        state = CardRewardState(
            state_type="card_reward",
            cards=[
                CardRewardCard(
                    card_id="STORM",
                    name="雷暴",
                    card_type="Power",
                    cost="1",
                    rarity="Uncommon",
                    is_upgraded=False,
                    index=0,
                )
            ],
            can_skip=True,
            run_floor=5,
        )

        view = build_card_reward_view(state, recommendation_store())

        self.assertEqual(view.title, "card_reward floor 5")
        self.assertEqual(view.cards[0].display_name, "雷暴")
        self.assertFalse(view.cards[0].is_unknown)
        self.assertEqual(
            [(item.type_name, item.recommend_index) for item in view.cards[0].recommendations],
            [("ability-interface", "1/1"), ("scaling-interface", "1/1")],
        )

    def test_marks_reward_card_without_recommendations_as_unknown(self):
        state = CardRewardState(
            state_type="card_reward",
            cards=[
                CardRewardCard(
                    card_id="NEW_EVENT_CARD",
                    name="新事件牌",
                    card_type="Skill",
                    cost="0",
                    rarity="Special",
                    is_upgraded=True,
                    index=2,
                )
            ],
            can_skip=False,
        )

        view = build_card_reward_view(state, recommendation_store())

        self.assertEqual(view.cards[0].card_id, "NEW_EVENT_CARD")
        self.assertEqual(view.cards[0].display_name, "新事件牌+")
        self.assertEqual(view.cards[0].metadata, "Skill | cost 0 | Special")
        self.assertTrue(view.cards[0].is_unknown)
        self.assertEqual(view.cards[0].unknown_message, "推荐表未收录")

    def test_does_not_duplicate_upgrade_marker_from_mcp_card_name(self):
        state = CardRewardState(
            state_type="card_reward",
            cards=[
                CardRewardCard(
                    card_id="BEGONE",
                    name="下去！+",
                    card_type="Skill",
                    cost="1",
                    rarity="Common",
                    is_upgraded=True,
                    index=0,
                )
            ],
            can_skip=False,
        )

        view = build_card_reward_view(state, recommendation_store())

        self.assertEqual(view.cards[0].display_name, "下去！+")
        self.assertTrue(view.cards[0].is_upgraded)

    def test_builds_visual_reward_view_with_recommendations_and_confidence(self):
        report = _visual_report(
            [
                _visual_match(
                    slot=0,
                    card_id="STORM",
                    display_name="雷暴",
                    confidence=0.82,
                    score=0.72,
                    margin=0.05,
                    is_uncertain=False,
                )
            ]
        )

        view = build_visual_card_reward_view(report, recommendation_store())

        self.assertEqual(view.title, "截图识别 card_reward")
        self.assertFalse(view.can_skip)
        self.assertFalse(view.has_uncertain)
        self.assertIsNone(view.uncertain_message)
        self.assertEqual(view.cards[0].index, 0)
        self.assertEqual(view.cards[0].display_name, "雷暴")
        self.assertEqual(view.cards[0].card_id, "STORM")
        self.assertIn("confidence 0.820", view.cards[0].metadata)
        self.assertIn("score 0.720", view.cards[0].metadata)
        self.assertIn("margin 0.050", view.cards[0].metadata)
        self.assertFalse(view.cards[0].is_unknown)
        self.assertEqual(
            [(item.type_name, item.recommend_index) for item in view.cards[0].recommendations],
            [("ability-interface", "1/1"), ("scaling-interface", "1/1")],
        )

    def test_builds_visual_reward_view_with_upgraded_style_state(self):
        report = _visual_report(
            [
                _visual_match(
                    slot=0,
                    card_id="STORM",
                    display_name="雷暴+",
                    confidence=0.96,
                    score=1.0,
                    margin=1.0,
                    is_uncertain=False,
                )
            ]
        )

        view = build_visual_card_reward_view(report, recommendation_store())

        self.assertEqual(view.cards[0].display_name, "雷暴+")
        self.assertTrue(view.cards[0].is_upgraded)
        self.assertEqual(
            [item.is_upgraded for item in view.cards[0].recommendations],
            [True, True],
        )

    def test_builds_visual_reward_view_with_uncertain_warning(self):
        report = _visual_report(
            [
                _visual_match(
                    slot=1,
                    card_id="STORM",
                    display_name="雷暴",
                    confidence=0.41,
                    score=0.38,
                    margin=0.01,
                    is_uncertain=True,
                    reason="low margin 0.010; inspect alternatives",
                )
            ]
        )

        view = build_visual_card_reward_view(report, recommendation_store())

        self.assertTrue(view.has_uncertain)
        self.assertEqual(view.uncertain_message, "请移开鼠标或确认画面为选牌奖励页")
        self.assertIn("uncertain", view.cards[0].metadata)
        self.assertIn("low margin", view.cards[0].metadata)

    def test_builds_visual_reward_view_for_unknown_match(self):
        report = _visual_report(
            [
                _visual_match(
                    slot=2,
                    card_id=None,
                    display_name=None,
                    confidence=0.0,
                    score=0.0,
                    margin=0.0,
                    is_uncertain=True,
                    reason="no card templates were loaded",
                )
            ]
        )

        view = build_visual_card_reward_view(report, recommendation_store())

        self.assertEqual(view.cards[0].card_id, "UNKNOWN")
        self.assertEqual(view.cards[0].display_name, "UNKNOWN")
        self.assertTrue(view.cards[0].is_unknown)
        self.assertEqual(view.cards[0].unknown_message, "无法可靠识别")

    def test_builds_deck_snapshot_stats_for_panel(self):
        snapshot = load_deck_snapshot(SAMPLE_PROFILE / "saves" / "current_run.save")

        view = build_deck_snapshot_view(snapshot, formal_recommendation_store())

        self.assertEqual(view.title, "牌组统计 | DEFECT")
        self.assertEqual(view.card_count, 23)
        self.assertEqual(view.unknown_count, 1)
        self.assertIn("23 cards", view.summary)
        self.assertIn("hp 6/75", view.summary)
        groups = {item.type_name: item for item in view.interfaces}

        starter = groups["初始牌"]
        self.assertFalse(starter.show_recommend_indexes)
        self.assertEqual(starter.count, 6)
        self.assertEqual(
            [item.label for item in starter.items],
            ["双重释放+", "电击+", "打击", "防御+", "防御", "防御"],
        )
        self.assertEqual(
            [item.is_upgraded for item in starter.items],
            [True, True, False, True, False, False],
        )

        curse = groups["诅咒牌"]
        self.assertFalse(curse.show_recommend_indexes)
        self.assertEqual([item.label for item in curse.items], ["进阶之灾"])

        draw = groups["过牌端口"]
        self.assertTrue(draw.show_recommend_indexes)
        self.assertEqual(
            [(item.label, item.tooltip, item.is_upgraded) for item in draw.items],
            [("2/6", "快速检索+", True), ("3/6", "编译冲击", False), ("4/6", "火箭飞拳+", True)],
        )

        damage = groups["伤害端口"]
        self.assertEqual(
            [(item.label, item.tooltip, item.is_upgraded) for item in damage.items],
            [("1/10", "火箭飞拳+", True), ("8/10", "骚动", False)],
        )

        unknown = groups["unknown"]
        self.assertFalse(unknown.show_recommend_indexes)
        self.assertEqual([item.label for item in unknown.items], ["压扁"])


if __name__ == "__main__":
    unittest.main()
