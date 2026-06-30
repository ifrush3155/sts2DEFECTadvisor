from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UserSettings:
    profile_path: Path | None = None


def default_settings_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "STS2DEFECT" / "settings.json"
    return Path.home() / ".sts2defect" / "settings.json"


def load_settings(path: str | Path | None = None) -> UserSettings:
    settings_path = Path(path) if path is not None else default_settings_path()
    if not settings_path.is_file():
        return UserSettings()

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserSettings()

    if not isinstance(payload, dict):
        return UserSettings()

    profile_path = payload.get("profile_path")
    if isinstance(profile_path, str) and profile_path:
        return UserSettings(profile_path=Path(profile_path))
    return UserSettings()


def save_settings(settings: UserSettings, path: str | Path | None = None) -> None:
    settings_path = Path(path) if path is not None else default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "profile_path": str(settings.profile_path) if settings.profile_path is not None else None,
    }
    settings_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
