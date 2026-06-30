from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Protocol

from PIL import Image, ImageOps

from sts2defect.models import Bounds
from sts2defect.recommendations import RecommendationStore
from sts2defect.recognition.card_reward import (
    CardMatchAlternative,
    CardRewardMatch,
    CardRewardRecognitionReport,
    _detect_card_count_from_clusters,
)


class OcrEngine(Protocol):
    def __call__(self, image) -> object:
        ...


@dataclass(frozen=True)
class OcrTextLine:
    text: str
    confidence: float


@dataclass(frozen=True)
class _PositionedOcrTextLine:
    text: str
    confidence: float
    center_x: float


@dataclass(frozen=True)
class NormalizedOcrName:
    text: str
    is_upgraded: bool


@dataclass(frozen=True)
class KnownCardNameMatch:
    card_id: str
    display_name: str
    score: float
    is_upgraded: bool
    is_uncertain: bool
    alternatives: list[CardMatchAlternative]
    normalized_text: str


class OcrCardRewardSession:
    def __init__(
        self,
        recommendations: RecommendationStore,
        engine: OcrEngine | None = None,
    ) -> None:
        self.recommendations = recommendations
        self.engine = engine if engine is not None else _create_rapidocr_engine()

    def recognize_image(self, image_path: str | Path) -> CardRewardRecognitionReport:
        path = Path(image_path)
        image = Image.open(path).convert("RGB")
        return self.recognize_image_object(image, label=str(path))

    def recognize_image_object(
        self,
        image: Image.Image,
        label: str = "<memory>",
    ) -> CardRewardRecognitionReport:
        image = image.convert("RGB")
        title_boxes = _slot_title_box_layout(image)
        ocr_lines = _recognize_combined_title_crops(self.engine, image, title_boxes)
        return recognize_card_reward_titles_from_ocr_lines(
            ocr_lines,
            self.recommendations,
            image_label=label,
            bounds=title_boxes,
        )


def recognize_card_reward_titles_from_ocr_lines(
    slot_lines: Iterable[Iterable[OcrTextLine]],
    recommendations: RecommendationStore,
    image_label: str = "<memory>",
    bounds: Iterable[Bounds] | None = None,
) -> CardRewardRecognitionReport:
    slot_bounds = list(bounds) if bounds is not None else []
    matches: list[CardRewardMatch] = []
    notes: list[str] = [
        "OCR is the primary recognition path and reads only reward-card title regions.",
        "Chinese OCR text is fuzzy-matched against recommendation knownCards names.",
        "Card-art template matching should only be used as a fallback for uncertain OCR slots.",
    ]

    for slot, lines in enumerate(slot_lines):
        bounds_item = (
            slot_bounds[slot]
            if slot < len(slot_bounds)
            else Bounds(x=0, y=0, width=0, height=0)
        )
        line_list = list(lines)
        ocr_text = _select_title_text(line_list)
        ocr_confidence = max((line.confidence for line in line_list), default=0.0)
        known_match = best_known_card_match(ocr_text, recommendations)
        matches.append(
            _build_ocr_slot_match(
                slot=slot,
                bounds=bounds_item,
                ocr_text=ocr_text,
                ocr_confidence=ocr_confidence,
                known_match=known_match,
            )
        )

    return CardRewardRecognitionReport(
        image_path=Path(image_label),
        method="ocr",
        candidates_loaded=len(recommendations.known_card_display_names()),
        candidates_failed=0,
        matches=matches,
        notes=notes,
    )


def merge_uncertain_matches_with_fallback(
    primary: CardRewardRecognitionReport,
    fallback: CardRewardRecognitionReport,
) -> CardRewardRecognitionReport:
    fallback_by_slot = {match.slot: match for match in fallback.matches}
    merged: list[CardRewardMatch] = []
    for match in primary.matches:
        fallback_match = fallback_by_slot.get(match.slot)
        if (
            fallback_match is not None
            and (match.card_id is None or match.is_uncertain)
            and fallback_match.card_id is not None
            and not fallback_match.is_uncertain
        ):
            merged.append(fallback_match)
            continue
        merged.append(match)
    return CardRewardRecognitionReport(
        image_path=primary.image_path,
        method=f"{primary.method}+fallback",
        candidates_loaded=primary.candidates_loaded + fallback.candidates_loaded,
        candidates_failed=primary.candidates_failed + fallback.candidates_failed,
        matches=merged,
        notes=[
            *primary.notes,
            "Uncertain OCR slots were checked with card-art template fallback.",
            *fallback.notes,
        ],
    )


def best_known_card_match(
    ocr_text: str,
    recommendations: RecommendationStore,
) -> KnownCardNameMatch | None:
    normalized = normalize_ocr_card_name(ocr_text)
    if not normalized.text:
        return None

    ranked: list[tuple[float, str, str]] = []
    for display_name, card_id in recommendations.known_card_display_names().items():
        candidate = normalize_ocr_card_name(display_name).text
        score = _fuzzy_score(normalized.text, candidate)
        ranked.append((score, display_name, card_id))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return None

    top_score, display_name, card_id = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    margin = top_score - second_score
    is_uncertain = top_score < _score_threshold(normalized.text) or margin < 0.04
    alternatives = [
        CardMatchAlternative(
            card_id=alternative_card_id,
            display_name=alternative_name,
            score=score,
        )
        for score, alternative_name, alternative_card_id in ranked[1:4]
    ]
    return KnownCardNameMatch(
        card_id=card_id,
        display_name=display_name,
        score=top_score,
        is_upgraded=normalized.is_upgraded,
        is_uncertain=is_uncertain,
        alternatives=alternatives,
        normalized_text=normalized.text,
    )


def normalize_ocr_card_name(text: str) -> NormalizedOcrName:
    is_upgraded = "+" in text or "＋" in text
    normalized = text.upper()
    normalized = normalized.replace("＋", "+")
    normalized = re.sub(r"[\s\+\-_/\\|·.,:;!?！？。，、：；'\"“”‘’()[\]{}<>《》（）]", "", normalized)
    return NormalizedOcrName(text=normalized, is_upgraded=is_upgraded)


def _create_rapidocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "rapidocr_onnxruntime is not installed. Install it with: "
            "python -m pip install rapidocr-onnxruntime"
        ) from exc
    return RapidOCR()


def _slot_title_box_layout(image: Image.Image) -> list[Bounds]:
    width, height = image.size
    layouts = {
        3: [
            (0.305, 0.448, 0.075, 0.045),
            (0.485, 0.448, 0.075, 0.045),
            (0.665, 0.448, 0.075, 0.045),
        ],
        4: [
            (0.198, 0.398, 0.070, 0.070),
            (0.377, 0.432, 0.078, 0.058),
            (0.554, 0.432, 0.078, 0.058),
            (0.731, 0.432, 0.078, 0.058),
        ],
    }
    detected_count = _detect_card_count_from_clusters(image)
    count = detected_count if detected_count in layouts else 4
    return [
        Bounds(
            x=round(x * width),
            y=round(y * height),
            width=round(w * width),
            height=round(h * height),
        )
        for x, y, w, h in layouts[count]
    ]


def _prepare_title_crop(image: Image.Image, bounds: Bounds) -> Image.Image:
    crop = image.crop(
        (
            bounds.x,
            bounds.y,
            bounds.x + bounds.width,
            bounds.y + bounds.height,
        )
    )
    crop = ImageOps.autocontrast(crop.convert("RGB"))
    scale = 2
    return crop.resize(
        (max(1, crop.width * scale), max(1, crop.height * scale)),
        Image.Resampling.LANCZOS,
    )


def _recognize_combined_title_crops(
    engine: OcrEngine,
    image: Image.Image,
    bounds: list[Bounds],
) -> list[list[OcrTextLine]]:
    crops = [_prepare_title_crop(image, bounds_item) for bounds_item in bounds]
    if not crops:
        return []
    gap = 80
    width = sum(crop.width for crop in crops) + gap * (len(crops) - 1)
    height = max(crop.height for crop in crops)
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    ranges: list[tuple[int, int]] = []
    x = 0
    for crop in crops:
        canvas.paste(crop, (x, 0))
        ranges.append((x, x + crop.width))
        x += crop.width + gap

    slot_lines: list[list[OcrTextLine]] = [[] for _ in crops]
    for line in _extract_positioned_ocr_text_lines(engine(canvas)):
        slot = _slot_index_for_x(line.center_x, ranges)
        if slot is None:
            continue
        slot_lines[slot].append(
            OcrTextLine(text=line.text, confidence=line.confidence)
        )
    return slot_lines


def _slot_index_for_x(center_x: float, ranges: list[tuple[int, int]]) -> int | None:
    for index, (start, end) in enumerate(ranges):
        if start <= center_x <= end:
            return index
    if not ranges:
        return None
    centers = [start + (end - start) / 2 for start, end in ranges]
    nearest = min(range(len(centers)), key=lambda index: abs(centers[index] - center_x))
    if abs(centers[nearest] - center_x) <= 80:
        return nearest
    return None


def _extract_ocr_text_lines(result: object) -> list[OcrTextLine]:
    return [
        OcrTextLine(text=line.text, confidence=line.confidence)
        for line in _extract_positioned_ocr_text_lines(result)
    ]


def _extract_positioned_ocr_text_lines(result: object) -> list[_PositionedOcrTextLine]:
    raw_lines = result[0] if isinstance(result, tuple) and result else result
    lines: list[_PositionedOcrTextLine] = []
    if not isinstance(raw_lines, list):
        return lines
    for item in raw_lines:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        center_x = _ocr_item_center_x(item)
        text = item[1] if isinstance(item[1], str) else None
        confidence = item[2] if len(item) > 2 else 0.0
        if text is None and isinstance(item[1], (list, tuple)) and item[1]:
            text = item[1][0] if isinstance(item[1][0], str) else None
            confidence = item[1][1] if len(item[1]) > 1 else confidence
        if isinstance(text, str) and text.strip():
            try:
                score = float(confidence)
            except (TypeError, ValueError):
                score = 0.0
            lines.append(
                _PositionedOcrTextLine(
                    text=text.strip(),
                    confidence=score,
                    center_x=center_x,
                )
            )
    return lines


def _ocr_item_center_x(item: object) -> float:
    if not isinstance(item, (list, tuple)) or not item:
        return 0.0
    box = item[0]
    if not isinstance(box, (list, tuple)):
        return 0.0
    xs: list[float] = []
    for point in box:
        if (
            isinstance(point, (list, tuple))
            and point
            and isinstance(point[0], (int, float))
        ):
            xs.append(float(point[0]))
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def _select_title_text(lines: list[OcrTextLine]) -> str:
    if not lines:
        return ""
    return max(lines, key=lambda line: (line.confidence, len(line.text))).text


def _build_ocr_slot_match(
    slot: int,
    bounds: Bounds,
    ocr_text: str,
    ocr_confidence: float,
    known_match: KnownCardNameMatch | None,
) -> CardRewardMatch:
    if known_match is None:
        return CardRewardMatch(
            slot=slot,
            card_id=None,
            display_name=None,
            confidence=0.0,
            score=0.0,
            margin=0.0,
            is_uncertain=True,
            bounds=bounds,
            alternatives=[],
            reason=f"no OCR title text matched known cards: {ocr_text!r}",
        )

    confidence = max(0.0, min(1.0, known_match.score * max(ocr_confidence, 0.65)))
    reason = None
    if known_match.is_uncertain:
        reason = (
            f"uncertain OCR match {ocr_text!r} -> {known_match.display_name!r} "
            f"score {known_match.score:.3f}"
        )
    display_name = (
        f"{known_match.display_name}+"
        if known_match.is_upgraded
        else known_match.display_name
    )
    return CardRewardMatch(
        slot=slot,
        card_id=known_match.card_id,
        display_name=display_name,
        confidence=confidence,
        score=known_match.score,
        margin=known_match.score,
        is_uncertain=known_match.is_uncertain,
        bounds=bounds,
        alternatives=known_match.alternatives,
        reason=reason,
    )


def _fuzzy_score(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    sequence_score = SequenceMatcher(None, left, right).ratio()
    overlap = len(set(left) & set(right)) / max(len(set(left)), len(set(right)))
    positional = sum(
        1 for left_char, right_char in zip(left, right) if left_char == right_char
    ) / max(len(left), len(right))
    substring_bonus = 0.12 if left in right or right in left else 0.0
    return min(
        1.0,
        sequence_score * 0.55 + overlap * 0.20 + positional * 0.25 + substring_bonus,
    )


def _score_threshold(text: str) -> float:
    if len(text) <= 2:
        return 0.48
    if len(text) <= 4:
        return 0.58
    return 0.62
