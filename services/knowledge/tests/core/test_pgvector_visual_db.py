from __future__ import annotations

import importlib

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_visual_db(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(
        monkeypatch,
        tmp_path,
        DB_DATABASE_TYPE="sqlite",
        SQLITE_DATABASE=tmp_path / "runtime" / "storage" / "data" / "visual.sqlite3",
        **env_overrides,
    )
    clear_modules()
    return importlib.import_module("app.core.rag.vector_db.pgvector_visual_db")


def test_visual_dimension_prefers_visual_vector_dimension(monkeypatch, tmp_path) -> None:
    module = _import_visual_db(
        monkeypatch,
        tmp_path,
        VISUAL_VECTOR_DIMENSION="640",
        CLIP_VECTOR_DIMENSION="512",
    )

    assert module._visual_dimension() == 640


def test_visual_dimension_accepts_legacy_clip_vector_dimension(monkeypatch, tmp_path) -> None:
    module = _import_visual_db(
        monkeypatch,
        tmp_path,
        VISUAL_VECTOR_DIMENSION="",
        CLIP_VECTOR_DIMENSION="768",
    )

    assert module._visual_dimension() == 768
