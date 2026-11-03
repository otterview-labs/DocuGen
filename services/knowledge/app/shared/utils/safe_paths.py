"""Constrain local file access to server-owned storage directories."""
from __future__ import annotations

import os
from pathlib import Path


def contained_path(root: str | Path, path: str | Path) -> Path:
    """Resolve symlinks before checking the directory boundary (not a string prefix)."""
    root_path = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root_path, path))
    if candidate.startswith(root_path + os.sep):
        return Path(candidate)
    raise ValueError("File is outside the permitted storage directory")


def relative_file_name(value: str) -> str:
    """Reject traversal before compatibility routes try a basename fallback."""
    if not value or '\x00' in value or '\\' in value or value.startswith('/'):
        raise ValueError("Invalid relative file path")
    if any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError("Invalid relative file path")
    return value


def local_media_path(path: str | Path) -> Path:
    """Only uploaded/downloaded files may reach file detection or media tools."""
    from app.config import settings

    for root in (
        Path(settings.storage.STATIC_DIR) / 'uploads',
        settings.storage.UPLOADS_DIR,
        settings.storage.TEMP_DIR,
    ):
        try:
            return contained_path(root, os.path.abspath(path))
        except ValueError:
            continue
    raise ValueError("File is outside the permitted media directories")
