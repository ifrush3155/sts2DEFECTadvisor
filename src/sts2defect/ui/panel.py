from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sts2defect.recommendations import RecommendationStore
from sts2defect.savefiles import SaveFileError, load_profile_deck_snapshot
from sts2defect.settings import UserSettings, load_settings, save_settings
from sts2defect.sts2mcp import Sts2McpClientError, Sts2McpReadOnlyClient
from sts2defect.ui.view_model import (
    CardRewardCardView,
    CardRewardPanelView,
    DeckInterfaceView,
    DeckSnapshotPanelView,
    build_card_reward_view,
    build_deck_snapshot_view,
    build_visual_card_reward_view,
)


class Sts2DefectPanel(QWidget):
    def __init__(
        self,
        recommendations: RecommendationStore,
        base_url: str = "http://localhost:15526",
        deck_interval_ms: int = 2000,
        card_reward_interval_ms: int = 1000,
    ) -> None:
        super().__init__()
        self.recommendations = recommendations
        self.settings = load_settings()
        self.setWindowTitle("STS2DEFECT")
        self.setWindowIcon(QIcon(str(_window_icon_path())))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumSize(_panel_minimum_size())

        tabs = QTabWidget()
        self.card_reward_page = CardRewardPage(recommendations, base_url)
        tabs.addTab(self.card_reward_page, "选牌推荐")
        self.deck_page = DeckStatsPage(recommendations, self.settings)
        tabs.addTab(self.deck_page, "牌组统计")

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(tabs)
        self.setLayout(root)
        self.setStyleSheet(_style_sheet())

        self.deck_timer = QTimer(self)
        self.deck_timer.timeout.connect(self.deck_page.refresh)
        self.deck_timer.start(deck_interval_ms)
        self.deck_page.refresh()

        self.card_reward_timer = QTimer(self)
        self.card_reward_timer.timeout.connect(self.card_reward_page.refresh)
        self.card_reward_timer.start(card_reward_interval_ms)
        self.card_reward_page.refresh()


class _CardRewardSignals(QObject):
    preload_finished = Signal(object, int, int, int)
    preload_failed = Signal(str)
    visual_finished = Signal(object, str)
    visual_failed = Signal(str)
    mcp_finished = Signal(object)
    mcp_failed = Signal(str)


class CardRewardPage(QWidget):
    def __init__(
        self,
        recommendations: RecommendationStore,
        base_url: str,
    ) -> None:
        super().__init__()
        self.recommendations = recommendations
        self.base_url = base_url
        self.session = None
        self.art_session = None
        self.preload_error: str | None = None
        self.visual_busy = False
        self.mcp_busy = False
        self.signals = _CardRewardSignals()
        self.signals.preload_finished.connect(self._on_preload_finished)
        self.signals.preload_failed.connect(self._on_preload_failed)
        self.signals.visual_finished.connect(self._on_visual_finished)
        self.signals.visual_failed.connect(self._on_visual_failed)
        self.signals.mcp_finished.connect(self._on_mcp_finished)
        self.signals.mcp_failed.connect(self._on_mcp_failed)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("截图识别", "visual")
        self.mode_combo.addItem("STS2MCP 只读", "mcp")
        self.mode_combo.setMinimumWidth(110)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)

        self.source_combo = QComboBox()
        self.source_combo.addItem("全屏", "fullscreen")
        self.source_combo.addItem("窗口标题", "window")
        self.source_combo.setMinimumWidth(80)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        self.window_title_input = QLineEdit("Slay the Spire 2")
        self.window_title_input.setMinimumWidth(110)

        mode_row = FlowLayout(spacing=8)
        mode_row.addWidget(_plain_label("模式", "meta"))
        mode_row.addWidget(self.mode_combo)
        mode_row.addWidget(_plain_label("截图", "meta"))
        mode_row.addWidget(self.source_combo)
        mode_row.addWidget(self.window_title_input)

        self.header = QLabel("选牌推荐")
        self.header.setObjectName("header")
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.status = QLabel("正在预加载 OCR")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.warning = QLabel("")
        self.warning.setObjectName("unknown")
        self.warning.setWordWrap(True)
        self.warning.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(8)
        cards_widget = QWidget()
        cards_widget.setLayout(self.cards_layout)
        scroll = _scroll_area(cards_widget)

        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addLayout(mode_row)
        root.addWidget(self.header)
        root.addWidget(self.status)
        root.addWidget(self.warning)
        root.addWidget(scroll, 1)
        self.setLayout(root)
        self._source_changed()
        self._start_preload()

    def refresh(self) -> None:
        if self.mode_combo.currentData() == "mcp":
            self._refresh_mcp()
            return
        self._refresh_visual()

    def _mode_changed(self) -> None:
        self._source_changed()
        self.refresh()

    def _source_changed(self) -> None:
        visual_mode = self.mode_combo.currentData() == "visual"
        window_mode = self.source_combo.currentData() == "window"
        self.source_combo.setEnabled(visual_mode)
        self.window_title_input.setEnabled(visual_mode and window_mode)

    def _start_preload(self) -> None:
        thread = threading.Thread(target=self._preload_worker, daemon=True)
        thread.start()

    def _preload_worker(self) -> None:
        try:
            from sts2defect.recognition.card_reward_ocr import OcrCardRewardSession

            session = OcrCardRewardSession(self.recommendations)
        except Exception as exc:
            self.signals.preload_failed.emit(str(exc))
            return
        self.signals.preload_finished.emit(
            session,
            len(self.recommendations.known_card_display_names()),
            0,
            0,
        )

    def _refresh_visual(self) -> None:
        if self.session is None:
            if self.preload_error:
                self._render_message(f"截图识别预加载失败: {self.preload_error}")
            else:
                self._render_message("正在预加载 OCR")
            return
        if self.visual_busy:
            return
        self.visual_busy = True
        source_kind = self.source_combo.currentData()
        window_title = None
        if source_kind == "window":
            window_title = self.window_title_input.text().strip() or "Slay the Spire 2"
        thread = threading.Thread(
            target=self._visual_worker,
            args=(window_title,),
            daemon=True,
        )
        thread.start()

    def _visual_worker(self, window_title: str | None) -> None:
        try:
            from sts2defect.capture import ScreenshotCaptureSource

            capture_source = ScreenshotCaptureSource(
                window_title=window_title,
                persist=False,
            )
            frame = capture_source.capture()
            if isinstance(frame.image, Path):
                report = self.session.recognize_image(frame.image)
                image_for_fallback = None
            else:
                image_for_fallback = frame.image
                report = self.session.recognize_image_object(image_for_fallback, label="screen")
            if _report_needs_fallback(report):
                fallback_session = self._art_fallback_session()
                if fallback_session is not None:
                    from sts2defect.recognition.card_reward_ocr import (
                        merge_uncertain_matches_with_fallback,
                    )

                    if image_for_fallback is None:
                        fallback_report = fallback_session.recognize_image(frame.image)
                    else:
                        fallback_report = fallback_session.recognize_image_object(
                            image_for_fallback,
                            label="screen",
                        )
                    report = merge_uncertain_matches_with_fallback(report, fallback_report)
            view = build_visual_card_reward_view(report, self.recommendations)
        except Exception as exc:
            self.signals.visual_failed.emit(str(exc))
            return
        self.signals.visual_finished.emit(view, _capture_source_label(window_title))

    def _art_fallback_session(self):
        if self.art_session is not None:
            return self.art_session
        from sts2defect.recognition.card_reward import RecognitionSession

        templates = _templates_from_existing_cache(
            _default_card_cache_dir(),
            self.recommendations,
        )
        if not templates:
            return None
        self.art_session = RecognitionSession.from_templates(templates)
        return self.art_session

    def _refresh_mcp(self) -> None:
        if self.mcp_busy:
            return
        self.mcp_busy = True
        thread = threading.Thread(target=self._mcp_worker, daemon=True)
        thread.start()

    def _mcp_worker(self) -> None:
        try:
            client = Sts2McpReadOnlyClient(base_url=self.base_url, timeout_seconds=1.0)
            state = client.fetch_card_reward()
            view = build_card_reward_view(state, self.recommendations) if state else None
        except (Sts2McpClientError, OSError, ValueError) as exc:
            self.signals.mcp_failed.emit(str(exc))
            return
        self.signals.mcp_finished.emit(view)

    def _on_preload_finished(
        self,
        session,
        template_count: int,
        download_failures: int,
        load_failures: int,
    ) -> None:
        self.session = session
        self.preload_error = None
        self.status.setText(
            "OCR 截图识别已就绪 | "
            f"known cards {template_count}, fallback templates lazy-loaded"
        )

    def _on_preload_failed(self, message: str) -> None:
        self.preload_error = message
        self._render_message(f"截图识别预加载失败: {message}")

    def _on_visual_finished(self, view: CardRewardPanelView, image_path: str) -> None:
        self.visual_busy = False
        if self.mode_combo.currentData() != "visual":
            return
        self._render_view(view, f"截图: {image_path}")

    def _on_visual_failed(self, message: str) -> None:
        self.visual_busy = False
        if self.mode_combo.currentData() != "visual":
            return
        self._render_message(f"截图识别失败: {message}")

    def _on_mcp_finished(self, view: CardRewardPanelView | None) -> None:
        self.mcp_busy = False
        if self.mode_combo.currentData() != "mcp":
            return
        if view is None:
            self._render_message("STS2MCP 当前状态不是选牌奖励页")
            return
        self._render_view(view, "STS2MCP 只读模式")

    def _on_mcp_failed(self, message: str) -> None:
        self.mcp_busy = False
        if self.mode_combo.currentData() != "mcp":
            return
        self._render_message(f"STS2MCP 读取失败: {message}")

    def _render_view(self, view: CardRewardPanelView, source_text: str) -> None:
        self.header.setText(view.title)
        self.status.setText(f"{len(view.cards)} cards | {source_text}")
        self.warning.setText(view.uncertain_message or "")
        self._clear_cards()
        if not view.cards:
            self.cards_layout.addWidget(_plain_label("没有识别到奖励卡", "status"))
            return
        for card in view.cards:
            self.cards_layout.addWidget(_card_widget(card))
        self.cards_layout.addStretch(1)

    def _render_message(self, message: str) -> None:
        self.header.setText("选牌推荐")
        self.status.setText(message)
        self.warning.setText("")
        self._clear_cards()

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


class DeckStatsPage(QWidget):
    def __init__(
        self,
        recommendations: RecommendationStore,
        settings: UserSettings,
    ) -> None:
        super().__init__()
        self.recommendations = recommendations
        self.profile_path = settings.profile_path

        self.path_input = QLineEdit(str(self.profile_path) if self.profile_path else "")
        self.path_input.setPlaceholderText("选择 STS2 profile 路径")
        self.path_input.setMinimumWidth(120)
        self.path_input.editingFinished.connect(self._use_typed_path)
        browse_button = QPushButton("选择")
        browse_button.clicked.connect(self.choose_profile_path)
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh)

        path_row = FlowLayout(spacing=8)
        path_row.addWidget(self.path_input)
        path_row.addWidget(browse_button)
        path_row.addWidget(refresh_button)

        self.header = QLabel("牌组统计")
        self.header.setObjectName("header")
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.summary = QLabel("请选择 profile 路径")
        self.summary.setObjectName("status")
        self.summary.setWordWrap(True)
        self.summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.source = QLabel("")
        self.source.setObjectName("status")
        self.source.setWordWrap(True)
        self.source.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.unknown = QLabel("")
        self.unknown.setObjectName("unknown")
        self.unknown.setWordWrap(True)
        self.unknown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.detail = QLabel("推荐详情：将鼠标移到推荐指数上，或点击一个指数")
        self.detail.setObjectName("detail")
        self.detail.setWordWrap(True)
        self.detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self.stats_layout = QVBoxLayout()
        self.stats_layout.setSpacing(8)
        stats_widget = QWidget()
        stats_widget.setLayout(self.stats_layout)
        scroll = _scroll_area(stats_widget)

        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addLayout(path_row)
        root.addWidget(self.header)
        root.addWidget(self.summary)
        root.addWidget(self.source)
        root.addWidget(self.unknown)
        root.addWidget(self.detail)
        root.addWidget(scroll, 1)
        self.setLayout(root)

    def choose_profile_path(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择 STS2 profile 路径",
            str(self.profile_path) if self.profile_path else str(Path.home()),
        )
        if not selected:
            return
        self.profile_path = Path(selected)
        self.path_input.setText(str(self.profile_path))
        save_settings(UserSettings(profile_path=self.profile_path))
        self.refresh()

    def refresh(self) -> None:
        if self.profile_path is None:
            self._render_message("请选择 STS2 profile 路径")
            return

        try:
            snapshot = load_profile_deck_snapshot(self.profile_path)
        except SaveFileError as exc:
            self._render_message(str(exc))
            return

        view = build_deck_snapshot_view(snapshot, self.recommendations)
        self._render_view(view)

    def _use_typed_path(self) -> None:
        text = self.path_input.text().strip()
        if not text:
            return
        self.profile_path = Path(text)
        save_settings(UserSettings(profile_path=self.profile_path))
        self.refresh()

    def _render_view(self, view: DeckSnapshotPanelView) -> None:
        self.header.setText(view.title)
        self.summary.setText(view.summary)
        self.source.setText(f"source: {view.source_path}")
        self.unknown.setText(f"unknown cards: {view.unknown_count}")
        self._clear_stats()
        if not view.interfaces:
            self.stats_layout.addWidget(_plain_label("没有匹配到推荐端口", "status"))
            return
        for item in view.interfaces:
            self.stats_layout.addWidget(_deck_stat_card(item, self._show_recommendation_detail))

    def _render_message(self, message: str) -> None:
        self.header.setText("牌组统计")
        self.summary.setText(message)
        self.source.setText("")
        self.unknown.setText("")
        self.detail.setText("推荐详情：将鼠标移到推荐指数上，或点击一个指数")
        self._clear_stats()

    def _show_recommendation_detail(self, detail: str) -> None:
        self.detail.setText(f"推荐详情：{detail}")

    def _clear_stats(self) -> None:
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


def _card_reward_placeholder() -> QWidget:
    widget = QWidget()
    root = QVBoxLayout()
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)
    header = QLabel("选牌推荐")
    header.setObjectName("header")
    body = QLabel("视觉识别尚未接入。当前版本不使用 MCP。")
    body.setObjectName("status")
    body.setWordWrap(True)
    root.addWidget(header)
    root.addWidget(body)
    root.addStretch(1)
    widget.setLayout(root)
    return widget


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class RecommendationDetailLabel(QLabel):
    detail_requested = Signal(str)

    def __init__(self, text: str, detail: str, object_name: str) -> None:
        super().__init__(text)
        self.detail = detail
        self.setObjectName(object_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def enterEvent(self, event) -> None:
        self.detail_requested.emit(self.detail)
        super().enterEvent(event)

    def mousePressEvent(self, event) -> None:
        self.detail_requested.emit(self.detail)
        super().mousePressEvent(event)


def _deck_stat_card(
    interface: DeckInterfaceView,
    detail_callback=None,
) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    layout = QVBoxLayout()
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)
    title_label = QLabel(f"{interface.type_name}: {interface.count}")
    title_label.setObjectName("cardName")
    title_label.setWordWrap(True)
    layout.addWidget(title_label)

    row = FlowLayout(spacing=6)
    row.addWidget(_plain_label("推荐指数: " if interface.show_recommend_indexes else "卡牌: ", "meta"))
    for item in interface.items:
        object_name = _deck_item_object_name(interface, item.is_upgraded)
        if interface.show_recommend_indexes and item.tooltip:
            item_label = RecommendationDetailLabel(
                item.label,
                f"{item.label} {item.tooltip}",
                object_name,
            )
            if detail_callback is not None:
                item_label.detail_requested.connect(detail_callback)
        else:
            item_label = QLabel(item.label)
            item_label.setObjectName(object_name)
            item_label.setWordWrap(True)
        row.addWidget(item_label)
    layout.addLayout(row)
    frame.setLayout(layout)
    return frame


def _plain_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    return label


def _scroll_area(widget: QWidget) -> QScrollArea:
    widget.setMinimumWidth(0)
    scroll = QScrollArea()
    scroll.setMinimumSize(0, 0)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


def _default_card_cache_dir() -> Path:
    project_cache = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "samples"
        / "card-reward"
        / "debug-cache"
    )
    if project_cache.is_dir():
        return project_cache
    return Path.home() / ".cache" / "sts2defect" / "card-images" / "defect"


def _window_icon_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "window-icon.png"


def _panel_minimum_size() -> QSize:
    return QSize(300, 120)


def _capture_source_label(window_title: str | None) -> str:
    if window_title:
        return f"窗口: {window_title}"
    return "全屏截图"


def _report_needs_fallback(report) -> bool:
    return any(match.card_id is None or match.is_uncertain for match in report.matches)


def _templates_from_existing_cache(
    cache_dir: Path, recommendations: RecommendationStore
):
    from sts2defect.recognition.card_reward import CardTemplate

    if not cache_dir.is_dir():
        return []

    templates = []
    for image_path in sorted(cache_dir.iterdir()):
        if image_path.suffix.lower() not in {".webp", ".png", ".jpg", ".jpeg"}:
            continue
        card_id = image_path.stem
        templates.append(
            CardTemplate(
                card_id=card_id,
                display_name=recommendations.card_display_name(card_id) or card_id,
                image_path=image_path,
            )
        )
    return templates


def _deck_item_object_name(interface: DeckInterfaceView, is_upgraded: bool) -> str:
    if is_upgraded:
        return "upgradedRecommendation" if interface.show_recommend_indexes else "upgradedMeta"
    return "recommendation" if interface.show_recommend_indexes else "meta"


def _card_widget(card: CardRewardCardView) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    layout = QVBoxLayout()
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)

    name = QLabel(f"{card.index}. {card.display_name}")
    name.setObjectName("upgradedCardName" if card.is_upgraded else "cardName")
    name.setWordWrap(True)
    meta = QLabel(f"{card.metadata} | {card.card_id}")
    meta.setObjectName("meta")
    meta.setWordWrap(True)
    layout.addWidget(name)
    layout.addWidget(meta)

    if card.is_unknown:
        unknown = QLabel(card.unknown_message or "推荐表未收录")
        unknown.setObjectName("unknown")
        unknown.setWordWrap(True)
        layout.addWidget(unknown)
    else:
        for recommendation in card.recommendations:
            label = QLabel(f"{recommendation.type_name} {recommendation.recommend_index}")
            label.setObjectName(
                "upgradedRecommendation" if recommendation.is_upgraded else "recommendation"
            )
            label.setWordWrap(True)
            layout.addWidget(label)

    frame.setLayout(layout)
    return frame


def run_panel_app(
    recommendations_path: Path,
    base_url: str = "http://localhost:15526",
    interval_ms: int = 2000,
) -> int:
    recommendations = RecommendationStore.from_file(recommendations_path)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    panel = Sts2DefectPanel(
        recommendations=recommendations,
        base_url=base_url,
        deck_interval_ms=interval_ms,
    )
    panel.show()
    return app.exec()


def _style_sheet() -> str:
    return """
    QWidget {
        background: #202225;
        color: #f1f3f5;
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 13px;
    }
    QTabWidget::pane {
        border: 0;
    }
    QTabBar::tab {
        background: #2b2f33;
        color: #ced4da;
        padding: 8px 12px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background: #343a40;
        color: #ffffff;
    }
    QLineEdit {
        background: #2b2f33;
        border: 1px solid #495057;
        border-radius: 4px;
        padding: 6px;
    }
    QPushButton {
        background: #3d444c;
        border: 1px solid #5c6670;
        border-radius: 4px;
        padding: 6px 10px;
    }
    QPushButton:hover {
        background: #4b545e;
    }
    QLabel#header {
        font-size: 16px;
        font-weight: 700;
    }
    QLabel#status {
        color: #adb5bd;
    }
    QFrame#card {
        background: #2b2f33;
        border: 1px solid #3d444c;
        border-radius: 6px;
    }
    QLabel#cardName {
        font-size: 15px;
        font-weight: 700;
    }
    QLabel#upgradedCardName {
        color: #63e6be;
        font-size: 15px;
        font-weight: 700;
    }
    QLabel#meta {
        color: #adb5bd;
    }
    QLabel#detail {
        color: #cfe8ff;
        background: #252a2f;
        border: 1px solid #3d444c;
        border-radius: 4px;
        padding: 6px;
    }
    QLabel#upgradedMeta {
        color: #63e6be;
        font-weight: 700;
    }
    QLabel#recommendation {
        color: #d8f3dc;
        background: #233028;
        border: 1px solid #365244;
        border-radius: 4px;
        padding: 2px 5px;
    }
    QLabel#upgradedRecommendation {
        color: #63e6be;
        background: #203731;
        border: 1px solid #3b6b5c;
        border-radius: 4px;
        padding: 2px 5px;
        font-weight: 700;
    }
    QLabel#unknown {
        color: #ffd166;
    }
    """
