from __future__ import annotations

import asyncio
import importlib
from requests.auth import HTTPBasicAuth

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_audio_module(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    return importlib.import_module("app.shared.audio_processor.paraformer_transcriber")


def test_audio_transcription_config_from_env_supports_local_basic_auth(monkeypatch, tmp_path) -> None:
    module = _import_audio_module(
        monkeypatch,
        tmp_path,
        AUDIO_TRANSCRIBE_PROVIDER="local",
        AUDIO_TRANSCRIBE_API_BASE="http://127.0.0.1:8002/v1",
        AUDIO_TRANSCRIBE_MODEL_NAME="whisper-1",
        AUDIO_TRANSCRIBE_AUTH_MODE="basic",
        AUDIO_TRANSCRIBE_USERNAME="tester",
        AUDIO_TRANSCRIBE_PASSWORD="secret",
    )

    config = module.AudioTranscriptionConfig.from_env()

    assert config.provider == "local"
    assert config.api_base == "http://127.0.0.1:8002/v1"
    assert config.model_name == "whisper-1"
    assert config.auth_mode == "basic"
    assert config.username == "tester"
    assert config.password == "secret"


def test_paraformer_transcriber_prefers_openai_compatible_remote_transcription(monkeypatch, tmp_path) -> None:
    module = _import_audio_module(monkeypatch, tmp_path)
    captured: dict[str, object] = {}
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake-audio")

    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {"text": "测试转录结果"}

    def _fake_post(url, headers=None, data=None, files=None, timeout=None, proxies=None, auth=None):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = dict(headers or {})
        captured["data"] = dict(data or {})
        captured["timeout"] = timeout
        captured["auth"] = auth
        captured["file_name"] = files["file"][0] if files and "file" in files else None
        return _Response()

    monkeypatch.setattr(module.requests, "post", _fake_post)

    transcriber = module.ParaformerTranscriber(
        lazy_load=True,
        transcription_config=module.AudioTranscriptionConfig(
            provider="local",
            model_name="whisper-1",
            api_base="http://127.0.0.1:8002/v1",
            auth_mode="basic",
            api_key=None,
            username="tester",
            password="secret",
            max_retries=0,
            timeout=30,
        ),
    )

    result = asyncio.run(transcriber.transcribe_audio_file(str(audio_path)))

    assert result["success"] is True
    assert result["full_transcript"] == "测试转录结果"
    assert result["metadata"]["model"] == "whisper-1"
    assert captured["url"] == "http://127.0.0.1:8002/v1/audio/transcriptions"
    assert captured["data"]["model"] == "whisper-1"
    assert captured["file_name"] == "sample.wav"
    assert isinstance(captured["auth"], HTTPBasicAuth)
    assert captured["auth"].username == "tester"
    assert captured["auth"].password == "secret"
    assert "Authorization" not in captured["headers"]
