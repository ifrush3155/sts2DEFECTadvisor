from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageOps

from sts2defect.models import Bounds


SPIRE_CODEX_CARDS_URL = "https://spire-codex.com/api/cards"


@dataclass(frozen=True)
class CardTemplate:
    card_id: str
    display_name: str
    image_path: Path


@dataclass(frozen=True)
class CardTemplateMetadata:
    card_id: str
    display_name: str
    image_url: str


@dataclass(frozen=True)
class CardMatchAlternative:
    card_id: str
    display_name: str
    score: float


@dataclass(frozen=True)
class CardRewardMatch:
    slot: int
    card_id: str | None
    display_name: str | None
    confidence: float
    score: float
    margin: float
    is_uncertain: bool
    bounds: Bounds
    alternatives: list[CardMatchAlternative]
    reason: str | None = None


@dataclass(frozen=True)
class CardRewardRecognitionReport:
    image_path: Path
    method: str
    candidates_loaded: int
    candidates_failed: int
    matches: list[CardRewardMatch]
    notes: list[str]


class RecognitionSession:
    def __init__(
        self,
        loaded_templates: list[tuple[CardTemplate, np.ndarray]],
        candidates_failed: int = 0,
    ) -> None:
        self.loaded_templates = loaded_templates
        self.candidates_failed = candidates_failed
        self.templates = [template for template, _feature in loaded_templates]

    @classmethod
    def from_templates(cls, templates: Iterable[CardTemplate]) -> RecognitionSession:
        loaded_templates: list[tuple[CardTemplate, np.ndarray]] = []
        failed = 0
        for template in templates:
            try:
                template_image = Image.open(template.image_path).convert("RGB")
            except (OSError, ValueError):
                failed += 1
                continue
            loaded_templates.append(
                (template, _image_feature(_template_art_crop(template_image)))
            )
        return cls(loaded_templates, candidates_failed=failed)

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
        matches = _recognize_best_layout(image, self.loaded_templates)

        return CardRewardRecognitionReport(
            image_path=Path(label),
            method="art-template",
            candidates_loaded=len(self.loaded_templates),
            candidates_failed=self.candidates_failed,
            matches=matches,
            notes=[
                "OCR evaluated but not used: pytesseract/easyocr are not available locally.",
                "Rendered title-text matching was evaluated and rejected for this sample.",
                "Art template matching is selected because card artwork is language-neutral.",
                "Card slots are detected from visible reward-card clusters when possible.",
                "Low margins are reported as uncertain instead of silently trusted.",
            ],
        )


def recognize_card_reward_image(
    image_path: str | Path,
    templates: Iterable[CardTemplate],
) -> CardRewardRecognitionReport:
    return RecognitionSession.from_templates(templates).recognize_image(image_path)


def fetch_spire_codex_card_metadata(
    color: str | None = "all",
    lang: str = "zhs",
    timeout_seconds: int = 30,
) -> list[CardTemplateMetadata]:
    if color and color.lower() not in {"all", "any"}:
        url = f"{SPIRE_CODEX_CARDS_URL}?color={color}&lang={lang}"
    else:
        url = f"{SPIRE_CODEX_CARDS_URL}?lang={lang}"
    request = urllib.request.Request(url, headers={"User-Agent": "Codex"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.load(response)
    cards = payload["value"] if isinstance(payload, dict) and "value" in payload else payload
    if not isinstance(cards, list):
        raise ValueError("Spire Codex cards response must be a list")

    metadata: list[CardTemplateMetadata] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_id = card.get("id")
        display_name = card.get("name")
        image_url = card.get("image_url_card")
        if (
            isinstance(card_id, str)
            and card_id
            and isinstance(display_name, str)
            and display_name
            and isinstance(image_url, str)
            and image_url
        ):
            metadata.append(
                CardTemplateMetadata(
                    card_id=card_id,
                    display_name=display_name,
                    image_url=image_url,
                )
            )
    return metadata


def ensure_card_templates(
    metadata: Iterable[CardTemplateMetadata],
    cache_dir: str | Path,
    timeout_seconds: int = 12,
) -> tuple[list[CardTemplate], list[str]]:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    templates: list[CardTemplate] = []
    failures: list[str] = []
    for item in metadata:
        suffix = Path(item.image_url).suffix or ".webp"
        image_path = cache_path / f"{item.card_id}{suffix}"
        if not image_path.exists():
            try:
                request = urllib.request.Request(
                    item.image_url, headers={"User-Agent": "Codex"}
                )
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    image_path.write_bytes(response.read())
            except (OSError, TimeoutError, ValueError) as exc:
                failures.append(f"{item.card_id}: {type(exc).__name__}")
                continue
        templates.append(
            CardTemplate(
                card_id=item.card_id,
                display_name=item.display_name,
                image_path=image_path,
            )
        )
    return templates, failures


def format_card_reward_recognition(report: CardRewardRecognitionReport) -> list[str]:
    lines = [
        f"card_reward_image {report.image_path}: {len(report.matches)} slots",
        f"method: {report.method}",
        (
            f"candidates: {report.candidates_loaded} loaded"
            f", {report.candidates_failed} failed"
        ),
    ]
    for match in report.matches:
        if match.card_id is None:
            lines.append(
                f"{match.slot}. UNKNOWN confidence {match.confidence:.3f}: "
                f"{match.reason or 'no template match'}"
            )
            continue
        uncertainty = " uncertain" if match.is_uncertain else ""
        lines.append(
            f"{match.slot}. {match.display_name} / {match.card_id}: "
            f"confidence {match.confidence:.3f}, score {match.score:.3f}, "
            f"margin {match.margin:.3f}{uncertainty}"
        )
        if match.alternatives:
            rendered = ", ".join(
                f"{item.display_name}/{item.card_id} {item.score:.3f}"
                for item in match.alternatives[:3]
            )
            lines.append(f"   alternatives: {rendered}")

    uncertain = [
        match
        for match in report.matches
        if match.card_id is None or match.is_uncertain
    ]
    if uncertain:
        lines.append("uncertain:")
        for match in uncertain:
            name = match.display_name or "UNKNOWN"
            card_id = match.card_id or "UNKNOWN"
            reason = match.reason or (
                f"low margin {match.margin:.3f}; inspect alternatives"
            )
            lines.append(f"- slot {match.slot}: {name} / {card_id} ({reason})")
    else:
        lines.append("uncertain: none")

    lines.append("assessment:")
    lines.extend(f"- {note}" for note in report.notes)
    return lines


def save_card_reward_debug_artifacts(
    report: CardRewardRecognitionReport,
    templates: Iterable[CardTemplate],
    output_dir: str | Path,
    alternatives_limit: int = 3,
) -> Path:
    run_dir = Path(output_dir) / report.image_path.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    template_by_id = {template.card_id: template for template in templates}
    image = Image.open(report.image_path).convert("RGB")
    manifest: dict[str, object] = {
        "image": str(report.image_path),
        "method": report.method,
        "slots": [],
    }

    for match in report.matches:
        crop_path = run_dir / f"slot-{match.slot}-crop.png"
        crop = image.crop(
            (
                match.bounds.x,
                match.bounds.y,
                match.bounds.x + match.bounds.width,
                match.bounds.y + match.bounds.height,
            )
        )
        crop.save(crop_path)

        slot_manifest: dict[str, object] = {
            "slot": match.slot,
            "crop": crop_path.name,
            "match": {
                "id": match.card_id,
                "name": match.display_name,
                "confidence": match.confidence,
                "score": match.score,
                "margin": match.margin,
                "uncertain": match.is_uncertain,
                "reason": match.reason,
            },
            "alternatives": [],
        }
        if match.card_id:
            match_template_path = _save_debug_template_image(
                template_by_id,
                match.card_id,
                run_dir / f"slot-{match.slot}-match-{match.card_id}.png",
            )
            if match_template_path:
                slot_manifest["match"]["template"] = match_template_path.name

        alternatives_manifest: list[dict[str, object]] = []
        for index, alternative in enumerate(match.alternatives[:alternatives_limit], start=1):
            alternative_path = _save_debug_template_image(
                template_by_id,
                alternative.card_id,
                run_dir / f"slot-{match.slot}-alt-{index}-{alternative.card_id}.png",
            )
            alternatives_manifest.append(
                {
                    "rank": index,
                    "id": alternative.card_id,
                    "name": alternative.display_name,
                    "score": alternative.score,
                    "template": alternative_path.name if alternative_path else None,
                }
            )
        slot_manifest["alternatives"] = alternatives_manifest
        manifest["slots"].append(slot_manifest)

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _save_debug_template_image(
    template_by_id: dict[str, CardTemplate],
    card_id: str,
    output_path: Path,
) -> Path | None:
    template = template_by_id.get(card_id)
    if template is None:
        return None
    try:
        image = Image.open(template.image_path).convert("RGB")
    except (OSError, ValueError):
        return None
    _template_art_crop(image).save(output_path)
    return output_path


def _build_slot_match(
    slot: int,
    bounds: Bounds,
    ranked: list[tuple[float, CardTemplate]],
) -> CardRewardMatch:
    if not ranked:
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
            reason="no card templates were loaded",
        )

    top_score, top_template = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    margin = top_score - second_score
    is_uncertain = top_score < 0.35 or margin < 0.03
    reason = None
    if top_score < 0.35:
        reason = f"low score {top_score:.3f}; inspect alternatives"
    elif margin < 0.03:
        reason = f"low margin {margin:.3f}; inspect alternatives"
    confidence = max(0.0, min(1.0, top_score + margin * 2.0))
    alternatives = [
        CardMatchAlternative(
            card_id=template.card_id,
            display_name=template.display_name,
            score=score,
        )
        for score, template in ranked[1:4]
    ]
    return CardRewardMatch(
        slot=slot,
        card_id=top_template.card_id,
        display_name=top_template.display_name,
        confidence=confidence,
        score=top_score,
        margin=margin,
        is_uncertain=is_uncertain,
        bounds=bounds,
        alternatives=alternatives,
        reason=reason,
    )


def _recognize_best_layout(
    image: Image.Image,
    loaded_templates: list[tuple[CardTemplate, np.ndarray]],
) -> list[CardRewardMatch]:
    layout_results: list[tuple[float, list[CardRewardMatch]]] = []
    for boxes in _slot_art_box_layouts(image):
        matches = [
            _recognize_slot(
                image,
                slot,
                box,
                loaded_templates,
                broad_vertical_search=len(boxes) == 4,
            )
            for slot, box in enumerate(boxes)
        ]
        if matches:
            layout_score = sum(
                match.score + max(0.0, match.margin)
                for match in matches
            ) / len(matches)
        else:
            layout_score = 0.0
        layout_results.append((layout_score, matches))

    if not layout_results:
        return []
    return max(layout_results, key=lambda item: item[0])[1]


def _recognize_slot(
    image: Image.Image,
    slot: int,
    base_box: Bounds,
    loaded_templates: list[tuple[CardTemplate, np.ndarray]],
    broad_vertical_search: bool = False,
) -> CardRewardMatch:
    best_quality = float("-inf")
    best_box = base_box
    best_ranked: list[tuple[float, CardTemplate]] = []
    for box, position_penalty in _nearby_art_boxes(
        base_box,
        image.size,
        broad_vertical_search=broad_vertical_search,
    ):
        crop = image.crop((box.x, box.y, box.x + box.width, box.y + box.height))
        feature = _image_feature(crop)
        ranked = sorted(
            (
                (_feature_score(feature, template_feature), template)
                for template, template_feature in loaded_templates
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        top_score = ranked[0][0] if ranked else 0.0
        second_score = ranked[1][0] if len(ranked) > 1 else 0.0
        quality = top_score - position_penalty
        if quality > best_quality:
            best_quality = quality
            best_box = box
            best_ranked = ranked
    return _build_slot_match(slot, best_box, best_ranked)


def _slot_art_box_layouts(image: Image.Image) -> list[list[Bounds]]:
    image_size = image.size
    width, height = image_size
    layouts = {
        3: [
            (535 / 1967, 555 / 1162, 188 / 1967, 139 / 1162),
            (894 / 1967, 555 / 1162, 189 / 1967, 139 / 1162),
            (1249 / 1967, 555 / 1162, 190 / 1967, 139 / 1162),
        ],
        4: [
            (413 / 2559, 730 / 1516, 250 / 2559, 184 / 1516),
            (872 / 2559, 730 / 1516, 250 / 2559, 184 / 1516),
            (1331 / 2559, 730 / 1516, 250 / 2559, 184 / 1516),
            (1790 / 2559, 730 / 1516, 250 / 2559, 184 / 1516),
        ],
    }
    detected_count = _detect_card_count_from_clusters(image)
    selected_counts = [detected_count] if detected_count in layouts else [3, 4]
    return [
        [
            Bounds(
                x=round(x * width),
                y=round(y * height),
                width=round(w * width),
                height=round(h * height),
            )
            for x, y, w, h in layouts[count]
        ]
        for count in selected_counts
    ]


def _detect_card_count_from_clusters(image: Image.Image) -> int | None:
    width, height = image.size
    top = round(height * 0.38)
    bottom = round(height * 0.72)
    pixels = np.array(image.crop((0, top, width, bottom))).astype(np.float32)
    brightness = pixels.mean(axis=2)
    saturation = pixels.max(axis=2) - pixels.min(axis=2)
    mask = (brightness > 55) & (saturation > 25)
    column_density = mask.mean(axis=0)
    kernel_width = max(5, width // 100)
    kernel = np.ones(kernel_width, dtype=np.float32) / kernel_width
    smoothed = np.convolve(column_density, kernel, mode="same")
    threshold = max(0.02, float(smoothed.max()) * 0.22)

    clusters: list[tuple[int, int]] = []
    start: int | None = None
    min_width = round(width * 0.035)
    for index, value in enumerate(smoothed):
        if value > threshold and start is None:
            start = index
        if start is not None and (value <= threshold or index == len(smoothed) - 1):
            end = index
            if end - start >= min_width:
                clusters.append((start, end))
            start = None

    if len(clusters) in {3, 4}:
        return len(clusters)
    return None


def _nearby_art_boxes(
    base_box: Bounds,
    image_size: tuple[int, int],
    broad_vertical_search: bool = False,
) -> list[tuple[Bounds, float]]:
    image_width, image_height = image_size
    boxes: list[tuple[Bounds, float]] = []
    seen: set[Bounds] = set()
    scales = [(0.92, 0.92), (1.0, 1.0), (1.08, 1.08)]
    if broad_vertical_search:
        scales.extend([(0.92, 0.78), (1.0, 0.78), (1.08, 0.78)])
    for width_scale, height_scale in scales:
        width = round(base_box.width * width_scale)
        height = round(base_box.height * height_scale)
        dy_ratios = (
            (-0.50, -0.35, -0.20, -0.12, 0.0, 0.12, 0.20)
            if broad_vertical_search
            else (-0.12, 0.0, 0.12)
        )
        dx_ratios = (
            (-0.08, 0.0, 0.08, 0.16, 0.24)
            if broad_vertical_search
            else (-0.08, 0.0, 0.08)
        )
        for dx_ratio in dx_ratios:
            for dy_ratio in dy_ratios:
                x = round(base_box.x + base_box.width * dx_ratio)
                y = round(base_box.y + base_box.height * dy_ratio)
                x = max(0, min(x, image_width - width))
                y = max(0, min(y, image_height - height))
                box = Bounds(x=x, y=y, width=width, height=height)
                if box not in seen:
                    seen.add(box)
                    penalty = abs(dx_ratio) * 0.06 + abs(dy_ratio) * 0.12
                    penalty += abs(width_scale - 1.0) * 0.08
                    penalty += abs(height_scale - 1.0) * 0.04
                    boxes.append((box, penalty))
    return boxes


def _template_art_crop(image: Image.Image) -> Image.Image:
    width, height = image.size
    box = (
        round(82 / 400 * width),
        round(143 / 520 * height),
        round(320 / 400 * width),
        round(294 / 520 * height),
    )
    return image.crop(box)


def _image_feature(image: Image.Image) -> np.ndarray:
    resized = ImageOps.grayscale(image.resize((96, 64), Image.Resampling.LANCZOS))
    values = np.array(resized).astype(np.float32)
    return (values - values.mean()) / (values.std() + 1e-6)


def _feature_score(left: np.ndarray, right: np.ndarray) -> float:
    return float((left * right).mean())
