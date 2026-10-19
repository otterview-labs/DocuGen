from __future__ import annotations

import importlib

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_unified_config(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    return importlib.import_module("app.core.llm.unified_config")


def test_local_provider_default_model_ids_route_to_local_config(
    monkeypatch,
    tmp_path,
) -> None:
    module = _import_unified_config(
        monkeypatch,
        tmp_path,
        LLM_PROVIDER="local",
        LOCAL_LLM_ENDPOINT="http://127.0.0.1:8001/v1",
        LOCAL_LLM_MODEL_NAME="qwen3-8b-instruct",
    )

    config = module.get_unified_llm_config()

    assert config.get_default_model_id(module.TaskType.SIMPLE_CHAT) == "local-llm"
    assert config.get_default_model_id(module.TaskType.AGENT_CHAT) == "local-llm"


def test_default_embedding_config_supports_basic_auth(monkeypatch, tmp_path) -> None:
    module = _import_unified_config(
        monkeypatch,
        tmp_path,
        EMBEDDING_PROVIDER="local",
        EMBEDDING_LOCAL_EMBEDDING_URL="http://127.0.0.1:8001/v1",
        EMBEDDING_LOCAL_EMBEDDING_MODEL="bge-m3",
        EMBEDDING_LOCAL_EMBEDDING_AUTH_MODE="basic",
        EMBEDDING_LOCAL_EMBEDDING_USERNAME="tester",
        EMBEDDING_LOCAL_EMBEDDING_PASSWORD="secret",
    )

    config = module.get_embedding_config()

    assert config["model_type"] == "Local"
    assert config["auth_mode"] == "basic"
    assert config["username"] == "tester"
    assert config["password"] == "secret"


def test_unified_config_no_longer_exports_legacy_qwen_helper_functions(monkeypatch, tmp_path) -> None:
    module = _import_unified_config(monkeypatch, tmp_path)

    assert hasattr(module, "get_model_config")
    assert hasattr(module, "get_embedding_config")
    assert not hasattr(module, "get_qwen_agent_config")
    assert not hasattr(module, "get_basic_llm_config")
