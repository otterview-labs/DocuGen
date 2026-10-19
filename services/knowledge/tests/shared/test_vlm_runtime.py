from __future__ import annotations

import importlib
from requests.auth import HTTPBasicAuth

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_vlm_modules(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    config_module = importlib.import_module("app.shared.vlm.config")
    analyzer_module = importlib.import_module("app.shared.vlm.vision_analyzer")
    return config_module, analyzer_module


def test_vlm_config_from_env_supports_local_basic_auth(monkeypatch, tmp_path) -> None:
    config_module, _ = _import_vlm_modules(
        monkeypatch,
        tmp_path,
        VLM_PROVIDER="local",
        VLM_API_BASE="http://127.0.0.1:8001/v1",
        VLM_MODEL_NAME="qwen3-vl-4b-instruct",
        VLM_API_AUTH_MODE="basic",
        VLM_API_USERNAME="tester",
        VLM_API_PASSWORD="secret",
    )

    config = config_module.VLMConfig.from_env()

    assert config.provider == "local"
    assert config.model_type == "local"
    assert config.api_base == "http://127.0.0.1:8001/v1"
    assert config.auth_mode == "basic"
    assert config.username == "tester"
    assert config.password == "secret"


def test_vision_analyzer_calls_openai_compatible_endpoint_with_basic_auth(monkeypatch, tmp_path) -> None:
    config_module, analyzer_module = _import_vlm_modules(monkeypatch, tmp_path)
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "视觉描述结果"
                        }
                    }
                ]
            }

    def _fake_post(url, headers=None, json=None, timeout=None, proxies=None, auth=None):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = dict(headers or {})
        captured["json"] = json
        captured["timeout"] = timeout
        captured["auth"] = auth
        return _Response()

    monkeypatch.setattr(analyzer_module.requests, "post", _fake_post)

    analyzer = analyzer_module.VisionAnalyzer(
        config_module.VLMConfig(
            provider="local",
            model_name="qwen3-vl-4b-instruct",
            api_base="http://127.0.0.1:8001/v1",
            auth_mode="basic",
            username="tester",
            password="secret",
        )
    )

    response_text = analyzer._call_llm_with_retry(
        [{"role": "user", "content": [{"type": "text", "text": "请分析这张图片"}]}]
    )

    assert response_text == "视觉描述结果"
    assert captured["url"] == "http://127.0.0.1:8001/v1/chat/completions"
    assert isinstance(captured["auth"], HTTPBasicAuth)
    assert captured["auth"].username == "tester"
    assert captured["auth"].password == "secret"
    assert "Authorization" not in captured["headers"]
