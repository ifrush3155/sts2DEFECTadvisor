from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import CardRecommendation, LibrarySummary, TypeSummary


class RecommendationDataError(ValueError):
    """Raised when recommendation data is malformed or inconsistent."""


class RecommendationStore:
    def __init__(
        self,
        version: str,
        recommendations: dict[str, list[CardRecommendation]],
        card_display_names: dict[str, str] | None = None,
    ):
        self.version = version
        self._recommendations = recommendations
        self._card_display_names = card_display_names or {}

    @classmethod
    def from_file(cls, path: str | Path) -> "RecommendationStore":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RecommendationStore":
        version = _require_string(payload, "version")
        types = payload.get("types")
        if not isinstance(types, list) or not types:
            raise RecommendationDataError("'types' must be a non-empty list")

        recommendations: dict[str, list[CardRecommendation]] = {}
        card_display_names: dict[str, str] = {}
        for card in _optional_cards(payload, "knownCards"):
            card_id = _require_string(card, "id")
            display_name = _card_display_name(card, _require_string(card, "name"))
            for alias in _card_aliases(card):
                card_display_names[alias] = display_name

        for type_entry in types:
            type_name = _require_string(type_entry, "name")
            cards = type_entry.get("cards")
            if not isinstance(cards, list) or not cards:
                raise RecommendationDataError(f"type '{type_name}' must contain cards")

            expected_total = len(cards)
            seen_ranks: set[int] = set()
            for card in cards:
                card_name = _require_string(card, "name")
                card_id = _optional_string(card, "id") or card_name
                rank = _require_int(card, "rank")
                total = _require_int(card, "total")
                recommend_index = _require_string(card, "recommendIndex")

                if total != expected_total:
                    raise RecommendationDataError(
                        f"card '{card_name}' total {total} does not match "
                        f"type '{type_name}' card count {expected_total}"
                    )
                if rank < 1 or rank > expected_total:
                    raise RecommendationDataError(
                        f"card '{card_name}' rank {rank} is outside 1..{expected_total}"
                    )
                if rank in seen_ranks:
                    raise RecommendationDataError(
                        f"type '{type_name}' contains duplicate rank {rank}"
                    )
                seen_ranks.add(rank)
                if recommend_index != f"{rank}/{total}":
                    raise RecommendationDataError(
                        f"card '{card_name}' recommendIndex must be '{rank}/{total}'"
                    )
                recommendation = CardRecommendation(
                    card_id=card_id,
                    card_name=card_name,
                    display_name=_card_display_name(card, card_name),
                    type_name=type_name,
                    rank=rank,
                    total=total,
                    recommend_index=recommend_index,
                )
                for alias in _card_aliases(card):
                    recommendations.setdefault(alias, []).append(recommendation)
                    card_display_names.setdefault(alias, recommendation.display_name)

            if seen_ranks != set(range(1, expected_total + 1)):
                raise RecommendationDataError(
                    f"type '{type_name}' ranks must be continuous from 1 to {expected_total}"
                )

        return cls(
            version=version,
            recommendations=recommendations,
            card_display_names=card_display_names,
        )

    def lookup(self, card_name: str) -> CardRecommendation | None:
        recommendations = self.lookup_all(card_name)
        if not recommendations:
            return None
        return recommendations[0]

    def lookup_all(self, card_name: str) -> list[CardRecommendation]:
        return list(self._recommendations.get(card_name, []))

    def card_display_name(self, card_name: str) -> str | None:
        return self._card_display_names.get(card_name)

    def known_card_display_names(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for alias, display_name in self._card_display_names.items():
            if alias.isascii() and alias.upper() == alias:
                result[display_name] = alias
        return result

    def summarize_cards(self, card_names: Iterable[str]) -> LibrarySummary:
        total_cards = 0
        unknown_count = 0
        grouped: dict[str, list[str]] = {}

        for card_name in card_names:
            total_cards += 1
            recommendation = self.lookup(card_name)
            if recommendation is None:
                unknown_count += 1
                continue
            grouped.setdefault(recommendation.type_name, []).append(
                recommendation.recommend_index
            )

        by_type = {
            type_name: TypeSummary(count=len(indexes), recommend_indexes=indexes)
            for type_name, indexes in grouped.items()
        }
        return LibrarySummary(
            total_cards=total_cards,
            unknown_count=unknown_count,
            by_type=by_type,
        )


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RecommendationDataError(f"'{key}' must be a non-empty string")
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RecommendationDataError(f"'{key}' must be a non-empty string")
    return value


def _optional_cards(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise RecommendationDataError(f"'{key}' must be a list")
    for item in value:
        if not isinstance(item, dict):
            raise RecommendationDataError(f"'{key}' entries must be objects")
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise RecommendationDataError(f"'{key}' must be an integer")
    return value


def _card_aliases(card: dict[str, Any]) -> list[str]:
    aliases: list[str] = [_require_string(card, "name")]

    card_id = _optional_string(card, "id")
    if card_id is not None:
        aliases.append(card_id)

    names = card.get("names")
    if names is not None:
        if not isinstance(names, dict):
            raise RecommendationDataError("'names' must be an object")
        for value in names.values():
            if not isinstance(value, str) or not value:
                raise RecommendationDataError("'names' values must be non-empty strings")
            aliases.append(value)

    explicit_aliases = card.get("aliases")
    if explicit_aliases is not None:
        if not isinstance(explicit_aliases, list):
            raise RecommendationDataError("'aliases' must be a list")
        for value in explicit_aliases:
            if not isinstance(value, str) or not value:
                raise RecommendationDataError("'aliases' values must be non-empty strings")
            aliases.append(value)

    return list(dict.fromkeys(aliases))


def _card_display_name(card: dict[str, Any], fallback: str) -> str:
    names = card.get("names")
    if names is None:
        return fallback
    if not isinstance(names, dict):
        raise RecommendationDataError("'names' must be an object")

    for key in ("zhs", "zh", "cn", "eng"):
        value = names.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise RecommendationDataError("'names' values must be non-empty strings")
            return value
    return fallback
