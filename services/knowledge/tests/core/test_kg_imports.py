from __future__ import annotations

import importlib

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def test_kg_package_import_is_lazy_without_neo4j_driver(monkeypatch, tmp_path) -> None:
    configure_runtime_env(
        monkeypatch,
        tmp_path,
        GRAPH_DB_ENABLED=False,
        GRAPH_DB_TYPE="postgres",
    )
    clear_modules()

    kg_module = importlib.import_module("app.core.kg")

    assert "PostgresGraphStorage" in kg_module.__all__
    assert kg_module.KnowledgeGraphManager.__name__ == "KnowledgeGraphManager"


def test_simple_manager_compat_wrapper_no_longer_requires_neo4j(monkeypatch, tmp_path) -> None:
    configure_runtime_env(
        monkeypatch,
        tmp_path,
        GRAPH_DB_ENABLED=False,
        GRAPH_DB_TYPE="postgres",
    )
    clear_modules()

    simple_manager_module = importlib.import_module("app.core.kg.simple_manager")
    manager = simple_manager_module.KGManager(namespace="compat")

    assert manager.namespace == "compat"
    assert hasattr(manager, "query_nodes")
    assert hasattr(manager, "cleanup")


def test_graph_db_settings_default_to_postgres(monkeypatch, tmp_path) -> None:
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules()

    config_module = importlib.import_module("app.config")

    assert config_module.settings.graph_db.GRAPH_DB_TYPE == "postgres"
