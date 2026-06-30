from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bounds:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class RecognizedCard:
    name: str
    confidence: float
    bounds: Bounds | None = None


@dataclass(frozen=True)
class CardRecommendation:
    card_id: str
    card_name: str
    display_name: str
    type_name: str
    rank: int
    total: int
    recommend_index: str


@dataclass(frozen=True)
class EnrichedCard:
    card_name: str
    recommendation: CardRecommendation | None
    confidence: float | None = None
    bounds: Bounds | None = None


@dataclass(frozen=True)
class TypeSummary:
    count: int
    recommend_indexes: list[str]


@dataclass(frozen=True)
class LibrarySummary:
    total_cards: int
    unknown_count: int
    by_type: dict[str, TypeSummary]
