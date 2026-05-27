"""RefChecker version metadata.

`APP_VERSION` has a static fallback for source checkouts, but packaged builds can
override it without editing source files:

- `REFCHECKER_APP_VERSION` environment variable.
- `VERSION.txt` next to a packaged executable, or next to its parent portable
  package directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_APP_VERSION = "1.2.0"


def _clean_version(value: str | None) -> str:
    return (value or "").strip()


def _read_version_file(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8-sig").splitlines()[0].strip()
    except (OSError, IndexError, UnicodeError):
        return ""
    return value.lstrip("\ufeff")


def _candidate_version_files() -> list[Path]:
    candidates: list[Path] = []

    explicit_path = _clean_version(os.getenv("REFCHECKER_VERSION_FILE"))
    if explicit_path:
        candidates.append(Path(explicit_path))

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([
            exe_dir / "VERSION.txt",
            exe_dir.parent / "VERSION.txt",
        ])
        bundle_dir = Path(getattr(sys, "_MEIPASS", ""))
        if str(bundle_dir):
            candidates.append(bundle_dir / "VERSION.txt")

    try:
        source_root = Path(__file__).resolve().parents[1]
        candidates.append(source_root / "VERSION.txt")
    except (OSError, IndexError):
        pass

    return candidates


def _detect_app_version() -> str:
    env_version = _clean_version(os.getenv("REFCHECKER_APP_VERSION"))
    if env_version:
        return env_version

    for candidate in _candidate_version_files():
        value = _read_version_file(candidate)
        if value:
            return value

    return DEFAULT_APP_VERSION


APP_VERSION = _detect_app_version()

