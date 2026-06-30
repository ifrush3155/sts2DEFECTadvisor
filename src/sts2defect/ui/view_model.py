from __future__ import annotations

from dataclasses import dataclass

from sts2defect.recognition.card_reward import CardRewardRecognitionReport
from sts2defect.recommendations import RecommendationStore
from sts2defect.savefiles import DeckCard, DeckSnapshot
from sts2defect.sts2mcp import CardRewardState


@dataclass(frozen=True)
class RecommendationView:
    type_name: str
    recommend_index: str
    is_upgraded: bool = False


@dataclass(frozen=True)
class CardRewardCardView:
    index: int
    card_id: str
    display_name: str
    metadata: str
    recommendations: list[RecommendationView]
    unknown_message: str | None = None
    is_upgraded: bool = False

    @property
    def is_unknown(self) -> bool:
        return not self.recommendations


@dataclass(frozen=True)
class CardRewardPanelView:
    title: str
    cards: list[CardRewardCardView]
    can_skip: bool
    has_uncertain: bool = False
    uncertain_message: str | None = None


@dataclass(frozen=True)
class DeckStatItemView:
    label: str
    tooltip: str | None = None
    is_upgraded: bool = False


@dataclass(frozen=True)
class DeckInterfaceView:
    type_name: str
    count: int
    items: list[DeckStatItemView]
    show_recommend_indexes: bool = True

    @property
    def recommend_indexes(self) -> list[str]:
        return [item.label for item in self.items]


@dataclass(frozen=True)
class DeckSnapshotPanelView:
    title: str
    summary: str
    source_path: str
    save_time: int | None
    card_count: int
    unknown_count: int
    interfaces: list[DeckInterfaceView]


def build_card_reward_view(
    state: CardRewardState, recommendations: RecommendationStore
) -> CardRewardPanelView:
    title = "card_reward"
    if state.run_floor is not None:
        title = f"{title} floor {state.run_floor}"

    cards: list[CardRewardCardView] = []
    for card in sorted(state.cards, key=lambda item: item.index):
        matches = recommendations.lookup_all(card.card_id) or recommendations.lookup_all(card.name)
        display_name = matches[0].display_name if matches else card.name
        recommendation_views = [
            RecommendationView(
                type_name=item.type_name,
                recommend_index=item.recommend_index,
                is_upgraded=card.is_upgraded,
            )
            for item in matches
        ]
        cards.append(
            CardRewardCardView(
                index=card.index,
                card_id=card.card_id,
                display_name=_display_card_name(display_name, card.is_upgraded),
                metadata=f"{card.card_type} | cost {card.cost} | {card.rarity}",
                recommendations=recommendation_views,
                unknown_message="推荐表未收录" if not recommendation_views else None,
                is_upgraded=card.is_upgraded,
            )
        )

    return CardRewardPanelView(title=title, cards=cards, can_skip=state.can_skip)


def build_visual_card_reward_view(
    report: CardRewardRecognitionReport, recommendations: RecommendationStore
) -> CardRewardPanelView:
    cards: list[CardRewardCardView] = []
    has_uncertain = False

    for match in sorted(report.matches, key=lambda item: item.slot):
        card_id = match.card_id or "UNKNOWN"
        matches = recommendations.lookup_all(card_id) if match.card_id else []
        display_name = _visual_display_name(match, matches, recommendations)
        is_upgraded = _visual_is_upgraded(match)
        recommendation_views = [
            RecommendationView(
                type_name=item.type_name,
                recommend_index=item.recommend_index,
                is_upgraded=is_upgraded,
            )
            for item in matches
        ]
        metadata_parts = [
            f"confidence {match.confidence:.3f}",
            f"score {match.score:.3f}",
            f"margin {match.margin:.3f}",
            f"uncertain {'yes' if match.is_uncertain or match.card_id is None else 'no'}",
        ]
        if match.is_uncertain or match.card_id is None:
            has_uncertain = True
        if match.reason:
            metadata_parts.append(match.reason)

        cards.append(
            CardRewardCardView(
                index=match.slot,
                card_id=card_id,
                display_name=display_name,
                metadata=" | ".join(metadata_parts),
                recommendations=recommendation_views,
                unknown_message=_visual_unknown_message(match, recommendation_views),
                is_upgraded=is_upgraded,
            )
        )

    return CardRewardPanelView(
        title="截图识别 card_reward",
        cards=cards,
        can_skip=False,
        has_uncertain=has_uncertain,
        uncertain_message="请移开鼠标或确认画面为选牌奖励页" if has_uncertain else None,
    )


def build_deck_snapshot_view(
    snapshot: DeckSnapshot, recommendations: RecommendationStore
) -> DeckSnapshotPanelView:
    unknown_items: list[DeckStatItemView] = []
    grouped_items: dict[str, list[tuple[DeckCard, DeckStatItemView]]] = {}

    for card in snapshot.cards:
        matches = recommendations.lookup_all(card.card_id)
        if not matches:
            display_name = recommendations.card_display_name(card.card_id) or card.card_id
            unknown_items.append(
                DeckStatItemView(
                    label=_display_card_name(display_name, card.is_upgraded),
                    tooltip=card.raw_id,
                    is_upgraded=card.is_upgraded,
                )
            )
            continue
        for match in matches:
            grouped_items.setdefault(match.type_name, []).append(
                (
                    card,
                    DeckStatItemView(
                        label=match.recommend_index,
                        tooltip=_display_card_name(match.display_name, card.is_upgraded),
                        is_upgraded=card.is_upgraded,
                    ),
                )
            )

    interfaces: list[DeckInterfaceView] = []
    for type_name, pairs in sorted(
        grouped_items.items(), key=lambda item: _deck_interface_sort_key(item[0])
    ):
        if type_name in _NAME_DISPLAY_GROUPS:
            name_items = [
                DeckStatItemView(
                    label=item.tooltip
                    or _display_card_name(card.card_id, card.is_upgraded),
                    tooltip=card.raw_id,
                    is_upgraded=card.is_upgraded,
                )
                for card, item in sorted(
                    pairs,
                    key=lambda pair: _name_display_sort_key(type_name, pair[0], pair[1]),
                )
            ]
            interfaces.append(
                DeckInterfaceView(
                    type_name=type_name,
                    count=len(name_items),
                    items=name_items,
                    show_recommend_indexes=False,
                )
            )
            continue

        stat_items = [
            item
            for _card, item in sorted(
                pairs,
                key=lambda pair: _recommendation_item_sort_key(pair[1]),
            )
        ]
        interfaces.append(
            DeckInterfaceView(
                type_name=type_name,
                count=len(stat_items),
                items=stat_items,
                show_recommend_indexes=True,
            )
        )

    if unknown_items:
        interfaces.append(
            DeckInterfaceView(
                type_name="unknown",
                count=len(unknown_items),
                items=unknown_items,
                show_recommend_indexes=False,
            )
        )

    hp = "hp ?/?"
    if snapshot.current_hp is not None and snapshot.max_hp is not None:
        hp = f"hp {snapshot.current_hp}/{snapshot.max_hp}"
    gold = f"gold {snapshot.gold}" if snapshot.gold is not None else "gold ?"
    save_time = (
        f"save_time {snapshot.save_time}" if snapshot.save_time is not None else "save_time ?"
    )
    summary = f"{snapshot.card_count} cards | {hp} | {gold} | {save_time}"

    return DeckSnapshotPanelView(
        title=f"牌组统计 | {snapshot.normalized_character_id}",
        summary=summary,
        source_path=str(snapshot.source_path),
        save_time=snapshot.save_time,
        card_count=snapshot.card_count,
        unknown_count=len(unknown_items),
        interfaces=interfaces,
    )


def _deck_interface_sort_key(type_name: str) -> tuple[int, str]:
    priority = {
        "初始牌": 0,
        "诅咒牌": 1,
        "unknown": 2,
    }
    return (priority.get(type_name, 10), type_name)


def _name_display_sort_key(
    type_name: str, card: DeckCard, item: DeckStatItemView
) -> tuple[int, int, str]:
    if type_name == "初始牌":
        order = {
            "DUALCAST": 0,
            "ZAP": 1,
            "STRIKE_DEFECT": 2,
            "DEFEND_DEFECT": 3,
        }
        return (order.get(card.card_id, 99), 0 if card.is_upgraded else 1, item.label)
    return (0, 0 if card.is_upgraded else 1, item.label)


def _recommendation_item_sort_key(item: DeckStatItemView) -> tuple[int, int, str]:
    try:
        rank_text, total_text = item.label.split("/", 1)
        return (int(rank_text), int(total_text), item.tooltip or item.label)
    except ValueError:
        return (9999, 9999, item.tooltip or item.label)


_NAME_DISPLAY_GROUPS = {"初始牌", "诅咒牌"}


def _display_card_name(name: str, is_upgraded: bool) -> str:
    if not is_upgraded:
        return name
    return f"{name.rstrip('+＋')}+"


def _visual_display_name(
    match, matches, recommendations: RecommendationStore
) -> str:
    if match.card_id is None:
        return "UNKNOWN"
    if match.display_name:
        return match.display_name
    if matches:
        return matches[0].display_name
    return (
        recommendations.card_display_name(match.card_id)
        or match.card_id
    )


def _visual_unknown_message(
    match, recommendation_views: list[RecommendationView]
) -> str | None:
    if recommendation_views:
        return None
    if match.card_id is None:
        return "无法可靠识别"
    return "推荐表未收录"


def _visual_is_upgraded(match) -> bool:
    return bool(match.display_name and match.display_name.endswith("+"))
