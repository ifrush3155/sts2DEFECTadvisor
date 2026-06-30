from __future__ import annotations

from typing import Protocol

from sts2defect.models import EnrichedCard, LibrarySummary


class OverlayPresenter(Protocol):
    def show_card_labels(self, cards: list[EnrichedCard]) -> None:
        """Render card labels over the game window."""

    def show_library_summary(self, summary: LibrarySummary) -> None:
        """Render the card-library summary panel."""

    def hide(self) -> None:
        """Hide overlay content."""
