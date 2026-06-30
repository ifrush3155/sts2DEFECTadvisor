from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts2defect.recommendations import RecommendationStore


class SaveFileError(ValueError):
    """Raised when an STS2 save/profile cannot be read as a deck snapshot."""


@dataclass(frozen=True)
class DeckCard:
    raw_id: str
    card_id: str
    floor_added: int | None
    upgrade_level: int

    @property
    def is_upgraded(self) -> bool:
        return self.upgrade_level > 0


@dataclass(frozen=True)
class DeckSnapshot:
    source_path: Path
    save_time: int | None
    character_id: str
    current_hp: int | None
    max_hp: int | None
    gold: int | None
    cards: list[DeckCard]

    @property
    def normalized_character_id(self) -> str:
        return _strip_prefix(self.character_id, "CHARACTER.")

    @property
    def card_count(self) -> int:
        return len(self.cards)

    @property
    def card_ids(self) -> list[str]:
        return [card.card_id for card in self.cards]


def find_current_run_save(profile_path: str | Path) -> Path:
    path = Path(profile_path)
    candidates = [
        path / "saves" / "current_run.save",
        path / "current_run.save",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SaveFileError(f"current_run.save not found under profile path: {path}")


def load_deck_snapshot(save_path: str | Path) -> DeckSnapshot:
    path = Path(save_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SaveFileError(f"failed to read save file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SaveFileError(f"save file is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise SaveFileError("save file root must be a JSON object")

    players = payload.get("players")
    if not isinstance(players, list) or not players:
        raise SaveFileError("save file does not contain players")

    player = players[0]
    if not isinstance(player, dict):
        raise SaveFileError("first player must be an object")

    deck = player.get("deck")
    if not isinstance(deck, list):
        raise SaveFileError("first player does not contain a deck list")

    return DeckSnapshot(
        source_path=path,
        save_time=_optional_int(payload, "save_time"),
        character_id=_require_string(player, "character_id"),
        current_hp=_optional_int(player, "current_hp"),
        max_hp=_optional_int(player, "max_hp"),
        gold=_optional_int(player, "gold"),
        cards=[_parse_deck_card(card) for card in deck],
    )


def load_profile_deck_snapshot(profile_path: str | Path) -> DeckSnapshot:
    return load_deck_snapshot(find_current_run_save(profile_path))


def normalize_game_card_id(card_id: str) -> str:
    return _strip_prefix(card_id, "CARD.")


def format_deck_snapshot_preview(
    snapshot: DeckSnapshot, recommendations: RecommendationStore
) -> list[str]:
    hp = "hp ?/?"
    if snapshot.current_hp is not None and snapshot.max_hp is not None:
        hp = f"hp {snapshot.current_hp}/{snapshot.max_hp}"
    gold = f"gold {snapshot.gold}" if snapshot.gold is not None else "gold ?"

    lines = [
        f"deck snapshot {snapshot.normalized_character_id}: {snapshot.card_count} cards",
        f"{hp} {gold}",
        f"source: {snapshot.source_path}",
    ]
    if snapshot.save_time is not None:
        lines.append(f"save_time: {snapshot.save_time}")

    unknown_count = 0
    grouped_indexes: dict[str, list[str]] = {}
    for card in snapshot.cards:
        matches = recommendations.lookup_all(card.card_id)
        if not matches:
            unknown_count += 1
            continue
        for match in matches:
            grouped_indexes.setdefault(match.type_name, []).append(match.recommend_index)

    lines.append(f"unknown cards: {unknown_count}")
    if grouped_indexes:
        lines.append("interfaces:")
        for type_name in sorted(grouped_indexes):
            indexes = sorted(grouped_indexes[type_name], key=_recommend_index_sort_key)
            rendered_indexes = ", ".join(indexes)
            lines.append(f"{type_name}: {len(indexes)} card(s), {rendered_indexes}")
    else:
        lines.append("interfaces: no recommendation matches")

    return lines


def _parse_deck_card(payload: Any) -> DeckCard:
    if not isinstance(payload, dict):
        raise SaveFileError("deck card must be an object")
    raw_id = _require_string(payload, "id")
    return DeckCard(
        raw_id=raw_id,
        card_id=normalize_game_card_id(raw_id),
        floor_added=_optional_int(payload, "floor_added_to_deck"),
        upgrade_level=_optional_int(payload, "current_upgrade_level") or 0,
    )


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SaveFileError(f"'{key}' must be a non-empty string")
    return value


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise SaveFileError(f"'{key}' must be an integer")
    return value


def _strip_prefix(value: str, prefix: str) -> str:
    if value.startswith(prefix):
        return value[len(prefix) :]
    return value


def _recommend_index_sort_key(value: str) -> tuple[int, int, str]:
    try:
        rank_text, total_text = value.split("/", 1)
        return (int(rank_text), int(total_text), value)
    except ValueError:
        return (9999, 9999, value)
