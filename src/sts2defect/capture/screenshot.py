from __future__ import annotations

import ctypes
import ctypes.wintypes
import platform
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageGrab

from sts2defect.capture.interfaces import CaptureFrame
from sts2defect.models import Bounds


ScreenGrabber = Callable[[tuple[int, int, int, int] | None], Image.Image]
WindowLocator = Callable[[str], tuple[int, int, int, int]]


class ScreenshotCaptureError(RuntimeError):
    pass


class ScreenshotCaptureSource:
    def __init__(
        self,
        output_dir: str | Path | None = None,
        window_title: str | None = None,
        persist: bool = True,
        grabber: ScreenGrabber | None = None,
        window_locator: WindowLocator | None = None,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else _default_screenshot_dir()
        self.window_title = window_title
        self.persist = persist
        self.grabber = grabber or _grab_screen
        self.window_locator = window_locator or find_window_rect_by_title

    def capture(self) -> CaptureFrame:
        bbox = None
        if self.window_title:
            bbox = self.window_locator(self.window_title)
        image = self.grabber(bbox)
        if image.mode != "RGB":
            image = image.convert("RGB")

        frame_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        frame_image: object = image
        if self.persist:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            image_path = self.output_dir / f"card-reward-screen-{frame_id}.png"
            image.save(image_path)
            frame_image = image_path

        if bbox:
            left, top, right, bottom = bbox
            bounds = Bounds(x=left, y=top, width=right - left, height=bottom - top)
        else:
            bounds = Bounds(x=0, y=0, width=image.width, height=image.height)

        return CaptureFrame(
            frame_id=frame_id,
            window_bounds=bounds,
            image=frame_image,
        )


def find_window_rect_by_title(title: str) -> tuple[int, int, int, int]:
    if platform.system() != "Windows":
        raise ScreenshotCaptureError("--window-title is only supported on Windows")

    user32 = ctypes.windll.user32
    matches: list[int] = []
    needle = title.casefold()

    enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if needle in buffer.value.casefold():
            matches.append(hwnd)
        return True

    user32.EnumWindows(enum_windows_proc(callback), 0)
    if not matches:
        raise ScreenshotCaptureError(f"window not found: {title}")

    rect = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(matches[0], ctypes.byref(rect)):
        raise ScreenshotCaptureError(f"failed to read window bounds: {title}")
    if rect.right <= rect.left or rect.bottom <= rect.top:
        raise ScreenshotCaptureError(f"invalid window bounds: {title}")
    return (rect.left, rect.top, rect.right, rect.bottom)


def _grab_screen(bbox: tuple[int, int, int, int] | None = None) -> Image.Image:
    try:
        if bbox:
            return ImageGrab.grab(bbox=bbox)
        return ImageGrab.grab(all_screens=True)
    except TypeError:
        return ImageGrab.grab(bbox=bbox)


def _default_screenshot_dir() -> Path:
    return Path(tempfile.gettempdir()) / "sts2defect" / "screenshots"
