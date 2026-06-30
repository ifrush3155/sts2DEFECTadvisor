from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .recommendations import RecommendationDataError, RecommendationStore
from .savefiles import (
    SaveFileError,
    format_deck_snapshot_preview,
    load_profile_deck_snapshot,
)
from .sts2mcp import (
    Sts2McpClientError,
    Sts2McpReadOnlyClient,
    format_card_reward_preview,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sts2defect")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-data", help="Validate a recommendation JSON file."
    )
    validate_parser.add_argument("path", type=Path)

    preview_parser = subparsers.add_parser(
        "preview-card-reward",
        help="Read STS2MCP card_reward state and print matched recommendations.",
    )
    preview_parser.add_argument("recommendations", type=Path)
    preview_parser.add_argument("--base-url", default="http://localhost:15526")
    preview_parser.add_argument(
        "--ascii",
        action="store_true",
        help="Print ASCII interface labels for terminals that cannot display UTF-8.",
    )

    panel_parser = subparsers.add_parser(
        "run-panel",
        help="Open the read-only always-on-top assistant panel.",
    )
    panel_parser.add_argument("recommendations", type=Path)
    panel_parser.add_argument("--base-url", default="http://localhost:15526")
    panel_parser.add_argument(
        "--interval-ms",
        type=int,
        default=2000,
        help="Refresh interval for the local deck snapshot page.",
    )

    deck_parser = subparsers.add_parser(
        "preview-deck-snapshot",
        help="Read a local STS2 profile current_run.save and print deck recommendation stats.",
    )
    deck_parser.add_argument("profile_path", type=Path)
    deck_parser.add_argument("recommendations", type=Path)

    vision_parser = subparsers.add_parser(
        "recognize-card-reward",
        help="Recognize a card reward screenshot with read-only OCR or image matching.",
    )
    vision_parser.add_argument("image", type=Path)
    vision_parser.add_argument(
        "--recommendations",
        type=Path,
        default=Path("data/recommendations/slay-the-spire-2-manual.json"),
        help="Recommendation JSON used for OCR Chinese-name matching.",
    )
    vision_parser.add_argument(
        "--method",
        choices=("ocr", "art", "auto"),
        default="ocr",
        help="Recognition method. auto uses OCR first and art templates only for uncertain slots.",
    )
    vision_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "sts2defect" / "card-images" / "defect",
        help="Directory used to cache downloaded card face templates.",
    )
    vision_parser.add_argument(
        "--color",
        default="all",
        help="Spire Codex card color used as template candidates; use all for every card.",
    )
    vision_parser.add_argument(
        "--debug-dir",
        type=Path,
        help="Optional directory for slot crops, matched templates, alternatives, and manifest.",
    )

    screen_parser = subparsers.add_parser(
        "recognize-card-reward-screen",
        help="Capture the current screen or a visible window, then recognize card rewards.",
    )
    screen_parser.add_argument(
        "--window-title",
        help="Optional visible Windows window title substring to capture.",
    )
    screen_parser.add_argument(
        "--screenshot-dir",
        type=Path,
        help="Directory used to save captured screenshots before recognition.",
    )
    screen_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "sts2defect" / "card-images" / "defect",
        help="Directory used to cache downloaded card face templates.",
    )
    screen_parser.add_argument(
        "--color",
        default="all",
        help="Spire Codex card color used as template candidates; use all for every card.",
    )
    screen_parser.add_argument(
        "--debug-dir",
        type=Path,
        help="Optional directory for screenshot crops, matched templates, alternatives, and manifest.",
    )
    screen_parser.add_argument(
        "--recommendations",
        type=Path,
        default=Path("data/recommendations/slay-the-spire-2-manual.json"),
        help="Recommendation JSON used for OCR Chinese-name matching.",
    )
    screen_parser.add_argument(
        "--method",
        choices=("ocr", "art", "auto"),
        default="ocr",
        help="Recognition method. auto uses OCR first and art templates only for uncertain slots.",
    )

    benchmark_parser = subparsers.add_parser(
        "benchmark-card-reward-recognition",
        help="Benchmark screenshot capture, template preload, and hot card reward recognition.",
    )
    benchmark_parser.add_argument(
        "--image",
        type=Path,
        help="Existing screenshot image to benchmark. If omitted, capture the screen first.",
    )
    benchmark_parser.add_argument(
        "--window-title",
        help="Optional visible Windows window title substring to capture when --image is omitted.",
    )
    benchmark_parser.add_argument(
        "--screenshot-dir",
        type=Path,
        help="Directory used to save captured screenshots when --image is omitted.",
    )
    benchmark_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "sts2defect" / "card-images" / "defect",
        help="Directory used to cache downloaded card face templates.",
    )
    benchmark_parser.add_argument(
        "--color",
        default="all",
        help="Spire Codex card color used as template candidates; use all for every card.",
    )
    benchmark_parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of hot recognition runs after preload.",
    )

    ocr_benchmark_parser = subparsers.add_parser(
        "benchmark-card-reward-ocr",
        help="Benchmark OCR recognition hot path and RSS memory growth.",
    )
    ocr_benchmark_parser.add_argument("image", type=Path)
    ocr_benchmark_parser.add_argument(
        "--recommendations",
        type=Path,
        default=Path("data/recommendations/slay-the-spire-2-manual.json"),
        help="Recommendation JSON used for OCR Chinese-name matching.",
    )
    ocr_benchmark_parser.add_argument(
        "--runs",
        type=int,
        default=100,
        help="Number of repeated OCR recognitions with one reused OCR session.",
    )

    args = parser.parse_args(argv)
    if args.command == "validate-data":
        return validate_data(args.path)
    if args.command == "preview-card-reward":
        return preview_card_reward(args.recommendations, args.base_url, args.ascii)
    if args.command == "run-panel":
        return run_panel(args.recommendations, args.base_url, args.interval_ms)
    if args.command == "preview-deck-snapshot":
        return preview_deck_snapshot(args.profile_path, args.recommendations)
    if args.command == "recognize-card-reward":
        return recognize_card_reward(
            args.image,
            args.cache_dir,
            args.color,
            args.debug_dir,
            args.recommendations,
            args.method,
        )
    if args.command == "recognize-card-reward-screen":
        return recognize_card_reward_screen(
            args.window_title,
            args.screenshot_dir,
            args.cache_dir,
            args.color,
            args.debug_dir,
            args.recommendations,
            args.method,
        )
    if args.command == "benchmark-card-reward-recognition":
        return benchmark_card_reward_recognition(
            args.image,
            args.window_title,
            args.screenshot_dir,
            args.cache_dir,
            args.color,
            args.runs,
        )
    if args.command == "benchmark-card-reward-ocr":
        return benchmark_card_reward_ocr(
            args.image,
            args.recommendations,
            args.runs,
        )
    parser.error(f"unknown command: {args.command}")
    return 2


def validate_data(path: Path) -> int:
    try:
        store = RecommendationStore.from_file(path)
    except (OSError, RecommendationDataError, ValueError) as exc:
        print(f"invalid recommendation data: {exc}", file=sys.stderr)
        return 1

    print(f"valid recommendation data: {path} (version {store.version})")
    return 0


def preview_card_reward(recommendations_path: Path, base_url: str, ascii_only: bool) -> int:
    try:
        recommendations = RecommendationStore.from_file(recommendations_path)
    except (OSError, RecommendationDataError, ValueError) as exc:
        print(f"invalid recommendation data: {exc}", file=sys.stderr)
        return 1

    client = Sts2McpReadOnlyClient(base_url=base_url)
    try:
        state = client.fetch_card_reward()
    except Sts2McpClientError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if state is None:
        print("current STS2MCP state is not card_reward")
        return 0

    for line in format_card_reward_preview(state, recommendations, ascii_only=ascii_only):
        print(line)
    return 0


def run_panel(recommendations_path: Path, base_url: str, interval_ms: int) -> int:
    if interval_ms < 100:
        print("interval-ms must be at least 100", file=sys.stderr)
        return 1

    try:
        from .ui.panel import run_panel_app
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "PySide6 is not installed. Install it with: python -m pip install PySide6",
                file=sys.stderr,
            )
            return 1
        raise

    try:
        return run_panel_app(
            recommendations_path=recommendations_path,
            base_url=base_url,
            interval_ms=interval_ms,
        )
    except (OSError, RecommendationDataError, ValueError) as exc:
        print(f"failed to start panel: {exc}", file=sys.stderr)
        return 1


def preview_deck_snapshot(profile_path: Path, recommendations_path: Path) -> int:
    try:
        recommendations = RecommendationStore.from_file(recommendations_path)
        snapshot = load_profile_deck_snapshot(profile_path)
    except (OSError, RecommendationDataError, SaveFileError, ValueError) as exc:
        print(f"failed to preview deck snapshot: {exc}", file=sys.stderr)
        return 1

    for line in format_deck_snapshot_preview(snapshot, recommendations):
        print(line)
    return 0


def recognize_card_reward(
    image_path: Path,
    cache_dir: Path,
    color: str,
    debug_dir: Path | None,
    recommendations_path: Path,
    method: str,
) -> int:
    return _recognize_card_reward_image_path(
        image_path,
        cache_dir,
        color,
        debug_dir,
        recommendations_path,
        method,
    )


def recognize_card_reward_screen(
    window_title: str | None,
    screenshot_dir: Path | None,
    cache_dir: Path,
    color: str,
    debug_dir: Path | None,
    recommendations_path: Path,
    method: str,
) -> int:
    try:
        from .capture import ScreenshotCaptureError, ScreenshotCaptureSource
    except ModuleNotFoundError as exc:
        missing = exc.name or "required screenshot package"
        print(f"{missing} is not installed.", file=sys.stderr)
        return 1

    try:
        capture_source = ScreenshotCaptureSource(
            output_dir=screenshot_dir,
            window_title=window_title,
        )
        frame = capture_source.capture()
    except (OSError, ScreenshotCaptureError, ValueError) as exc:
        print(f"failed to capture screenshot: {exc}", file=sys.stderr)
        return 1

    screenshot_path = Path(frame.image)
    print(f"captured screenshot: {screenshot_path}")
    return _recognize_card_reward_image_path(
        screenshot_path,
        cache_dir,
        color,
        debug_dir,
        recommendations_path,
        method,
    )


def _recognize_card_reward_image_path(
    image_path: Path,
    cache_dir: Path,
    color: str,
    debug_dir: Path | None,
    recommendations_path: Path,
    method: str,
) -> int:
    try:
        report, templates, failures = _recognize_card_reward_report(
            image_path=image_path,
            cache_dir=cache_dir,
            color=color,
            recommendations_path=recommendations_path,
            method=method,
        )
        from .recognition.card_reward import (
            format_card_reward_recognition,
            save_card_reward_debug_artifacts,
        )
    except (OSError, RecommendationDataError, ValueError, ModuleNotFoundError) as exc:
        print(f"failed to recognize card reward screenshot: {exc}", file=sys.stderr)
        return 1

    if failures:
        print(f"template download failures: {len(failures)}", file=sys.stderr)
        for failure in failures[:5]:
            print(f"- {failure}", file=sys.stderr)
    for line in format_card_reward_recognition(report):
        print(line)
    if debug_dir is not None:
        try:
            manifest_path = save_card_reward_debug_artifacts(
                report,
                templates,
                debug_dir,
            )
        except OSError as exc:
            print(f"failed to write debug artifacts: {exc}", file=sys.stderr)
            return 1
        print(f"debug artifacts: {manifest_path}")
    return 0


def _recognize_card_reward_report(
    image_path: Path,
    cache_dir: Path,
    color: str,
    recommendations_path: Path,
    method: str,
):
    if method not in {"ocr", "art", "auto"}:
        raise ValueError("method must be one of: ocr, art, auto")

    templates = []
    failures: list[str] = []
    if method in {"art", "auto"}:
        from .recognition.card_reward import (
            ensure_card_templates,
            fetch_spire_codex_card_metadata,
        )

        metadata = fetch_spire_codex_card_metadata(color=color)
        templates, failures = ensure_card_templates(metadata, cache_dir)

    if method == "art":
        from .recognition.card_reward import recognize_card_reward_image

        return recognize_card_reward_image(image_path, templates), templates, failures

    from .recognition.card_reward_ocr import (
        OcrCardRewardSession,
        merge_uncertain_matches_with_fallback,
    )

    recommendations = RecommendationStore.from_file(recommendations_path)
    ocr_report = OcrCardRewardSession(recommendations).recognize_image(image_path)
    if method == "ocr" or not _report_needs_fallback(ocr_report):
        return ocr_report, templates, failures

    from .recognition.card_reward import recognize_card_reward_image

    fallback_report = recognize_card_reward_image(image_path, templates)
    return (
        merge_uncertain_matches_with_fallback(ocr_report, fallback_report),
        templates,
        failures,
    )


def benchmark_card_reward_recognition(
    image_path: Path | None,
    window_title: str | None,
    screenshot_dir: Path | None,
    cache_dir: Path,
    color: str,
    runs: int,
) -> int:
    if runs < 1:
        print("--runs must be at least 1", file=sys.stderr)
        return 1

    try:
        from .recognition.card_reward import (
            RecognitionSession,
            ensure_card_templates,
            fetch_spire_codex_card_metadata,
            format_card_reward_recognition,
        )
    except ModuleNotFoundError as exc:
        missing = exc.name or "required image package"
        print(f"{missing} is not installed.", file=sys.stderr)
        return 1

    screenshot_seconds = 0.0
    if image_path is None:
        try:
            from .capture import ScreenshotCaptureError, ScreenshotCaptureSource
            capture_source = ScreenshotCaptureSource(
                output_dir=screenshot_dir,
                window_title=window_title,
            )
            start = time.perf_counter()
            frame = capture_source.capture()
            screenshot_seconds = time.perf_counter() - start
            image_path = Path(frame.image)
        except (OSError, ScreenshotCaptureError, ValueError) as exc:
            print(f"failed to capture screenshot: {exc}", file=sys.stderr)
            return 1

    try:
        start = time.perf_counter()
        metadata = fetch_spire_codex_card_metadata(color=color)
        metadata_seconds = time.perf_counter() - start

        start = time.perf_counter()
        templates, failures = ensure_card_templates(metadata, cache_dir)
        ensure_seconds = time.perf_counter() - start

        start = time.perf_counter()
        session = RecognitionSession.from_templates(templates)
        preload_seconds = time.perf_counter() - start

        hot_times: list[float] = []
        report = None
        for _index in range(runs):
            start = time.perf_counter()
            report = session.recognize_image(image_path)
            hot_times.append(time.perf_counter() - start)
    except (OSError, ValueError) as exc:
        print(f"failed to benchmark recognition: {exc}", file=sys.stderr)
        return 1

    if failures:
        print(f"template download failures: {len(failures)}", file=sys.stderr)
        for failure in failures[:5]:
            print(f"- {failure}", file=sys.stderr)

    print(f"benchmark image: {image_path}")
    print(f"screenshot: {screenshot_seconds:.3f}s")
    print(f"metadata: {metadata_seconds:.3f}s ({len(metadata)} cards)")
    print(f"ensure_templates: {ensure_seconds:.3f}s ({len(templates)} templates)")
    print(
        "preload_features: "
        f"{preload_seconds:.3f}s ({len(session.loaded_templates)} loaded, "
        f"{session.candidates_failed} failed)"
    )
    print(f"single_hot_recognition: {hot_times[0]:.3f}s")
    average = sum(hot_times) / len(hot_times)
    print(f"hot_recognition_average: {average:.3f}s over {runs} runs")
    print(f"hot_recognition_times: {', '.join(f'{item:.3f}' for item in hot_times)}")
    if report is not None:
        for line in format_card_reward_recognition(report):
            print(line)
    return 0


def benchmark_card_reward_ocr(
    image_path: Path,
    recommendations_path: Path,
    runs: int,
) -> int:
    if runs < 1:
        print("--runs must be at least 1", file=sys.stderr)
        return 1

    try:
        from .recognition.card_reward import format_card_reward_recognition
        from .recognition.card_reward_ocr import OcrCardRewardSession

        recommendations = RecommendationStore.from_file(recommendations_path)

        start = time.perf_counter()
        session = OcrCardRewardSession(recommendations)
        preload_seconds = time.perf_counter() - start

        initial_rss = _current_rss_mb()
        hot_times: list[float] = []
        report = None
        for _index in range(runs):
            start = time.perf_counter()
            report = session.recognize_image(image_path)
            hot_times.append(time.perf_counter() - start)
        final_rss = _current_rss_mb()
    except (OSError, RecommendationDataError, ValueError, ModuleNotFoundError) as exc:
        print(f"failed to benchmark OCR recognition: {exc}", file=sys.stderr)
        return 1

    print(f"benchmark image: {image_path}")
    print(f"preload_ocr: {preload_seconds:.3f}s")
    print(f"single_hot_recognition: {hot_times[0]:.3f}s")
    average = sum(hot_times) / len(hot_times)
    print(f"hot_recognition_average: {average:.3f}s over {runs} runs")
    if initial_rss is None or final_rss is None:
        print("rss: unavailable (install psutil for process RSS)")
    else:
        print(f"initial_rss_mb: {initial_rss:.1f}")
        print(f"final_rss_mb: {final_rss:.1f}")
        print(f"rss_delta_mb: {final_rss - initial_rss:.1f}")
    if report is not None:
        for line in format_card_reward_recognition(report):
            print(line)
    return 0


def _report_needs_fallback(report) -> bool:
    return any(match.card_id is None or match.is_uncertain for match in report.matches)


def _current_rss_mb() -> float | None:
    try:
        import psutil
    except ModuleNotFoundError:
        return None
    return psutil.Process().memory_info().rss / (1024 * 1024)


if __name__ == "__main__":
    raise SystemExit(main())
