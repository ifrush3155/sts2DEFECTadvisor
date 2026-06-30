from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from sts2defect.capture import CaptureFrame
from sts2defect.models import RecognizedCard


class PageType(StrEnum):
    CARD_REWARD = "CARD_REWARD"
    CARD_LIBRARY = "CARD_LIBRARY"
    GAMEPLAY = "GAMEPLAY"
    UNKNOWN = "UNKNOWN"
    WINDOW_LOST = "WINDOW_LOST"


class PageRecognizer(Protocol):
    def recognize_page(self, frame: CaptureFrame) -> PageType:
        """Classify the current game page."""


class CardRecognizer(Protocol):
    def recognize_cards(self, frame: CaptureFrame) -> list[RecognizedCard]:
        """Recognize visible cards in the current frame."""
