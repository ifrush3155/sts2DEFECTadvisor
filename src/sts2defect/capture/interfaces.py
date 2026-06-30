from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sts2defect.models import Bounds


@dataclass(frozen=True)
class CaptureFrame:
    frame_id: str
    window_bounds: Bounds
    image: object


class CaptureSource(Protocol):
    def capture(self) -> CaptureFrame:
        """Capture one frame from the configured source."""
