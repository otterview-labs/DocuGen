from __future__ import annotations

import importlib

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_config(monkeypatch, tmp_path, **env_overrides):
    paths = configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    module = importlib.import_module("app.config")
    return module, paths


def test_storage_settings_read_storage_prefixed_env_paths(monkeypatch, tmp_path) -> None:
    config_module, paths = _import_config(monkeypatch, tmp_path)

    settings = config_module.settings

    assert settings.storage.STORAGE_ROOT == str(paths["storage_root"])
    assert settings.storage.DATA_DIR == str(paths["data_dir"])
    assert settings.storage.UPLOADS_DIR == str(paths["uploads_dir"])
    assert settings.storage.STATIC_DIR == str(paths["static_dir"])
    assert settings.storage.INDICES_DIR == str(paths["indices_dir"])
    assert settings.storage.LOGS_DIR == str(paths["logs_dir"])
    assert settings.storage.TEMP_DIR == str(paths["temp_dir"])
    assert settings.storage.WORKSPACE_DIR == str(paths["workspace_dir"])


def test_vector_db_settings_accept_legacy_vector_env_names(monkeypatch, tmp_path) -> None:
    config_module, _ = _import_config(
        monkeypatch,
        tmp_path,
        VECTOR_DB_TYPE="",
        VECTOR_DB_DIMENSION="",
        VECTOR_VECTOR_DB_TYPE="pgvector",
        VECTOR_VECTOR_DB_DIMENSION="2048",
    )

    settings = config_module.settings

    assert settings.vector_db.DB_TYPE == "pgvector"
    assert settings.vector_db.VECTOR_DB_TYPE == "pgvector"
    assert settings.vector_db.DB_DIMENSION == 2048
    assert settings.vector_db.VECTOR_DB_DIMENSION == 2048


def test_embedding_settings_accept_legacy_openai_provider_and_model_names(monkeypatch, tmp_path) -> None:
    config_module, _ = _import_config(
        monkeypatch,
        tmp_path,
        EMBEDDING_PROVIDER="",
        EMBEDDING_MODEL_TYPE="OpenAI",
        EMBEDDING_MODEL_NAME="legacy-embedding-model",
    )

    settings = config_module.settings

    assert settings.embedding.PROVIDER == "openai"
    assert settings.embedding.EMBEDDING_PROVIDER == "openai"
    assert settings.embedding.OPENAI_EMBEDDING_MODEL == "legacy-embedding-model"


def test_llm_settings_only_keep_openai_local_provider_and_auth_config(monkeypatch, tmp_path) -> None:
    config_module, _ = _import_config(
        monkeypatch,
        tmp_path,
        LLM_PROVIDER="local",
        OPENAI_API_KEY="",
        LLM_API_KEY="legacy-openai-key",
        LOCAL_LLM_AUTH_MODE="basic",
        LOCAL_LLM_USERNAME="jetlinks",
        LOCAL_LLM_PASSWORD="secret-password",
    )

    settings = config_module.settings

    assert settings.llm.LLM_PROVIDER == "local"
    assert settings.llm.OPENAI_API_KEY == "legacy-openai-key"
    assert settings.llm.LOCAL_LLM_AUTH_MODE == "basic"
    assert settings.llm.LOCAL_LLM_USERNAME == "jetlinks"
    assert settings.llm.LOCAL_LLM_PASSWORD == "secret-password"
    assert not hasattr(settings.llm, "QWEN_MODEL_NAME")
    assert not hasattr(settings.llm, "DASHSCOPE_API_KEY")


def test_default_database_and_vector_db_are_pg_first(monkeypatch, tmp_path) -> None:
    paths = configure_runtime_env(monkeypatch, tmp_path)
    for key in (
        "DB_DATABASE_TYPE",
        "DB_MYSQL_HOST",
        "DB_MYSQL_PORT",
        "DB_MYSQL_USER",
        "DB_MYSQL_PASSWORD",
        "DB_MYSQL_DATABASE",
        "VECTOR_DB_TYPE",
        "VECTOR_VECTOR_DB_TYPE",
    ):
        monkeypatch.delenv(key, raising=False)

    clear_modules()
    config_module = importlib.import_module("app.config")
    settings = config_module.settings

    assert settings.storage.STORAGE_ROOT == str(paths["storage_root"])
    assert settings.database.DB_DATABASE_TYPE == "postgresql"
    assert settings.database.DB_MYSQL_HOST == "localhost"
    assert settings.database.DB_MYSQL_PORT == 5432
    assert settings.database.DB_MYSQL_USER == "postgres"
    assert settings.database.DB_MYSQL_DATABASE == "jetlinks_knowledge"
    assert settings.vector_db.DB_TYPE == "pgvector"
    assert settings.vector_db.VECTOR_DB_TYPE == "pgvector"
