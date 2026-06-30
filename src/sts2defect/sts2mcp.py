from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from .models import EnrichedCard
from .recommendations import RecommendationStore


class Sts2McpClientError(RuntimeError):
    """Raised when the read-only STS2MCP API cannot be reached or parsed."""


@dataclass(frozen=True)
class CardRewardCard:
    card_id: str
    name: str
    card_type: str
    cost: str
    rarity: str
    is_upgraded: bool
    index: int


@dataclass(frozen=True)
class CardRewardState:
    state_type: str
    cards: list[CardRewardCard]
    can_skip: bool
    run_act: int | None = None
    run_floor: int | None = None
    run_ascension: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CardRewardState":
        state_type = payload.get("state_type")
        if state_type != "card_reward":
            raise ValueError(f"expected state_type 'card_reward', got {state_type!r}")

        reward = payload.get("card_reward")
        if not isinstance(reward, dict):
            raise ValueError("'card_reward' must be an object")

        raw_cards = reward.get("cards")
        if not isinstance(raw_cards, list):
            raise ValueError("'card_reward.cards' must be a list")

        cards = [_parse_card_reward_card(card) for card in raw_cards]
        run = payload.get("run") if isinstance(payload.get("run"), dict) else {}

        return cls(
            state_type=state_type,
            cards=cards,
            can_skip=bool(reward.get("can_skip")),
            run_act=_optional_int(run, "act"),
            run_floor=_optional_int(run, "floor"),
            run_ascension=_optional_int(run, "ascension"),
        )


class Sts2McpReadOnlyClient:
    def __init__(self, base_url: str = "http://localhost:15526", timeout_seconds: float = 2):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def fetch_singleplayer(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/singleplayer?format=json"
        try:
            with urlopen(url, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except (OSError, URLError) as exc:
            raise Sts2McpClientError(f"failed to read STS2MCP singleplayer state: {exc}") from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise Sts2McpClientError("STS2MCP returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise Sts2McpClientError("STS2MCP singleplayer response must be a JSON object")
        return payload

    def fetch_card_reward(self) -> CardRewardState | None:
        payload = self.fetch_singleplayer()
        if payload.get("state_type") != "card_reward":
            return None
        try:
            return CardRewardState.from_payload(payload)
        except ValueError as exc:
            raise Sts2McpClientError(f"invalid STS2MCP card_reward payload: {exc}") from exc


def enrich_card_reward(
    state: CardRewardState, recommendations: RecommendationStore
) -> list[EnrichedCard]:
    enriched: list[EnrichedCard] = []
    for card in sorted(state.cards, key=lambda item: item.index):
        recommendation = recommendations.lookup(card.card_id) or recommendations.lookup(card.name)
        enriched.append(
            EnrichedCard(
                card_name=card.name,
                recommendation=recommendation,
            )
        )
    return enriched


def format_card_reward_preview(
    state: CardRewardState,
    recommendations: RecommendationStore,
    ascii_only: bool = False,
) -> list[str]:
    floor = f" floor {state.run_floor}" if state.run_floor is not None else ""
    lines = [f"card_reward{floor}: {len(state.cards)} cards"]
    for card in sorted(state.cards, key=lambda item: item.index):
        display_name = card.card_id if ascii_only else card.name
        matches = recommendations.lookup_all(card.card_id) or recommendations.lookup_all(card.name)
        if not matches:
            lines.append(f"{card.index}. {display_name}: no recommendation data")
            continue
        rendered = "; ".join(
            f"{_render_type_name(item.type_name, ascii_only)} {item.recommend_index}"
            for item in matches
        )
        lines.append(f"{card.index}. {display_name}: {rendered}")
    return lines


def _parse_card_reward_card(payload: Any) -> CardRewardCard:
    if not isinstance(payload, dict):
        raise ValueError("card_reward card must be an object")
    return CardRewardCard(
        card_id=_require_string(payload, "id"),
        name=_require_string(payload, "name"),
        card_type=_require_string(payload, "type"),
        cost=str(payload.get("cost", "")),
        rarity=_require_string(payload, "rarity"),
        is_upgraded=bool(payload.get("is_upgraded")),
        index=_require_int(payload, "index"),
    )


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"'{key}' must be a non-empty string")
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"'{key}' must be an integer")
    return value


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"'{key}' must be an integer")
    return value


def _render_type_name(type_name: str, ascii_only: bool) -> str:
    if not ascii_only:
        return type_name
    return _ASCII_TYPE_NAMES.get(type_name, _slugify_ascii(type_name))


def _slugify_ascii(value: str) -> str:
    result = []
    previous_dash = False
    for char in value:
        if char.isascii() and char.isalnum():
            result.append(char.lower())
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True
    return "".join(result).strip("-") or "interface"


_ASCII_TYPE_NAMES = {
    "过牌端口": "draw-interface",
    "费用端口（0 费默认属于此端口）": "cost-interface",
    "伤害端口": "damage-interface",
    "伤害端口（AOE）": "aoe-damage-interface",
    "防御端口（伤害复合型）": "defense-damage-interface",
    "防御端口": "defense-interface",
    "上限端口": "scaling-interface",
    "启动端口（防御端口默认属于此端口）": "startup-interface",
    "稳定端口": "stability-interface",
    "能力接口": "ability-interface",
    "攻击接口": "attack-interface",
}
