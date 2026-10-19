from __future__ import annotations

import importlib
import sys

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_vector_db_package(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    return importlib.import_module("app.core.rag.vector_db")


def _import_vector_db_factory(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    return importlib.import_module("app.core.rag.vector_db.factory")


def test_vector_db_package_import_is_lazy(monkeypatch, tmp_path) -> None:
    vector_db_module = _import_vector_db_package(monkeypatch, tmp_path, VECTOR_DB_TYPE="pgvector")

    assert "app.core.rag.vector_db.faiss_db" not in sys.modules
    assert "app.core.rag.vector_db.pgvector_db" not in sys.modules
    assert callable(vector_db_module.get_vector_db)
    assert callable(vector_db_module.create_vector_db)


def test_create_vector_db_prefers_pgvector_without_faiss_fallback(monkeypatch, tmp_path) -> None:
    factory = _import_vector_db_factory(monkeypatch, tmp_path, VECTOR_DB_TYPE="pgvector")
    calls: list[str] = []

    class _FakePgVectorDB:
        pass

    def _fake_instantiate_backend(db_type: str):
        calls.append(db_type)
        if db_type != "pgvector":
            raise AssertionError(f"unexpected fallback backend: {db_type}")
        return _FakePgVectorDB()

    monkeypatch.setattr(factory, "_instantiate_backend", _fake_instantiate_backend)

    vector_db = factory.create_vector_db()

    assert isinstance(vector_db, _FakePgVectorDB)
    assert calls == ["pgvector"]
